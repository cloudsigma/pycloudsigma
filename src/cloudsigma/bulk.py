import logging
import time

from cloudsigma.conf import config
from cloudsigma.resource import Drive, Server, LibDrive
from cloudsigma.generic import GenericClient

LOG = logging.getLogger(__name__)


class BulkBase(object):
    """
    Common base class for all stress operations.
    """
    def __init__(self, id_prefix):
        """
        @param id_prefix: a string prefix that is used in created artifacts names
        """
        self.id_prefix = id_prefix
        self.id_counter = 0

        self.c = GenericClient()
        self.c_drive = Drive()
        self.c_libdrive = LibDrive()
        self.c_guest = Server()

    def get_name(self):
        """
        Generates name for an artifact
        """
        self.id_counter += 1
        return "%s-%.5d" % (self.id_prefix, self.id_counter)

    def filter_by_name_uuid(self, resp, name_or_uuid):
        def _filter(d):
            return (d['uuid'] == name_or_uuid) or (name_or_uuid in d['name'])

        candidates = filter(_filter, resp)
        return candidates


class DrivesBulk(BulkBase):
    CREATE_DRIVE_MEDIA = config.get('CREATE_DRIVE_MEDIA', 'disk')
    CREATE_DRIVE_SIZE = config.get('CREATE_DRIVE_SIZE', 10*1024**3)
    CREATE_DRIVE_DESCRIPTION = config.get('CREATE_DRIVE_DESCRIPTION', 'some descr')

    def __init__(self, media=CREATE_DRIVE_MEDIA, size=CREATE_DRIVE_SIZE,
                description=CREATE_DRIVE_DESCRIPTION,
                *args, **kwargs):
        super(DrivesBulk, self).__init__(*args, **kwargs)

        self.media = media
        self.size = size
        self.description = description

    def generate_definition(self):
        return {
            "media": self.media,
            "name": self.get_name(),
            "size": self.size,
            "meta": {
                "description": self.description,
                }
            }

    def create(self, count):
        """Creates a number of new drives

        @param count: the amount to be created
        """

        drives = []
        for _ in range(count):
            d = self.generate_definition()
            req = {
                    "objects": [d, ],
                }
            resp = self.c_drive.create(req)
            LOG.info('Created drive %r', resp['name'])
            drives.append(resp)
        return drives

    def delete(self, uuid, name):
        self.c_drive.delete(uuid)
        LOG.info('Deleted drive %r', name)

    def wipe(self):
        """Deletes all artifacts created by this identification prefix
        """
        resp = self.get_list()
        for d in resp:
            self.delete(d['uuid'], d['name'])

    def clone(self, count, source_name_or_uuid):
        """Creates a number of new drives, cloning from the given original.

        The source drive is first looked-up in the drives of the current account and then in the drives library

        @param count: the amount to be created
        @param source_name_or_uuid: either the UUID of the source or substring match of its name
        """
        source_drive = self.lookup(source_name_or_uuid)

        drives = []
        for _ in range(count):
            d = {
                    "media": source_drive['media'],
                    "name": self.get_name(),
                    "size": source_drive['size'],
                    "meta": source_drive['meta'],
                    "affinities": source_drive['affinities'],
                }
            resp = self.c_drive.clone(source_drive['uuid'], d)
            LOG.info('Cloned drive %r from %r', resp['name'], source_drive['name'])
            drives.append(resp)

        # Wait for all drives to finish clonning
        drives_uuids = [d['uuid'] for d in drives]

        def is_clonning_finished():

            existing_drives = self.get_detail()
            current_scenario_drives = [d for d in existing_drives if d['uuid'] in drives_uuids]
            current_scenario_drives_statuses = [d['status'] for d in current_scenario_drives]

            return current_scenario_drives_statuses

        statuses = is_clonning_finished()
        while 'cloning_dst' in statuses:
            time.sleep(10)
            drives_statuses_string = '\n'.join(['{}: {}'.format(uuid, status) for uuid, status in zip(drives_uuids, statuses)])
            LOG.info('Waiting for all drives cloning from {} to finish cloning:\n{}'.format(source_drive['uuid'],
                     drives_statuses_string))
            statuses = is_clonning_finished()

        # All finished print final statuses
        drives_statuses_string = '\n'.join(['{}: {}'.format(uuid, status) for uuid, status in zip(drives_uuids, statuses)])
        LOG.info('Finished cloning {} to drives:\n{}'.format(source_drive['uuid'], drives_statuses_string))

        return drives

    def clone_all(self, count=1):
        src_drives = self.get_detail()
        drives = []
        for drv in src_drives:
            if drv['status'] == 'unavailable':
                continue
            for i in range(int(count)):
                d = {
                        "media": drv['media'],
                        "name": 'clone_%s_%i' % (drv['name'], i),
                        "size": drv['size'],
                        "meta": drv['meta'],
                        "affinities": drv['affinities'],
                    }
                resp = self.c_drive.clone(drv['uuid'], d)
                LOG.info('Cloned drive %r from %r', resp['name'], drv['name'])
                drives.append(resp)
        return drives

    def get_list(self):
        """Queries the drives in this account with the given prefix
        """
        resp = self.c_drive.list(query_params={"fields": 'name,uuid'})
        resp = filter(lambda x: x['name'].startswith(self.id_prefix), resp)
        return resp

    def get_detail(self):
        resp = self.c_drive.list_detail()
        resp = filter(lambda x: x['name'].startswith(self.id_prefix), resp)
        return resp

    def lookup(self, name_or_uuid):
        resp = self.c_drive.list_detail()
        candidates = self.filter_by_name_uuid(resp, name_or_uuid)
        if not candidates:
            resp = self.c_drive.list_library_drives()
            candidates = self.filter_by_name_uuid(resp, name_or_uuid)
        if len(candidates) == 0:
            raise Exception("Could not find %s with lookup key %s" % (
                    self.__class__.__name__, name_or_uuid))
        return candidates[0]

    def get_by_uuids(self, uuids):
        """Queries the drives in this account with the given prefix
        """
        resp = self.c_drive.list_detail(query_params={"fields": 'name,uuid,status'})
        resp = filter(lambda x: x['uuid'] in uuids, resp)
        return resp

## TODO: Port this class
#class GuestsBulk(BulkBase):
#    def __init__(self, cpu=None, mem=None, smp=None, *args, **kwargs):
#        super(GuestsBulk, self).__init__(self, *args, **kwargs)
#
#        self.cpu = cpu if cpu else settings.API.STRESS_CLIENT_CREATE_GUEST_CPU
#        self.mem = mem if mem else settings.API.STRESS_CLIENT_CREATE_GUEST_MEM
#        self.smp = smp if smp else settings.API.STRESS_CLIENT_CREATE_GUEST_SMP
#        self.description = settings.API.STRESS_CLIENT_CREATE_GUEST_DESCRIPTION
#
#        self.drives = DrivesBulk(id_prefix=self.id_prefix)
#        self.cdroms = DrivesBulk(id_prefix=self.id_prefix, media="cdrom")
#        self.tag = Tag(id_prefix=self.id_prefix)
#
#    def get_list(self):
#        """Queries the guests in this account with the given prefix
#        """
#        resp = self.response_helper(self.c_guest.list({"limit":9000}), return_list=True)
#        resp = filter(lambda x: x['name'].startswith(str(self.id_prefix)), resp)
#        return resp
#
#    def get_detail(self):
#        """Queries the guests in this account with the given prefix
#        """
#        resp = self.response_helper(self.c_guest.list_detail({"limit":9000}), return_list=True)
#        resp = filter(lambda x: x['name'].startswith(str(self.id_prefix)), resp)
#        return resp
#
#    def get_guest_drive_defs(self, data_drives, enum_from=0, ):
#        res = []
#        for dnum, drive in enumerate(data_drives, start=enum_from):
#            dev_chan = "%i:%i" % (dnum/16, dnum%16)
#            res.append(
#                {
#                    "dev_channel": dev_chan,
#                    "device": "virtio",
#                    "drive": drive['uuid'],
#                    }
#
#            )
#        return res
#
#    def wipe(self):
#        """Deletes all artifacts created by this identification prefix
#        """
#        self.stop()
#
#        resp = self.get_detail()
#
#        for g in resp:
#            self.c_guest.delete(g['uuid'])
#            LOG.info('Deleted guest %r', g['name'])
#            guest_drives_uuids = []
#            for d in g['drives']:
#                guest_drives_uuids.append(d['drive']['uuid'])
#
#            guest_drives = self.drives.get_by_uuids(guest_drives_uuids)
#            for d in guest_drives:
#                if 'disk'==d['media']:
#                    self.drives.delete(d['uuid'], d['name'])
#        self.tag.wipe()
#
#    def stop(self, count=None):
#        resp = self.get_detail()
#
#        count_stopped = 0
#        for d in resp:
#            if d['status'] == 'running':
#                self.c_guest.stop(d['uuid'])
#                LOG.info('Stopped guest %r', d['name'])
#                count_stopped += 1
#            if count and count_stopped == count:
#                break
#
#    def start(self, count=None, allocation_method=None):
#        resp = self.get_detail()
#
#        count_started = 0
#        for d in resp:
#            if d['status'] == 'stopped':
#                self.c_guest.start(d['uuid'], allocation_method=allocation_method)
#                LOG.info('Started guest %r', d['name'])
#                count_started += 1
#            if count and count_started == count:
#                break
#
#    def create(self, count, boot_name_or_uuid=False, data_drives_num=1,  start=False):
#        """Creates a number of new guests
#
#        @param count: the amount to be created
#        """
#
#        # if there is no specific boot_name_or_uuid create and reuse one for the unittests.
#
#        boot_drive = self.drives.lookup(boot_name_or_uuid)
#
#        for i in range(count):
#            data_drives = self.drives.create(data_drives_num)
#            d = {
#                    "mem": self.mem,
#                    "name": self.get_name(),
#                    "cpu": self.cpu,
#                    "smp": self.smp,
#                    "vnc_password" : 'alabala',
#                    "meta": {
#                          "description": self.description,
#                    },
#                    "drives" : [],
#                }
#
#            enum_from = 0
#
#            if boot_name_or_uuid:
#                d.drives = [{
#                    "boot_order": 1,
#                    "dev_channel": "0:0",
#                    "device": "virtio",
#                    "drive": boot_drive['uuid'],
#                    }]
#                enum_from = 1
#
#            d['drives'] = self.get_guest_drive_defs(data_drives, enum_from=enum_from)
#            req = {
#                    "objects": [d,],
#                }
#            resp = self.response_helper(self.c_guest.create(req))
#            LOG.info('Created guest %r', resp['name'])
#
#            if start:
#                self.c_guest.start(resp['uuid'])
#                LOG.info('Started guest %r', resp['name'])
#
#    def clone(self, count, source_name_or_uuid):
#
#        """Creates a number of new Guests, cloning from the given original.
#
#        The source Guest is looked-up in the guests of the current account
#
#        @param count: the amount to be created
#        @param source_name_or_uuid: either the UUID of the source or substring match of its name
#        """
#        source_guest = self.lookup(source_name_or_uuid)
#
#        guests = []
#        for i in range(count):
#            g = {
#                    "name": self.get_name()
#                }
#            resp = self.response_helper(self.c_guest._action('clone', source_guest['uuid'], data=g))
#            LOG.info('Cloned guest %r from %r', resp['name'], source_guest['name'])
#            guests.append(resp)
#
#        # Wait for all drives to finish clonning
#        guests_uuids = [g['uuid'] for g in guests]
#
#        def is_clonning_finished():
#
#            existing_guests = self.get_detail()
#            drives_uuids = []
#            for g in existing_guests:
#                for d in g['drives']:
#                    drives_uuids.append(d['drive']['uuid'])
#
#            current_scenario_guests_drives = self.drives.get_by_uuids(drives_uuids)
#            drive_status={}
#            for d in current_scenario_guests_drives:
#                drive_status[d['uuid']] = d['status']
#
#            for g in existing_guests:
#                for d in g['drives']:
#                    if d['drive']['uuid'] in drive_status and 'cloning_dst'==drive_status[ d['drive']['uuid'] ]:
#                        g['status'] = 'cloning_dst'
#                        break
#
#            current_scenario_guests = [(g['status']) for g in existing_guests if g['uuid'] in guests_uuids]
#
#            return current_scenario_guests
#
#        statuses = is_clonning_finished()
#        while 'cloning_dst' in statuses:
#            time.sleep(10)
#            guests_statuses_string = '\n'.join(['{}: {}'.format(uuid, status) for uuid, status in zip(guests_uuids, statuses)])
#            LOG.info('Waiting for all drives cloning from {} to finish cloning:\n{}'.format(source_guest['uuid'], guests_statuses_string))
#            statuses = is_clonning_finished()
#
#        # All finished print final statuses
#        guests_statuses_string = '\n'.join(['{}: {}'.format(uuid, status) for uuid, status in zip(guests_uuids, statuses)])
#        LOG.info('Finished cloning {} to guests:\n{}'.format(source_guest['uuid'], guests_statuses_string))
#        return guests
#
#    def lookup(self, name_or_uuid):
#        resp = self.response_helper(self.c_guest.list_detail({"limit":9000,}), return_list=True)
#        candidates = self.filter_by_name_uuid(resp, name_or_uuid)
#        if len(candidates) == 0:
#            raise Exception("Could not find %s with lookup key %s" % (
#                    self.__class__.__name__, name_or_uuid))
#        return candidates[0]
#
#    def create_from_drive_and_net(self, max_count=None, start=False, drives_per_guest=1):
#        drives_list = self.drives.get_detail()
#        vlan_uuid = self.get_vlan_uuid()
#
#        if vlan_uuid:
#            nics = [{"model": "virtio", "ip_v4_conf": {"conf": "dhcp"}},
#                    {"model": "virtio", "vlan": {'uuid': vlan_uuid}}
#            ]
#        else:
#            nics = [{"model": "virtio", "ip_v4_conf": {"conf": "dhcp"}}]
#
#        drives = []
#        for n, drive in enumerate(drives_list):
#            if max_count is not None and n >= max_count:
#                break
#
#            drives.append(drive)
#
#            if len(drives) % drives_per_guest == 0:
#
#                d = {"mem": self.mem,
#                     "name": '{}-guest'.format(drive['name']),
#                     "cpu": self.cpu,
#                     "smp": self.smp,
#                     "vnc_password": 'alabala',
#                     "meta": {
#                              "description": self.description,
#                     },
#                     "drives": [
#                     ],
#                     "nics": nics
#                }
#
#                d['drives'] = self.get_guest_drive_defs(drives)
#                req = {
#                        "objects": [d,],
#                    }
#                drives = []
#                resp = self.response_helper(self.c_guest.create(req))
#                LOG.info('Created guest %r', resp['name'])
#
#                if start:
#                    self.c_guest.start(resp['uuid'])
#                    LOG.info('Started guest %r', resp['name'])
#        if drives:
#            d = {"mem": self.mem,
#                 "name": '{}-guest'.format(drive['name']),
#                 "cpu": self.cpu,
#                 "smp": self.smp,
#                 "vnc_password": 'alabala',
#                 "meta": {
#                     "description": self.description,
#                     },
#                 "drives": [
#                 ],
#                 "nics": nics
#            }
#
#            d['drives'] = self.get_guest_drive_defs(drives)
#            req = {
#                "objects": [d,],
#                }
#            resp = self.response_helper(self.c_guest.create(req))
#            LOG.info('Created guest %r', resp['name'])
#
#            if start:
#                self.c_guest.start(resp['uuid'])
#                LOG.info('Started guest %r', resp['name'])
#
#    def create_from_libdrives_and_net(self, guest_clones_count=None, start=False):
#        guest_clones_count = guest_clones_count if guest_clones_count else 1
#
#        drives_list = self.response_helper(self.c_libdrive.list({"limit":9000}), return_list=True)
#        vlan_uuid = self.get_vlan_uuid()
#        if vlan_uuid:
#            nics = [{"model": "virtio", "ip_v4_conf": {"conf": "dhcp"}},
#                    {"model": "virtio", "vlan": {'uuid': vlan_uuid}}
#            ]
#        else:
#            nics = [{"model": "virtio", "ip_v4_conf": {"conf": "dhcp"}}]
#
#        guests = []
#        for n,libdrive in enumerate(drives_list):
#            if libdrive['status'] == 'unavailable':
#                continue
#
#            for i in range(guest_clones_count):
#                guest_name = '{}-{}-guest{}'.format(self.id_prefix, libdrive['name'], i if i>1 else '')
#
#                if "disk" == libdrive['media']:
#                    resp = self.response_helper(self.c_drive.clone(libdrive['uuid'], {'name': '{}-{}'.format(self.id_prefix, libdrive['name'])}))
#                    LOG.info('Cloned drive %r from %r', resp['name'], libdrive['name'])
#                    drive = resp
#                else:
#                    drive = libdrive
#
#                d = {"mem": self.mem,
#                     "name": guest_name,
#                     "cpu": self.cpu,
#                     "smp": self.smp,
#                     "vnc_password": 'alabala',
#                     "meta": {
#                              "description": self.description,
#                     },
#                     "drives": [{"boot_order": 1,
#                                 "dev_channel": "0:0",
#                                 "device": "virtio" if "virtio" in drive['name'] else "ide",
#                                 "drive": drive['uuid'],
#                                 }
#                     ],
#                     "nics": nics
#                }
#                req = {
#                        "objects": [d,],
#                    }
#                resp = self.response_helper(self.c_guest.create(req))
#                LOG.info('Created guest %r', resp['name'])
#                guests.append(resp)
#
#        print 'Please check if all drives are cloned before trying to start guests'
##        TODO: check if drives cloning is ready and start
##        if start:
##            self.c_guest.start(resp['uuid'])
##            LOG.info('Started guest %r', resp['name'])
#
#    def get_runtime(self):
#        resp = self.get_list()
#        r = []
#        for d in resp:
#            resp = self.response_helper(self.c_guest.runtime(d['uuid']))
#            LOG.info('Runtime for guest %r', resp)
#        return r
#
#    def get_vlan_uuid(self):
#        resp = self.response_helper(self.c_vlan.list_detail(), return_list=True)
#        for vlan in resp:
#            try:
#                if vlan['meta']['name'].startswith(self.id_prefix):
#                    return vlan['uuid']
#            except KeyError:
#                continue
#
#        return None
