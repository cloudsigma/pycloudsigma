"""Existing bulk clone selects the documented route; no real mutation/polling."""
import copy
import json
import unittest
from unittest.mock import patch

from cloudsigma.bulk import DrivesBulk
from cloudsigma.conf import config
from cloudsigma.errors import PermissionError
from test_bulk_library_lookup import LookupAdapter


class BulkCloneRouteTests(unittest.TestCase):
    def exercise(self, owner, library, count=1, failure=False, missing_owner=False):
        source = {'uuid': 'source', 'name': 'image', 'owner': owner,
                  'media': 'disk', 'size': 9007199254740993,
                  'meta': {'description': 'keep'}, 'affinities': []}
        if missing_owner:
            del source['owner']
        original = copy.deepcopy(source)
        clones = [dict(source, uuid='clone-%d' % i, name='fixture-%05d' % (i+1),
                       status='unmounted') for i in range(count)]
        responses = [(200, {'objects': [] if library else [source]})]
        if library:
            responses.append((200, {'objects': [source]}))
        if failure:
            responses.append((403, {'error_message': 'synthetic refusal'}))
        else:
            responses.extend((202, {'objects': [item]}) for item in clones)
            responses.append((200, {'objects': clones}))
        adapter = LookupAdapter(responses)
        with patch.dict(config, {'api_endpoint': 'https://fixture.invalid/api/2.0/',
                                 'username': 'fixture', 'password': 'synthetic',
                                 'login_method': 'basic'}, clear=True):
            bulk = DrivesBulk(id_prefix='fixture')
        self.addCleanup(bulk.c.http.close)
        for resource in (bulk.c_drive, bulk.c_libdrive, bulk.c_guest):
            self.addCleanup(resource.c.http.close)
            resource.c.http.mount('https://', adapter)
        with patch('cloudsigma.bulk.time.sleep', side_effect=AssertionError('unexpected wait')):
            if failure:
                with self.assertRaises(PermissionError) as caught:
                    bulk.clone(count, 'source')
                self.assertEqual(caught.exception.status_code, 403)
                self.assertEqual(caught.exception.request_id, 'lookup-fixture')
            else:
                self.assertEqual(bulk.clone(count, 'source'), clones)
        prefix = 'https://fixture.invalid/api/2.0/'
        expected = [('GET', prefix+'drives/detail/?limit=0')]
        if library:
            expected.append(('GET', prefix+'libdrives/detail/?limit=0'))
        route = 'libdrives' if owner is None and not missing_owner else 'drives'
        expected.extend(('POST', prefix+route+'/source/action/?do=clone')
                        for _ in range(1 if failure else count))
        if not failure:
            expected.append(('GET', prefix+'drives/detail/?limit=0'))
        self.assertEqual([(r.method, r.url) for r in adapter.requests], expected)
        posts = [r for r in adapter.requests if r.method == 'POST']
        for i, request in enumerate(posts):
            self.assertEqual(json.loads(request.body),
                             {'media': 'disk', 'name': 'fixture-%05d' % (i+1),
                              'size': 9007199254740993,
                              'meta': {'description': 'keep'}, 'affinities': []})
        self.assertTrue(all(r.body is None for r in adapter.requests if r.method == 'GET'))
        self.assertEqual(adapter.responses, [])
        self.assertEqual(source, original)

    def test_library_clone_uses_library_action(self):
        self.exercise(None, True)

    def test_multiple_library_clones_keep_route_and_names(self):
        self.exercise(None, True, count=2)

    def test_owned_clone_preserves_drive_action(self):
        self.exercise({'uuid': 'account'}, False)

    def test_absent_owner_preserves_legacy_drive_action(self):
        self.exercise(None, False, missing_owner=True)

    def test_library_clone_error_stops_before_poll(self):
        self.exercise(None, True, failure=True)

    def test_zero_count_does_not_dispatch_clone(self):
        self.exercise(None, True, count=0)
