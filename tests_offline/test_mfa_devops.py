"""Synthetic owner-relayed DevOps contract; public documentation pending."""
import json
import unittest
import traceback
from unittest.mock import patch
import requests
from requests.adapters import BaseAdapter
from cloudsigma import generic as g, errors

SECRET = 'GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ'  # RFC4226 public test key

class Adapter(BaseAdapter):
    def __init__(self, statuses=(200,)):
        self.calls = []
        self.statuses = list(statuses)
    def send(self, request, **kwargs):
        self.calls.append((request, kwargs))
        r = requests.Response()
        r.request = request
        r.status_code = self.statuses.pop(0) if self.statuses else 200
        r._content = b'' if r.status_code == 401 else b'{}'
        r.headers['WWW-Authenticate'] = 'OTP'
        r.cookies.set('csrftoken', 'synthetic-csrf')
        return r
    def close(self): pass

class MFA(unittest.TestCase):
    def client(self, method='none', statuses=(200,), **kw):
        s = requests.Session()
        a = Adapter(statuses)
        s.mount('https://', a)
        self.addCleanup(s.close)
        c = g.GenericClient('https://example.invalid/api/2.0/', 'synthetic-user',
                            'synthetic-password', method, session=s, **kw)
        return c, a
    def test_old_positional_and_absent_secret(self):
        with patch.dict(g.config, {}, clear=True):
            c, a = self.client()
            self.assertEqual(c.login_method, 'none')
            self.assertEqual(a.calls, [])
            for method in ('basic', 'digest', 'none'):
                c, a = self.client(method)
                self.assertNotIn('OTP', c._get_req_args()['headers'])
    def test_totp_fixed_rfc_vectors(self):
        c, _ = self.client(secret=SECRET)
        for instant, expected in ((59,'287082'), (1111111109,'081804'),
                                   (1111111111,'050471'), (1234567890,'005924'),
                                   (2000000000,'279037'), (20000000000,'353130')):
            with patch.object(g.time, 'time', return_value=instant):
                self.assertEqual(c._session_otp(), expected)
    def test_login_header_only_then_no_automatic_refresh(self):
        with patch.object(g.time, 'time', return_value=59):
            c, a = self.client('session', secret=SECRET)
        req, opts = a.calls[0]
        self.assertEqual(req.method, 'POST')
        self.assertEqual(json.loads(req.body), {'username':'synthetic-user','password':'synthetic-password'})
        self.assertEqual(req.headers['OTP'], '287082')
        self.assertFalse(opts['stream'])
        with patch.object(c, '_session_otp', side_effect=AssertionError('must not generate OTP')):
            for name in ('get', 'get_raw', 'post', 'put', 'delete'):
                args = ('tags/', {}) if name in ('post', 'put') else ('tags/',)
                getattr(c, name)(*args)
        for req, _ in a.calls[1:]:
            self.assertNotIn('OTP', req.headers)
            self.assertEqual(req.headers['X-CSRFToken'], 'synthetic-csrf')
        self.assertNotIn('OTP', c.http.headers)
    def test_explicit_otp_all_existing_http_verbs(self):
        c, a = self.client()
        for name in ('get','get_raw','post','put','delete'):
            args = ('tags/', {}) if name in ('post','put') else ('tags/',)
            getattr(c,name)(*args, otp='123456')
            self.assertEqual(a.calls[-1][0].headers['OTP'], '123456')
        self.assertEqual([r.method for r,_ in a.calls], ['GET','GET','POST','PUT','DELETE'])
        c.get('tags/')
        self.assertNotIn('OTP', a.calls[-1][0].headers)
    def test_empty_challenge_no_retry_or_downgrade(self):
        for name in ('get','get_raw','post','put','delete'):
            c, a = self.client('session', (200,401), secret=None)
            args = ('tags/', {}) if name in ('post','put') else ('tags/',)
            with self.assertRaises(errors.AuthError) as caught:
                getattr(c,name)(*args, otp='123456')
            self.assertEqual(caught.exception.status_code,401)
            self.assertEqual(caught.exception.response_body,'')
            self.assertEqual(len(a.calls),2)
            self.assertNotIn('Authorization',a.calls[-1][0].headers)
    def test_cookie_does_not_suppress_login_challenge(self):
        s=requests.Session(); self.addCleanup(s.close)
        s.cookies.set('sessionid','synthetic-cookie')
        a=Adapter((401,)); s.mount('https://',a)
        with self.assertRaises(errors.AuthError):
            g.GenericClient('https://example.invalid/api/2.0/','u','p','session',session=s)
        self.assertEqual(len(a.calls),1)
    def test_invalid_secret_sanitized_and_uri_not_consumed(self):
        for secret in ('otpauth://totp/example?secret=DO-NOT-LOG', 'DO-NOT-LOG!'):
            c,_=self.client(secret=secret)
            with self.assertRaises(errors.ApiClientError) as caught: c._session_otp()
            text=''.join(traceback.format_exception(caught.exception))
            self.assertNotIn(secret,text)
            self.assertIsNone(caught.exception.__context__)
    def test_invalid_otp_zero_dispatch(self):
        c,a=self.client()
        for otp in ('12345','1234567','１２３４５６','12345\n',123456):
            with self.assertRaises(errors.ApiClientError): c.post('tags/',{},otp=otp)
        self.assertEqual(a.calls,[])
    def test_redirect_and_origin_still_refused(self):
        c,a=self.client(statuses=(307,))
        with self.assertRaises(errors.ApiClientError): c.post('tags/',{},otp='123456')
        self.assertEqual(len(a.calls),1)
        with self.assertRaises(errors.ApiClientError): c.get('https://elsewhere.invalid/',otp='123456')
        self.assertEqual(len(a.calls),1)

class DigestOTPPolicy(unittest.TestCase):
    def test_digest_otp_refused_all_entries_without_dispatch(self):
        from test_digest_auth import Adapter as DigestAdapter
        for name in ('get', 'get_raw', 'post', 'put', 'delete'):
            with self.subTest(method=name):
                session = requests.Session()
                self.addCleanup(session.close)
                adapter = DigestAdapter(self)
                session.mount('https://', adapter)
                c = g.GenericClient('https://fixture.invalid/api/2.0/',
                                    'synthetic-user', 'synthetic-password',
                                    'digest', session=session)
                args = ('/servers/', {'name':'synthetic'}) if name in ('post','put') else ('/servers/',)
                kw = {'data':{'name':'synthetic-delete'}} if name == 'delete' else {}
                with self.assertRaises(errors.ApiClientError) as caught:
                    getattr(c, name)(*args, otp='123456', **kw)
                self.assertEqual(caught.exception.message,
                                 'explicit OTP with Digest authentication is unsupported')
                self.assertEqual(adapter.calls, [])
                # Same real challenge adapter remains operational: legacy Digest
                # without OTP still negotiates twice with unchanged mutation data.
                getattr(c, name)(*args, **kw)
                self.assertEqual(len(adapter.calls), 2)
                for req in adapter.calls:
                    self.assertNotIn('OTP', req.headers)
                self.assertEqual(adapter.calls[0].body, adapter.calls[1].body)
                if name in ('post','put','delete'):
                    self.assertIsNotNone(adapter.calls[0].body)
                # A prior successful Digest negotiation grants no OTP exception.
                with self.assertRaises(errors.ApiClientError):
                    getattr(c, name)(*args, otp='654321', **kw)
                self.assertEqual(len(adapter.calls), 2)

    def test_basic_explicit_otp_empty_challenge_single_dispatch(self):
        session=requests.Session(); self.addCleanup(session.close)
        adapter=Adapter((401,)); session.mount('https://',adapter)
        c=g.GenericClient('https://example.invalid/api/2.0/','synthetic-user',
                          'synthetic-password','basic',session=session)
        with self.assertRaises(errors.AuthError):
            c.post('tags/', {'name':'synthetic'}, otp='123456')
        self.assertEqual(len(adapter.calls),1)
        self.assertEqual(adapter.calls[0][0].headers['OTP'],'123456')
        self.assertTrue(adapter.calls[0][0].headers['Authorization'].startswith('Basic '))
