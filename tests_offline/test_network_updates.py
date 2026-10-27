"""Public IP/VLAN metadata PUT contract at the real Requests adapter boundary.

Synthetic only: preservation of replacement payload is not server-side deletion
or writable-field validation. Existing CRUD tests cover empty metadata via fake
sessions, not these prepared populated/omitted requests and typed failures.
"""
import copy
import json
from unittest import TestCase
import requests
from cloudsigma import resource, errors
from test_network_reads import NetworkReadTests, fixture


class UpdateAdapter(requests.adapters.BaseAdapter):
    def __init__(self, case, url, body, payload, status, exception):
        self.case, self.url, self.body = case, url, body
        self.payload, self.status, self.exception = payload, status, exception
        self.calls = 0

    def send(self, request, **kwargs):
        self.calls += 1
        c = self.case
        c.assertEqual(request.method, 'PUT')
        c.assertEqual(request.url, self.url)
        c.assert_json_exact(json.loads(request.body), self.body)
        c.assertEqual(request.headers['Content-Type'], 'application/json')
        c.assertEqual(request.headers['Authorization'], 'Basic Zml4dHVyZTpzeW50aGV0aWM=')
        c.assertEqual(kwargs['timeout'], 15)
        c.assertIs(kwargs['verify'], True)
        c.assertEqual(kwargs['proxies'], {})
        if self.exception:
            raise self.exception
        res = requests.Response()
        res.status_code = self.status
        res.request, res.url = request, request.url
        res.headers['X-REQUEST-ID'] = 'update-fixture'
        if 300 <= self.status < 400:
            res.headers['Location'] = 'https://elsewhere.invalid/forbidden/'
        res._content = self.payload if isinstance(self.payload, bytes) else json.dumps(self.payload).encode()
        self.response = res
        return res

    def close(self):
        pass


class NetworkUpdateTests(TestCase):
    assert_json_exact = NetworkReadTests.assert_json_exact

    def update(self, kind, body, payload, status=200, exception=None):
        cls = resource.IP if kind == 'ip' else resource.VLAN
        uid = fixture(kind, 'single')['uuid']
        path = 'ips' if kind == 'ip' else 'vlans'
        before = copy.deepcopy(body)
        adapter = UpdateAdapter(self, 'https://fixture.invalid/api/2.0/%s/%s/' % (path, uid),
                                before, payload, status, exception)
        with requests.Session() as session:
            session.trust_env = False
            session.mount('https://', adapter)
            session.mount('http://', adapter)
            obj = cls(api_endpoint='https://fixture.invalid/api/2.0/',
                      username='fixture', password='synthetic', session=session)
            try:
                result = obj.update(uid, body)
                self.assertIs(obj.c.resp, adapter.response)
                return result
            finally:
                self.assertEqual(adapter.calls, 1)
                self.assert_json_exact(body, before)

    def test_metadata_presence_and_replacement_bytes(self):
        for kind in ('ip', 'vlan'):
            for body in ({}, {'meta': {}}, {'meta': {'name': 'synthetic', 'custom_field': 'данни',
                                                     'empty': '', 'k' * 32: 'boundary'}}):
                with self.subTest(kind=kind, body=body):
                    response = fixture(kind, 'single')
                    if 'meta' in body:
                        response['meta'] = copy.deepcopy(body['meta'])
                    self.assert_json_exact(self.update(kind, body, response), response)

    def test_typed_errors_and_refused_redirects(self):
        for kind in ('ip', 'vlan'):
            for status, error in ((401, errors.AuthError), (403, errors.PermissionError),
                                  (404, errors.ClientError), (429, errors.ClientError),
                                  (500, errors.ServerError),
                                  *((s, errors.ApiClientError) for s in (301, 302, 303, 307, 308))):
                with self.subTest(kind=kind, status=status), self.assertRaises(error) as caught:
                    self.update(kind, {'meta': {'name': 'synthetic'}}, b'synthetic failure', status)
                exc = caught.exception
                self.assertEqual(exc.status_code, status)
                if status == 401:
                    self.assertEqual(exc.response_body, 'synthetic failure')
                    self.assertEqual(exc.response_request_id, 'update-fixture')
                else:
                    self.assertEqual(exc.request_id, 'update-fixture')
                    self.assertEqual(exc.message, 'redirect refused' if 300 <= status < 400 else 'synthetic failure')

    def test_malformed_json_and_timeout_identity(self):
        for kind in ('ip', 'vlan'):
            with self.assertRaises(requests.exceptions.JSONDecodeError):
                self.update(kind, {'meta': {}}, b'{bad')
            sentinel = requests.Timeout('synthetic')
            with self.assertRaises(requests.Timeout) as caught:
                self.update(kind, {'meta': {}}, {}, exception=sentinel)
            self.assertIs(caught.exception, sentinel)
