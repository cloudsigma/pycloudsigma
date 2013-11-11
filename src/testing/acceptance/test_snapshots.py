from nose.plugins.attrib import attr
from testing.acceptance.common import StatefulResourceTestBase
from testing.utils import DumpResponse
from cloudsigma.errors import ClientError
import cloudsigma.resource as cr


@attr('acceptance_test')
class SnapshotsTest(StatefulResourceTestBase):
    def setUp(self):
        super(SnapshotsTest, self).setUp()
        self.snap_client = cr.Snapshot()
        self.drive_client = cr.Drive()
        self.dump_response = DumpResponse(clients=[self.snap_client, self.drive_client])

    @attr('docs_snippets')
    def test_get_snapshot_schema(self):
        with self.dump_response("snapshot_schema"):
            self.snap_client.get_schema()

    @attr('docs_snippets')
    def test_snapshot_cycle(self):
        drive_def = {
            'name': 'test_drive_snapshot',
            'size': 1024000000,
            'media': 'disk',
        }

        with self.dump_response('drive_for_snapshots'):
            d = self.drive_client.create(drive_def)
        drive_uuid = d['uuid']

        self._wait_for_status(drive_uuid, client=self.drive_client, status='unmounted')
        self.assertFalse(d['snapshots'])

        snap_def = {
            'drive': drive_uuid,
            'name': 'first_snapshot',
            'meta': {'key': 'val'}
        }

        with self.dump_response('snapshot_create'):
            snap = self.snap_client.create(snap_def)
        snap_uuid = snap['uuid']

        self._wait_for_status(snap_uuid, 'available', client=self.snap_client)
        self.assertEqual(snap['drive']['uuid'], drive_uuid)

        with self.dump_response('drive_with_one_snapshot'):
            d = self.drive_client.get(drive_uuid)

        self.assertEqual(snap_uuid, d['snapshots'][0]['uuid'])

        another_snap_def = {'drive': drive_uuid}
        with self.dump_response('snapshot_create_another'):
            another_snap = self.snap_client.create(another_snap_def)
        another_snap_uuid = another_snap['uuid']
        self._wait_for_status(another_snap_uuid, 'available', client=self.snap_client)
        another_snap['name'] = 'another_snap'
        self.snap_client.update(another_snap_uuid, another_snap)

        another_snap = self.snap_client.get(another_snap_uuid)

        self.assertEqual('another_snap', another_snap['name'])

        with self.dump_response('drive_with_two_snapshots'):
            d = self.drive_client.get(drive_uuid)

        self.assertItemsEqual([snap_uuid, another_snap_uuid], [s['uuid'] for s in d['snapshots']])

        with self.dump_response('snapshot_delete'):
            self.snap_client.delete(snap_uuid)

        self._wait_deleted(snap_uuid, client=self.snap_client)
        with self.assertRaises(ClientError) as cm:
            self.snap_client.get(snap_uuid)
        self.assertEqual(cm.exception[0], 404)

        d = self.drive_client.get(drive_uuid)
        self.assertEqual(another_snap_uuid, d['snapshots'][0]['uuid'])

        self.drive_client.delete(drive_uuid)

        self._wait_deleted(drive_uuid, client=self.drive_client)

        with self.assertRaises(ClientError) as cm:
            self.snap_client.get(another_snap_uuid)
        self.assertEqual(cm.exception[0], 404)

    @attr('docs_snippets')
    def test_snapshot_listing(self):

        drive_def = {
            'name': 'test_drive_snapshot',
            'size': 1024000000,
            'media': 'disk',
        }

        # Create 3 drives
        drive_uuids = []
        for _ in xrange(3):
            d = self.drive_client.create(drive_def)
            drive_uuids.append(d['uuid'])

        for d_uuid in drive_uuids:
            self._wait_for_status(d_uuid, 'unmounted', client=self.drive_client)

        self.assertFalse(self.drive_client.get(drive_uuids[0])['snapshots'])

        # Create two snapshots for each drive
        snap_uuids = []
        for d_uuid in drive_uuids:
            snap_uuid1 = self.snap_client.create({'drive': d_uuid})['uuid']
            snap_uuid2 = self.snap_client.create({'drive': d_uuid})['uuid']
            snap_uuids.extend([snap_uuid1, snap_uuid2])

        with self.dump_response("snapshot_get"):
            self.snap_client.get(snap_uuid1)

        with self.dump_response('snapshot_list'):
            self.snap_client.list()
        with self.dump_response('snapshot_list_detail'):
            snap_list = self.snap_client.list_detail()

        self.assertLessEqual(6, len(snap_list))
        self.assertTrue(set(snap_uuids).issubset([s['uuid'] for s in snap_list]))

        with self.dump_response('snapshot_list_for_drive'):
            drive_snapshots = self.snap_client.list_detail(query_params={'drive': drive_uuids[0]})

        self.assertEqual(len(drive_snapshots), 2)
        with self.dump_response('snapshots_in_drive_def'):
            snapshots_from_drive_def = self.drive_client.get(drive_uuids[0])['snapshots']

        self.assertItemsEqual([s['uuid'] for s in drive_snapshots], [s['uuid'] for s in snapshots_from_drive_def])

        for d_uuid in drive_uuids:
            self.drive_client.delete(d_uuid)

        self._wait_deleted(drive_uuids[0], client=self.drive_client)
        self.assertFalse(self.snap_client.list_detail(query_params={'drive': drive_uuids[0]}))

    @attr('docs_snippets')
    def test_snapshot_clone(self):
        drive_def = {
            'name': 'test_drive_snapshot',
            'size': 1024000000,
            'media': 'disk',
        }

        with self.dump_response('drive_for_clone_snapshot'):
            d = self.drive_client.create(drive_def)
        drive_uuid = d['uuid']

        self._wait_for_status(drive_uuid, client=self.drive_client, status='unmounted')
        snap = self.snap_client.create({'drive': drive_uuid})
        snap_uuid = snap['uuid']
        self._wait_for_status(snap_uuid, client=self.snap_client, status='available')

        with self.dump_response('snapshot_clone'):
            cloned_drive = self.snap_client.clone(snap_uuid, avoid=drive_uuid)

        self.assertEqual(snap['name'], cloned_drive['name'])
        self.assertEqual(d['media'], cloned_drive['media'])
        self.assertEqual(d['size'], cloned_drive['size'])

        self._wait_for_status(cloned_drive['uuid'], 'unmounted', client=self.drive_client)
        self.drive_client.delete(cloned_drive['uuid'])
        self._wait_deleted(cloned_drive['uuid'], client=self.drive_client)

        clone_data = {'media': 'cdrom', 'name': 'test_drive_snapshot_clone_name'}

        cloned_drive = self.snap_client.clone(snap_uuid, data=clone_data, avoid=drive_uuid)

        self.assertEqual(clone_data['name'], cloned_drive['name'])
        self.assertEqual(clone_data['media'], cloned_drive['media'])
        self.assertEqual(d['size'], cloned_drive['size'])

        self._wait_for_status(cloned_drive['uuid'], 'unmounted', client=self.drive_client)
        self.drive_client.delete(cloned_drive['uuid'])
