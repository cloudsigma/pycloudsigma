"""Explicit tagged-resource pages; no implicit traversal or ordering guarantee."""
import copy
import json
import unittest
from urllib.parse import urlencode

import requests
from cloudsigma.resource import Tags
from cloudsigma import errors

UUID = '7b102579-e850-47cf-adf9-9c1a499b08f8'
BASE = 'https://fixture.invalid/api/2.0/'


class Adapter(requests.adapters.BaseAdapter):
    def __init__(self, payload, status=200, failure=None):
        self.payload, self.status, self.failure = payload, status, failure
        self.seen = []

    def send(self, request, **kwargs):
        self.seen.append((request, kwargs))
        if self.failure:
            raise self.failure
        response = requests.Response()
        response.status_code = self.status
        response._content = json.dumps(self.payload).encode('utf-8')
        response.headers['X-REQUEST-ID'] = 'synthetic-tag-page'
        response.request = request
        return response

    def close(self):
        pass


class TagResourcePaginationTests(unittest.TestCase):
    def invoke(self, kind, params, indices, generic=False, omitted=False,
               status=200, failure=None, error=None):
        # Literal indices supplied by each case are independent of SDK paging.
        objects = [{'uuid': 'synthetic-%d' % i,
                    'nested': {'number': 9007199254740993, 'value': None}}
                   for i in indices]
        payload = {'meta': {'limit': (params or {}).get('limit', 20),
                            'offset': (params or {}).get('offset', 0),
                            'total_count': 5}, 'objects': objects}
        original = copy.deepcopy(params)
        adapter = Adapter(payload, status, failure)
        with requests.Session() as session:
            session.mount('https://', adapter)
            resource = Tags(api_endpoint=BASE, username='fixture',
                            password='synthetic', session=session)
            method = resource.list_resource if generic else getattr(resource, kind)
            args = (UUID, kind) if generic else (UUID,)
            kwargs = {} if omitted else {'query_params': params}
            if error:
                with self.assertRaises(error) as caught:
                    method(*args, **kwargs)
                if failure:
                    self.assertIs(caught.exception, failure)
                else:
                    self.assertEqual(caught.exception.status_code, status)
                    self.assertEqual(caught.exception.request_id, 'synthetic-tag-page')
            else:
                result = method(*args, **kwargs)
                self.assertIs(type(result), list)
                self.assertEqual(result, objects)
            self.assertEqual(params, original)
            self.assertEqual(len(adapter.seen), 1)
            request, options = adapter.seen[0]
            query = '?' + urlencode(params) if params else ''
            self.assertEqual(request.url, BASE + 'tags/' + UUID + '/' + kind + '/' + query)
            self.assertEqual(request.method, 'GET')
            self.assertIn(request.body, (None, b'', ''))
            self.assertIn('Authorization', request.headers)
            self.assertEqual(options['timeout'], 15)

    def test_generic_explicit_pages(self):
        for params, indices in [({'limit': 2, 'offset': 0}, [0, 1]),
                                ({'limit': 2, 'offset': 2}, [2, 3]),
                                ({'limit': 2, 'offset': 4}, [4]),
                                ({'limit': 2, 'offset': 5}, [])]:
            with self.subTest(params=params):
                self.invoke('servers', params, indices, generic=True)

    def test_four_convenience_methods_forward_pages(self):
        for kind in ('servers', 'drives', 'ips', 'vlans'):
            with self.subTest(kind=kind):
                self.invoke(kind, {'limit': 2, 'offset': 4}, [4])

    def test_unlimited_and_offset_only(self):
        for kind in ('servers', 'drives', 'ips', 'vlans'):
            with self.subTest(kind=kind):
                self.invoke(kind, {'limit': 0}, [0, 1, 2, 3, 4])
                self.invoke(kind, {'offset': 4}, [4])

    def test_legacy_default_has_no_query(self):
        for generic in (False, True):
            for kind in ('servers', 'drives', 'ips', 'vlans'):
                self.invoke(kind, None, [0], generic=generic, omitted=True)

    def test_explicit_none_and_empty_have_no_query(self):
        for params in (None, {}):
            self.invoke('servers', params, [], generic=True)
            self.invoke('servers', params, [])

    def test_errors_and_transport_do_not_traverse(self):
        for status, error in ((403, errors.PermissionError),
                              (404, errors.ClientError), (500, errors.ServerError),
                              (302, errors.ApiClientError)):
            self.invoke('servers', {'limit': 2, 'offset': 4}, [],
                        status=status, error=error)
        failure = requests.exceptions.Timeout('synthetic page failure')
        self.invoke('servers', {'limit': 2}, [], failure=failure,
                    error=requests.exceptions.Timeout)
