"""Real Requests, synthetic adapter; public general Digest MD5/auth equations.
No sockets or credentials. Not server acceptance or universal Digest support.
"""
import hashlib
import io
import json
import unittest
import requests
from requests.utils import parse_dict_header
from cloudsigma.generic import GenericClient
from cloudsigma import errors

CHALLENGE = ('Digest nonce="1363185031.81:FCF2:443b657bfd1a7340a0841c704d93a579", '
             'realm="users", algorithm="MD5", '
             'opaque="d7d89a75f4f6e3044626c6c251456e6b401401e7", qop="auth"')


class Raw(io.BytesIO):
    def __init__(self):
        super().__init__(b'challenge body')
        self.releases = 0
        self.bytes_read = 0

    def read(self, *args, **kwargs):
        data = super().read(*args)
        self.bytes_read += len(data)
        return data

    def release_conn(self):
        self.releases += 1


class Adapter(requests.adapters.BaseAdapter):
    def __init__(self, case, statuses=(401, 200), challenge=CHALLENGE):
        self.case, self.statuses, self.challenge = case, statuses, challenge
        self.calls, self.responses = [], []

    def send(self, req, **kwargs):
        c = self.case
        c.assertTrue(req.url.startswith('https://fixture.invalid/api/2.0/'))
        c.assertEqual(kwargs['timeout'], 15)
        c.assertEqual(kwargs['proxies'], {})
        c.assertIs(kwargs['verify'], True)
        c.assertNotIn('Cookie', req.headers)
        c.assertNotIn('Proxy-Authorization', req.headers)
        c.assertNotIn('synthetic-password', str(req.headers))
        c.assertNotIn('synthetic-password', req.url)
        if len(self.calls) % len(self.statuses) == 0:
            c.assertNotIn('Authorization', req.headers)
        else:
            self.verify_digest(req)
            c.assertEqual(req.body, self.calls[-1].body)
            c.assertEqual(self.responses[-1].raw.releases, 1)
            c.assertEqual(self.responses[-1].raw.bytes_read, len(b'challenge body'))
        status = self.statuses[len(self.calls) % len(self.statuses)]
        self.calls.append(req)
        r = requests.Response()
        r.status_code, r.url, r.request, r.connection = status, req.url, req, self
        r.raw = Raw()
        if status == 401:
            if self.challenge:
                r.headers['WWW-Authenticate'] = self.challenge
        else:
            r._content = b'{"objects": [{"uuid": "fixture"}]}'
        if 300 <= status < 400:
            r.headers['Location'] = 'https://other.invalid/collect/'
        self.responses.append(r)
        return r

    def verify_digest(self, req):
        c = self.case
        header = req.headers['Authorization']
        c.assertTrue(header.startswith('Digest '))
        d = parse_dict_header(header[7:])
        expected = parse_dict_header(CHALLENGE[7:])
        for key in ('realm', 'nonce', 'opaque', 'algorithm', 'qop'):
            c.assertEqual(d[key], expected[key])
        c.assertEqual(d['username'], 'synthetic-user')
        c.assertEqual(d['uri'], req.path_url)
        c.assertEqual(d['nc'], '00000001')
        c.assertTrue(d['cnonce'])
        md5 = lambda text: hashlib.md5(text.encode()).hexdigest()
        ha1 = md5('synthetic-user:users:synthetic-password')
        ha2 = md5(req.method + ':' + req.path_url)
        c.assertEqual(d['response'], md5(':'.join((ha1, d['nonce'], d['nc'], d['cnonce'], 'auth', ha2))))

    def close(self):
        pass


class DigestTests(unittest.TestCase):
    def client(self, statuses=(401, 200), challenge=CHALLENGE):
        session = requests.Session()
        self.addCleanup(session.close)
        adapter = Adapter(self, statuses, challenge)
        session.mount('https://', adapter)
        session.mount('http://', adapter)
        client = GenericClient(api_endpoint='https://fixture.invalid/api/2.0/',
                               username='synthetic-user', password='synthetic-password',
                               login_method='digest', session=session)
        return client, adapter

    def test_challenge_all_common_methods_and_raw(self):
        for method in ('get', 'get_raw', 'post', 'put', 'delete'):
            with self.subTest(method=method):
                client, adapter = self.client()
                args = ['/servers/']
                if method in ('put', 'post'):
                    args.append({'name': 'synthetic', 'meta': {'unicode': 'данни'}})
                result = getattr(client, method)(*args, query_params={'limit': 2})
                self.assertEqual(result, {'objects': [{'uuid': 'fixture'}]} if method == 'get_raw' else {'uuid': 'fixture'})
                self.assertEqual(len(adapter.calls), 2)
                if method in ('post', 'put'):
                    self.assertEqual(json.loads(adapter.calls[1].body), args[1])
                self.assertEqual(client.resp.history, [adapter.responses[0]])

    def test_no_challenge_state_between_operations(self):
        client, adapter = self.client()
        client.get('/servers/')
        client.get('/drives/')
        self.assertEqual(len(adapter.calls), 4)

    def test_rejected_credentials_retry_once(self):
        client, adapter = self.client((401, 401))
        with self.assertRaises(errors.AuthError):
            client.get('/servers/')
        self.assertEqual(len(adapter.calls), 2)

    def test_no_basic_fallback(self):
        for challenge in (None, 'Basic realm="users"'):
            with self.subTest(challenge=challenge):
                client, adapter = self.client((401,), challenge)
                with self.assertRaises(errors.AuthError):
                    client.get('/servers/')
                self.assertEqual(len(adapter.calls), 1)

    def test_redirects_before_and_after_challenge_refused(self):
        for status in (301, 302, 303, 307, 308):
            for statuses in ((status,), (401, status)):
                with self.subTest(statuses=statuses):
                    client, adapter = self.client(statuses)
                    with self.assertRaises(errors.ApiClientError) as caught:
                        client.post('/servers/', {'name': 'synthetic'})
                    self.assertEqual(caught.exception.message, 'redirect refused')
                    self.assertEqual(len(adapter.calls), len(statuses))

    def test_cross_origin_refused_before_dispatch(self):
        client, adapter = self.client()
        with self.assertRaises(errors.ApiClientError):
            client.get('https://other.invalid/api/2.0/servers/')
        self.assertEqual(adapter.calls, [])

    def test_legacy_auth_argument_selection(self):
        for method in (None, 'basic', 'none'):
            client = GenericClient(api_endpoint='https://fixture.invalid/', username='user', password='pass', login_method=method)
            self.addCleanup(client.http.close)
            args = client._get_req_args()
            if method == 'none':
                self.assertNotIn('auth', args)
            else:
                self.assertEqual(args['auth'], ('user', 'pass'))
        # Session constructor/login behavior is covered by the inherited suite.
