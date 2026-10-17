"""Finite Server.list pagination contract; no traversal or server execution claim.

Public pagination.html defines zero-based offset, maximum limit, and limit=0
as all resources. The synthetic five-object collection below supplies a stable
oracle, not a claim that the service orders or snapshots changing collections.
"""
import copy
import unittest

import requests
from cloudsigma.resource import Server
from test_network_reads import FixtureAdapter


class ServerPaginationTests(unittest.TestCase):
    def check_page(self, params, query, indices):
        objects = [{'uuid': 'synthetic-server-%d' % i} for i in indices]
        payload = {'meta': {'limit': (params or {}).get('limit', 0),
                            'offset': (params or {}).get('offset', 0),
                            'total_count': 5}, 'objects': objects}
        before = copy.deepcopy(params)
        adapter = FixtureAdapter(self,
            'https://fixture.invalid/api/2.0/servers/?' + query, payload, 200, None)
        with requests.Session() as session:
            session.trust_env = False
            session.mount('https://', adapter)
            obj = Server(api_endpoint='https://fixture.invalid/api/2.0/',
                         username='fixture', password='synthetic', session=session)
            result = obj.list(params)
            self.assertIs(type(result), list)
            self.assertEqual(result, objects)
            self.assertEqual([item['uuid'] for item in result],
                             ['synthetic-server-%d' % i for i in indices])
            self.assertIs(obj.c.resp, adapter.response)
            # A partial/empty page never triggers implicit traversal.
            self.assertEqual(adapter.calls, 1)
            self.assertEqual(params, before)

    def test_default_and_explicit_unlimited(self):
        for params in (None, {}, {'limit': 0}):
            with self.subTest(params=params):
                self.check_page(params, 'limit=0', [0, 1, 2, 3, 4])
        self.check_page({'limit': 0, 'offset': 2}, 'limit=0&offset=2', [2, 3, 4])

    def test_zero_based_finite_last_and_empty_pages(self):
        # Literal expectations are independent of the implementation, not
        # computed by slicing with the very parameters under test.
        cases = ((0, 2, [0, 1]), (2, 2, [2, 3]), (4, 2, [4]), (5, 2, []))
        for offset, limit, indices in cases:
            with self.subTest(offset=offset, limit=limit):
                self.check_page({'limit': limit, 'offset': offset},
                                'limit=2&offset=%d' % offset, indices)

    def test_offset_only_retains_unlimited_default(self):
        self.check_page({'offset': 0}, 'limit=0&offset=0', [0, 1, 2, 3, 4])
        self.check_page({'offset': 4}, 'limit=0&offset=4', [4])
