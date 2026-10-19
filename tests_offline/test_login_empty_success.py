"""Public accounts login: 200 with empty body; native Requests cookie handling."""
import json
from email.message import Message
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import requests
from requests.adapters import BaseAdapter
from requests.cookies import extract_cookies_to_jar
from cloudsigma import generic as g, errors


class Adapter(BaseAdapter):
    def __init__(self, status=200, body=b'', cookies=True):
        self.status, self.body, self.cookies = status, body, cookies
        self.calls = []
        self.closed = False

    def send(self, request, **kwargs):
        self.calls.append((request, kwargs))
        r = requests.Response()
        r.request, r.url = request, request.url
        r.status_code, r._content = self.status, self.body
        r.headers['X-REQUEST-ID'] = 'synthetic-request'
        message = Message()
        if self.cookies:
            for value in ('csrftoken=synthetic-csrf; Path=/; Secure',
                          'sessionid=synthetic-session; Path=/; Secure; HttpOnly'):
                message.add_header('Set-Cookie', value)
        # Supply HTTPAdapter's raw cookie interface, not a pre-populated jar.
        r.raw = SimpleNamespace(_original_response=SimpleNamespace(msg=message))
        extract_cookies_to_jar(r.cookies, request, r.raw)
        return r

    def close(self):
        self.closed = True


class LoginEmptySuccess(unittest.TestCase):
    def setup_client(self, status=200, body=b'', cookies=True):
        s = requests.Session()
        a = Adapter(status, body, cookies)
        s.mount('https://', a)
        self.addCleanup(s.close)
        c = g.GenericClient('https://example.invalid/api/2.0/', 'user', 'password',
                            'none', session=s)
        return c, s, a

    def test_documented_empty_200_and_cookie_followup(self):
        c, s, a = self.setup_client()
        with patch.object(c, '_session_otp', return_value='123456') as otp:
            c.secret = 'synthetic'
            c._login_session()
            otp.assert_called_once_with()
        self.assertIs(c.http, s)
        self.assertFalse(a.closed)
        req, opts = a.calls[0]
        self.assertEqual(req.url, 'https://example.invalid/api/2.0/accounts/action/?do=login')
        self.assertEqual(req.method, 'POST')
        self.assertEqual(json.loads(req.body), {'username': 'user', 'password': 'password'})
        self.assertEqual(req.headers['OTP'], '123456')
        self.assertFalse(opts.get('allow_redirects', False))
        self.assertEqual(s.cookies.get('sessionid'), 'synthetic-session')
        self.assertEqual(s.headers['X-CSRFToken'], 'synthetic-csrf')
        a.body = b'{}'
        with patch.object(c, '_session_otp', side_effect=AssertionError('no regeneration')):
            c.get('tags/')
        req = a.calls[-1][0]
        self.assertIn('sessionid=synthetic-session', req.headers['Cookie'])
        self.assertEqual(req.headers['X-CSRFToken'], 'synthetic-csrf')
        self.assertNotIn('OTP', req.headers)
        self.assertEqual(len(a.calls), 2)

    def test_constructor_empty_success(self):
        _, s, a = self.setup_client()
        c = g.GenericClient('https://example.invalid/api/2.0/', 'user', 'password',
                            'session', session=s)
        self.assertIs(c.http, s)
        self.assertEqual(len(a.calls), 1)

    def test_legacy_json_success(self):
        c, s, a = self.setup_client(body=b'{}')
        c._login_session()
        self.assertEqual(s.headers['X-CSRFToken'], 'synthetic-csrf')
        self.assertEqual(len(a.calls), 1)

    def test_empty_success_requires_csrf_cookie(self):
        c, s, a = self.setup_client(cookies=False)
        with self.assertRaises(KeyError):
            c._login_session()
        self.assertNotIn('X-CSRFToken', s.headers)
        self.assertFalse(a.closed)

    def test_errors_and_redirect_do_not_establish_readiness(self):
        for status, error in ((401, errors.AuthError), (403, errors.PermissionError),
                              (500, errors.ServerError), (302, errors.ApiClientError)):
            with self.subTest(status=status):
                c, s, a = self.setup_client(status=status)
                with self.assertRaises(error):
                    c._login_session()
                self.assertNotIn('X-CSRFToken', s.headers)
                self.assertEqual(len(a.calls), 1)
                self.assertFalse(a.closed)

    def test_nonempty_malformed_login_is_not_ignored(self):
        for body in (b' ', b'not-json'):
            c, s, a = self.setup_client(body=body)
            with self.assertRaises(ValueError):
                c._login_session()
            self.assertNotIn('X-CSRFToken', s.headers)

    def test_other_json_operations_still_reject_empty_body(self):
        for method in ('get', 'get_raw', 'post', 'put'):
            c, _, a = self.setup_client()
            args = ('tags/', {}) if method in ('post', 'put') else ('tags/',)
            with self.assertRaises(ValueError):
                getattr(c, method)(*args)
            self.assertEqual(len(a.calls), 1)

    def test_other_json_success_statuses_not_newly_exempted(self):
        for status in (201, 202):
            c, s, a = self.setup_client(status=status)
            with self.assertRaises(ValueError):
                c._login_session()
            self.assertNotIn('X-CSRFToken', s.headers)
