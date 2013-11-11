import logging
import time

from .conf import config
from .resource import Drive, Server, LibDrive
from .generic import GenericClient

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
                    "objects": [d,],
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
        resp = self.c_drive.list(query_params={"fields":'name,uuid'})
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
        resp = self.c_drive.list_detail(query_params={"fields":'name,uuid,status'})
        resp = filter(lambda x: x['uuid'] in uuids, resp)
        return resp

