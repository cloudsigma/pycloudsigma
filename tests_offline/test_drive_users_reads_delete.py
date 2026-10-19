"""Offline DriveUsers GET/list/raw/DELETE evidence, not server acceptance."""
import copy
import json
import unittest
from urllib.parse import parse_qs, urlsplit

import requests
from cloudsigma import errors
from cloudsigma.resource import DriveUsers

UUID = '9876be5b-db07-4bc3-99cb-00c7ff55ec19'
BASE = 'https://fixture.invalid/api/2.0/driveusers/'
ITEM = {'amount': 2, 'drive': {'uuid': UUID,
        'resource_uri': '/api/2.0/drives/' + UUID + '/'}}


class Adapter(requests.adapters.BaseAdapter):
    def __init__(self, payload, status=200, failure=None):
        self.payload, self.status, self.failure = payload, status, failure
        self.seen = []

    def send(self, request, **kwargs):
        self.seen.append((request, kwargs))
        if self.failure is not None:
            raise self.failure
        response = requests.Response()
        response.status_code = self.status
        response._content = (b'' if self.status == 204 else
                             json.dumps(self.payload).encode('utf-8'))
        response.headers['X-REQUEST-ID'] = 'fixture-request'
        if 300 <= self.status < 400:
            response.headers['Location'] = 'https://redirect.invalid/forbidden'
        response.request = request
        return response

    def close(self):
        pass


class DriveUsersReadsDeleteTests(unittest.TestCase):
    def client(self, payload, status=200, failure=None):
        session = requests.Session()
        self.addCleanup(session.close)
        adapter = Adapter(payload, status, failure)
        session.mount('https://', adapter)
        resource = DriveUsers(api_endpoint='https://fixture.invalid/api/2.0/',
                              username='fixture', password='synthetic',
                              session=session)
        self.assertEqual(adapter.seen, [])  # construction performs no login
        self.assertFalse(session.trust_env)
        return resource, adapter

    def request(self, adapter, method, path, query=None):
        self.assertEqual(len(adapter.seen), 1)
        request, options = adapter.seen[0]
        url = urlsplit(request.url)
        self.assertEqual(request.method, method)
        self.assertEqual(url.scheme + '://' + url.netloc + url.path, path)
        self.assertEqual(parse_qs(url.query), query or {})
        self.assertIn(request.body, (None, b'', ''))
        self.assertEqual(request.headers['Authorization'], 'Basic Zml4dHVyZTpzeW50aGV0aWM=')
        self.assertEqual(request.headers['Content-Type'], 'application/json')
        self.assertEqual(options['timeout'], 15)

    def test_list_default_empty_single_many(self):
        for items in ([], [ITEM], [ITEM, dict(ITEM, amount=4)]):
            with self.subTest(items=items):
                resource, adapter = self.client({'meta': {'total_count': len(items)}, 'objects': items})
                self.assertEqual(resource.list(), items)
                self.request(adapter, 'GET', BASE, {'limit': ['0']})

    def test_list_and_raw_explicit_page_boundary(self):
        for method in ('list', 'list_raw'):
            for offset, items in ((0, [ITEM]), (1, [])):
                with self.subTest(method=method, offset=offset):
                    payload = {'meta': {'limit': 1, 'offset': offset, 'total_count': 1,
                               'next': '/api/2.0/driveusers/?offset=2'},
                               'objects': items, 'extension': {'preserve': False}}
                    resource, adapter = self.client(payload)
                    query = {'limit': 1, 'offset': offset, 'synthetic': 'a b'}
                    before = copy.deepcopy(query)
                    result = getattr(resource, method)(query)
                    self.assertEqual(result, payload if method == 'list_raw' else items)
                    self.assertEqual(query, before)
                    self.request(adapter, 'GET', BASE,
                                 {'limit': ['1'], 'offset': [str(offset)], 'synthetic': ['a b']})
                    # One send even with a next link: explicit pages, no traversal.

    def test_raw_default_preserves_envelope(self):
        payload = {'meta': {'limit': 0, 'offset': 0, 'total_count': 1}, 'objects': [ITEM]}
        resource, adapter = self.client(payload)
        self.assertEqual(resource.list_raw(), payload)
        self.request(adapter, 'GET', BASE, {'limit': ['0']})

    def test_singleton_public_direct_and_legacy_envelope(self):
        for payload in (ITEM, {'objects': [ITEM]}):
            with self.subTest(payload=payload):
                resource, adapter = self.client(payload)
                self.assertEqual(resource.get(UUID), ITEM)
                self.request(adapter, 'GET', BASE + UUID + '/')

    def test_delete_204_and_optional_query(self):
        for query in (None, {'synthetic': 'a b'}):
            with self.subTest(query=query):
                resource, adapter = self.client(None, 204)
                before = copy.deepcopy(query)
                self.assertIsNone(resource.delete(UUID, query))
                self.assertEqual(query, before)
                self.request(adapter, 'DELETE', BASE + UUID + '/',
                             {'synthetic': ['a b']} if query else {})

    def invoke(self, resource, operation):
        return getattr(resource, operation)(UUID) if operation in ('get', 'delete') else getattr(resource, operation)()

    def test_supported_errors_every_entrypoint(self):
        for operation in ('list', 'list_raw', 'get', 'delete'):
            for status, cls in ((401, errors.AuthError), (403, errors.PermissionError),
                                (400, errors.ClientError), (404, errors.ClientError),
                                (429, errors.ClientError), (500, errors.ServerError)):
                with self.subTest(operation=operation, status=status):
                    payload = {'error': 'fixture refusal'}
                    resource, adapter = self.client(payload, status)
                    with self.assertRaises(cls) as caught:
                        self.invoke(resource, operation)
                    error = caught.exception
                    self.assertIs(type(error), cls)
                    self.assertEqual(error.status_code, status)
                    if status == 401:
                        self.assertEqual(error.message, 'fixture-request')
                        self.assertEqual(error.request_id, '')  # preserved legacy API
                        self.assertEqual(error.response_request_id, 'fixture-request')
                        self.assertEqual(json.loads(error.response_body), payload)
                    else:
                        self.assertEqual(error.request_id, 'fixture-request')
                        self.assertEqual(json.loads(error.message), payload)
                    self.request(adapter, 'DELETE' if operation == 'delete' else 'GET',
                                 BASE + UUID + '/' if operation in ('get', 'delete') else BASE,
                                 {'limit': ['0']} if operation in ('list', 'list_raw') else {})

    def test_redirects_refused_without_second_dispatch(self):
        for operation in ('list', 'list_raw', 'get', 'delete'):
            for status in (301, 302, 303, 307, 308):
                with self.subTest(operation=operation, status=status):
                    resource, adapter = self.client({}, status)
                    with self.assertRaises(errors.ApiClientError) as caught:
                        self.invoke(resource, operation)
                    self.assertEqual(caught.exception.message, 'redirect refused')
                    self.assertEqual(caught.exception.status_code, status)
                    self.assertEqual(caught.exception.request_id, 'fixture-request')
                    self.assertEqual(len(adapter.seen), 1)
                    self.assertEqual(urlsplit(adapter.seen[0][0].url).netloc, 'fixture.invalid')

    def test_timeout_identity_every_entrypoint(self):
        for operation in ('list', 'list_raw', 'get', 'delete'):
            with self.subTest(operation=operation):
                failure = requests.exceptions.Timeout('fixture timeout')
                resource, adapter = self.client({}, failure=failure)
                with self.assertRaises(requests.exceptions.Timeout) as caught:
                    self.invoke(resource, operation)
                self.assertIs(caught.exception, failure)
                self.assertEqual(len(adapter.seen), 1)
                self.assertEqual(adapter.seen[0][1]['timeout'], 15)
