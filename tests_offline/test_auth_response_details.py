"""Additive 401 API; legacy diagnostics are deliberately unchanged."""
import unittest
from unittest.mock import patch
import requests
from requests.adapters import BaseAdapter
from cloudsigma import errors
from cloudsigma.resource import Balance

BODIES = ('[{"error_message":"denied","error_point":null,"error_type":"permission"}]',
          '{"error_message":"denied","error_point":"currency","error_type":"permission"}',
          'plain text', '', '{invalid JSON', '拒否 — café ☃', 'null')

class Adapter(BaseAdapter):
    def __init__(self, body, status, request_id):
        self.body, self.status, self.request_id = body, status, request_id
        self.calls = []

    def send(self, request, **kwargs):
        self.calls.append(request)
        response = requests.Response()
        response.status_code = self.status
        response.encoding = 'utf-8'
        response._content = self.body.encode('utf-8')
        response.request = request
        if self.request_id is not None:
            response.headers['x-request-id'] = self.request_id
        response.headers['Authorization'] = 'synthetic-response-secret'
        response.headers['Set-Cookie'] = 'synthetic-cookie-secret'
        return response

    def close(self):
        pass

class AuthResponseDetailsTests(unittest.TestCase):
    def invoke(self, body, status, request_id):
        obj = Balance(api_endpoint='https://next.cloudsigma.com/api/2.0/',
                      username='synthetic', password='synthetic')
        session = requests.Session()
        session.trust_env = False
        adapter = Adapter(body, status, request_id)
        session.mount('https://', adapter)
        obj.c._session = session
        self.addCleanup(session.close)
        with self.assertRaises(errors.ApiClientError) as caught:
            obj.get()
        self.assertEqual(len(adapter.calls), 1)
        self.assertEqual(adapter.calls[0].method, 'GET')
        self.assertEqual(adapter.calls[0].url, 'https://next.cloudsigma.com/api/2.0/balance/')
        self.assertIsNone(adapter.calls[0].body)
        return caught.exception

    def test_additive_accessor_raw_body(self):
        # This exact test is also run against the pristine installed baseline.
        for body in BODIES:
            for request_id in (None, '', 'synthetic-request-id'):
                with self.subTest(body=body, request_id=request_id):
                    with patch.object(requests.Response, 'json', side_effect=AssertionError('no JSON parsing')):
                        exc = self.invoke(body, 401, request_id)
                    self.assertEqual(exc.response_body, body)
                    self.assertEqual(exc.response_request_id, request_id)

    def test_legacy_401_compatibility(self):
        for body in BODIES:
            for request_id in (None, '', 'synthetic-request-id'):
                exc = self.invoke(body, 401, request_id)
                expected = errors.AuthError(request_id, status_code=401)
                self.assertIs(type(exc), errors.AuthError)
                self.assertEqual(exc.message, expected.message)
                self.assertEqual(exc.args, (request_id, 401, ''))
                self.assertEqual(exc.status_code, 401)
                self.assertEqual(exc.request_id, '')
                self.assertEqual(str(exc), str(expected))
                self.assertEqual(repr(exc), repr(expected))

    def test_non401_unchanged(self):
        for status in (301, 302, 307, 308, 400, 402, 403, 404, 405, 406, 500, 503):
            for request_id in (None, 'synthetic-request-id'):
                for body in BODIES:
                    exc = self.invoke(body, status, request_id)
                    cls = (errors.ApiClientError if status < 400 else
                           errors.PermissionError if status == 403 else
                           errors.ClientError if status < 500 else errors.ServerError)
                    message = 'redirect refused' if status < 400 else body
                    self.assertIs(type(exc), cls)
                    self.assertEqual(vars(exc), dict(message=message, status_code=status, request_id=request_id))
                    self.assertEqual(exc.args, (message, status, request_id))

    def test_no_header_dump_or_manual_constructor_change(self):
        exc = self.invoke('synthetic body', 401, 'synthetic-request-id')
        self.assertEqual(set(vars(exc)), {'message', 'status_code', 'request_id',
                                         'response_body', 'response_request_id'})
        self.assertNotIn('synthetic-response-secret', repr(vars(exc)))
        self.assertNotIn('synthetic-cookie-secret', repr(vars(exc)))
        manual = errors.AuthError('manual', status_code=401, request_id='manual-id')
        self.assertEqual(vars(manual), dict(message='manual', status_code=401, request_id='manual-id'))
        self.assertEqual(manual.args, ('manual', 401, 'manual-id'))

    def test_shared_decoder_and_session_login_no_retry_or_body_log(self):
        from cloudsigma.generic import GenericClient
        for method in ('get', 'get_raw', 'post', 'put', 'delete', 'login'):
            session = requests.Session()
            adapter = Adapter('synthetic-sensitive-body', 401, 'synthetic-request-id')
            session.mount('https://', adapter)
            self.addCleanup(session.close)
            kwargs = dict(api_endpoint='https://next.cloudsigma.com/api/2.0/',
                          username='synthetic', password='synthetic', session=session,
                          request_log_level='DEBUG')
            with self.assertLogs('cloudsigma.generic', level='DEBUG') as logs:
                with self.assertRaises(errors.AuthError) as caught:
                    if method == 'login':
                        GenericClient(login_method='session', **kwargs)
                    else:
                        client = GenericClient(**kwargs)
                        args = ('balance/', {}) if method in ('post', 'put') else ('balance/',)
                        getattr(client, method)(*args)
            exc = caught.exception
            self.assertEqual(exc.response_body, 'synthetic-sensitive-body')
            self.assertEqual(exc.response_request_id, 'synthetic-request-id')
            self.assertEqual(exc.args, ('synthetic-request-id', 401, ''))
            self.assertEqual(len(adapter.calls), 1)
            self.assertEqual(adapter.calls[0].method, 'POST' if method == 'login' else
                             'GET' if method == 'get_raw' else method.upper())
            self.assertEqual(adapter.calls[0].url,
                             'https://next.cloudsigma.com/api/2.0/accounts/action/?do=login'
                             if method == 'login' else 'https://next.cloudsigma.com/api/2.0/balance/')
            self.assertEqual(logs.output, ['DEBUG:cloudsigma.generic:HTTP response status=401'])
