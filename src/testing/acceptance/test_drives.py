import unittest
import time
from nose.plugins.attrib import attr

import cloudsigma.resource as cr
import cloudsigma.errors as errors

from testing.utils import DumpResponse
from testing.acceptance.common import StatefulResourceTestBase


@attr('acceptance_test')
class DriveBasicTest(StatefulResourceTestBase):

    def setUp(self):
        super(DriveBasicTest, self).setUp()
        self.client = cr.Drive()
        self.dump_response = DumpResponse(clients=[self.client])

    @attr('docs_snippets')
    def test_drive_cycle(self):
        drive_def = {
            'name': 'test_drive_1',
            'size': 1024000000,
            'media': 'disk',
        }

        with self.dump_response('drive_create_minimal'):
            drive = self.client.create(drive_def)

        self.assertEqual(drive['status'], 'creating')

        self._wait_for_status(drive['uuid'], 'unmounted')

        with self.dump_response('drive_get_unmounted'):
            drive = self.client.get(drive['uuid'])

        # with self.dump_response('drive_resize'):
        #     drive_def['size'] = 1024000000 * 2
        #     resizing_drive = self.client.update(drive['uuid'], drive_def)
        #
        # self.assertEqual(resizing_drive['status'], 'resizing')
        # self._wait_for_status(resizing_drive['uuid'], 'unmounted')

        with self.dump_response('drive_delete'):
            self.client.delete(drive['uuid'])  # replace with resizing drive when you uncomment the upper

        self._wait_deleted(drive['uuid'])

    @attr('docs_snippets')
    def test_drive_listing(self):
        req = [
            {
                'name': 'test_drive_%i' % i,
                'size': '1024000000',
                'media': 'disk',
            } for i in range(5)
        ]

        with self.dump_response('drive_create_bulk'):
            drives = self.client.create(req)

        for drive in drives:
            self._wait_for_status(drive['uuid'], 'unmounted')

        #Get the short list of fields
        with self.dump_response('drive_list'):
            self.client.list()

        #Get just a list of uuids
        with self.dump_response('drive_list_just_uuid_and_status'):
            just_uuids = self.client.list(query_params={'fields':'uuid,status'})

        for el in just_uuids:
            self.assertEqual(set(el.keys()), set(['uuid', 'status']))

        #Get detailed information on drives
        with self.dump_response('drive_list_detail'):
            self.client.list_detail()

        for drive in drives:
            self.client.delete(drive['uuid'])

        for drive in drives:
            self._wait_deleted(drive['uuid'])

    @attr('docs_snippets')
    def test_drive_edit(self):
        drive_def = {
            'name': 'test_drive_x',
            'size': 1024000000,
            'media': 'disk',
        }

        drive = self.client.create(drive_def)
        self._wait_for_status(drive['uuid'], 'unmounted')

        drive_def['name'] = 'test_drive_y'
        drive_def['media'] = 'cdrom'

        with self.dump_response('drive_edit'):
            updated_drive = self.client.update(drive['uuid'], drive_def)

        self.assertDictContainsSubset(drive_def, updated_drive)

        self.client.delete(updated_drive['uuid'])
        self._wait_deleted(updated_drive['uuid'])

    @attr('docs_snippets')
    def test_drive_clone(self):
        drive_def = {
            'name': 'test_drive_x',
            'size': '1024000000',
            'media': 'disk',
        }

        drive = self.client.create(drive_def)
        self._wait_for_status(drive['uuid'], 'unmounted', timeout=self.TIMEOUT_DRIVE_CLONING)

        clone_drive_def = {
            'name': 'test_drive_y',
            'media': 'cdrom',
            'affinities': [],
        }

        with self.dump_response('drive_clone'):
            cloned_drive = self.client.clone(drive['uuid'], clone_drive_def)

        self._wait_for_status(cloned_drive['uuid'], 'unmounted', timeout=self.TIMEOUT_DRIVE_CLONING)

        self.client.delete(drive['uuid'])
        self.client.delete(cloned_drive['uuid'])

        self._wait_deleted(cloned_drive['uuid'], timeout=60)
        self._wait_deleted(drive['uuid'], timeout=60)

    @attr('docs_snippets')
    def test_get_schema(self):
        with self.dump_response('drive_schema'):
            self.client.get_schema()

@attr('acceptance_test')
class LibraryDriveTest(StatefulResourceTestBase):

    def _gen_server_definition(self, drives=[], changed_def={}):
        drive_tmp = {
            "device": "virtio",
            "dev_channel": "0:0",
            "drive": None,
            "boot_order": 1
        }

        server_def = {
            'name': 'testServerAcc',
            'cpu': 1000,
            'mem': 512 * 1024 ** 2,
            'vnc_password': 'testserver',
            'drives': [],
        }

        server_def.update(changed_def)
        for drive in drives:
            if isinstance(drive, dict):
                drive = server_def['drives'].append(drive)
            elif isinstance(drive, basestring):
                guest_drive = drive_tmp.copy()
                guest_drive['drive'] = drive
                drive = guest_drive
            else:
                drive = None

            if drive is not None:
                server_def['drives'].append(drive)

        return server_def

    def setUp(self):
        super(LibraryDriveTest, self).setUp()
        self.client = cr.LibDrive()
        self.dump_response = DumpResponse(clients=[self.client])

    @attr('docs_snippets')
    def test_get_schema(self):
        with self.dump_response('libdrive_schema'):
            self.client.get_schema()

    @attr('docs_snippets')
    def test_libdrive_listing(self):
        with self.dump_response('libdrive_list'):
            libdrives = self.client.list(query_params={'limit': 5})

        # Select the lib drive with most interesting attributes
        libdrive_uuid = libdrives[0]['uuid']            # by default use the first possible
        for d in libdrives:
            if len(d['licenses']) > 0:                  # pick a drive with licenses
                libdrive_uuid = d['uuid']
                break

        with self.dump_response('libdrive_get'):
            libdrive = self.client.get(libdrive_uuid)

    def test_attaching_cdrom(self):

        server_client = cr.Server()

        found = None
        for drive in self.client.list():
            if drive['media'] == 'cdrom':
                found = drive
                break

        if found is None:
            raise unittest.SkipTest('Cannot find a cdrom drive in drives library')

        guest_def = self._gen_server_definition(drives=[found['uuid']])
        new_guest = server_client.create(guest_def)

        server_client.delete(new_guest['uuid'])
        self._wait_deleted(new_guest['uuid'], client=server_client)

    def test_attaching_preinstalled(self):
        server_client = cr.Server()

        found = None
        for drive in self.client.list():
            if drive['media'] == 'disk':
                found = drive
                break

        if found is None:
            raise unittest.SkipTest('Cannot find a preinstalled drive in the drives library')

        guest_def = self._gen_server_definition(drives=[found['uuid']])

        with self.assertRaises(errors.PermissionError):
            server_client.create(guest_def)


@attr('stress_test')
class DriveStressTest(StatefulResourceTestBase):
    CLONE_COUNT = 20
    DRIVE_COUNT = 100

    def setUp(self):
        super(DriveStressTest, self).setUp()
        self.client = cr.Drive()

    def _get_min_drive_size(self):
        return 1*1000**3

    def test_create_delete(self):
        """Creating MANY small drives via API, see if it works"""

        min_size = self._get_min_drive_size()
        defin_list = [
            {
                "name": "test_drive_{}".format(num),
                "size": min_size,
                "media": "disk",
            } for num in range(self.DRIVE_COUNT)
        ]
        res = []

        for drive_def in defin_list:
            res.append(self.client.create(drive_def))

        for creating_drive in res:
            self._wait_for_status(creating_drive['uuid'], status='unmounted', client=self.client, timeout=60)

        for drive in res:
            self.client.delete(drive['uuid'])

        for deleted_drive in res:
            self._wait_deleted(deleted_drive['uuid'], self.client, timeout=60)

    def test_clone(self):
        """Clone SOME drives via API, see if it works"""
        puuid, ppass = self._get_persistent_image_uuid_and_pass()

        cloned = []
        for num in range(self.CLONE_COUNT):
            cloned.append(self.client.clone(puuid, {'name': "test_atom_clone_{}".format(num)}))

        for cloning_drive in cloned:
            self._wait_for_status(cloning_drive['uuid'], status='unmounted', client=self.client, timeout=self.TIMEOUT_DRIVE_CLONING)

        for drive in cloned:
            self.client.delete(drive['uuid'])

        for deleted_drive in cloned:
            self._wait_deleted(deleted_drive['uuid'], self.client, timeout=60)
