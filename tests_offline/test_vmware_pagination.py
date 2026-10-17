"""Explicit VMware pages preserve the existing complete/Decimal read contract."""
import copy
import unittest
from decimal import Decimal
from urllib.parse import urlencode

import requests
from cloudsigma.vmware_read import VMwareRead
from cloudsigma import errors

BASE = 'https://fixture.invalid/api/2.0/'


class Adapter(requests.adapters.BaseAdapter):
    def __init__(self, indices, status=200, failure=None):
        self.indices, self.status, self.failure = indices, status, failure
        self.seen = []

    def send(self, request, **kwargs):
        self.seen.append((request, kwargs))
        if self.failure:
            raise self.failure
        response = requests.Response()
        response.status_code = self.status
        objects = ','.join('{"id":"%s","name":"synthetic VMware server",'
                           '"numeric":9007199254740993.00001,"nullable":null}' % i
                           for i in self.indices)
        response._content = ('{"meta":{"total_count":5},"objects":[' +
                             objects + '],"extension":null}').encode('ascii')
        response.headers['X-REQUEST-ID'] = 'synthetic-vmware-page'
        response.request = request
        return response

    def close(self):
        pass


class VMwarePaginationTests(unittest.TestCase):
    def invoke(self, params, indices, omitted=False, status=200,
               failure=None, error=None):
        original = copy.deepcopy(params)
        adapter = Adapter(indices, status, failure)
        with requests.Session() as session:
            session.mount('https://', adapter)
            resource = VMwareRead(api_endpoint=BASE, username='fixture',
                                  password='synthetic', session=session)
            kwargs = {} if omitted else {'query_params': params}
            if error:
                with self.assertRaises(error) as caught:
                    resource.list(**kwargs)
                if failure:
                    self.assertIs(caught.exception, failure)
                else:
                    self.assertEqual(caught.exception.status_code, status)
                    self.assertEqual(caught.exception.request_id, 'synthetic-vmware-page')
            else:
                result = resource.list(**kwargs)
                self.assertEqual(result, {
                    'meta': {'total_count': 5}, 'extension': None,
                    'objects': [{'id': str(i), 'name': 'synthetic VMware server',
                                 'numeric': Decimal('9007199254740993.00001'),
                                 'nullable': None} for i in indices]})
                for obj in result['objects']:
                    self.assertIs(type(obj['numeric']), Decimal)
            self.assertEqual(params, original)
            self.assertEqual(len(adapter.seen), 1)
            request, options = adapter.seen[0]
            query = '?' + urlencode(params) if params else ''
            self.assertEqual(request.url, BASE + 'vmware_servers/' + query)
            self.assertEqual(request.method, 'GET')
            self.assertIn(request.body, (None, b'', ''))
            self.assertEqual(request.headers['Authorization'], 'Basic Zml4dHVyZTpzeW50aGV0aWM=')
            self.assertEqual(options['timeout'], 15)

    def test_explicit_pages(self):
        # Literal expected members: fixture ordering is not a server guarantee.
        for params, indices in [({'limit': 2, 'offset': 0}, [0, 1]),
                                ({'limit': 2, 'offset': 2}, [2, 3]),
                                ({'limit': 2, 'offset': 4}, [4]),
                                ({'limit': 2, 'offset': 5}, [])]:
            with self.subTest(params=params):
                self.invoke(params, indices)

    def test_unlimited_and_offset_only(self):
        self.invoke({'limit': 0}, [0, 1, 2, 3, 4])
        self.invoke({'offset': 4}, [4])

    def test_legacy_default(self):
        self.invoke(None, [0], omitted=True)

    def test_none_and_empty(self):
        self.invoke(None, [])
        self.invoke({}, [])

    def test_errors_without_traversal(self):
        for status, error in ((403, errors.PermissionError),
                              (404, errors.ClientError), (500, errors.ServerError),
                              (302, errors.ApiClientError)):
            with self.subTest(status=status):
                self.invoke({'limit': 2, 'offset': 4}, [], status=status, error=error)

    def test_transport_error_identity(self):
        failure = requests.exceptions.Timeout('synthetic VMware server page failure')
        self.invoke({'limit': 2}, [], failure=failure,
                    error=requests.exceptions.Timeout)
