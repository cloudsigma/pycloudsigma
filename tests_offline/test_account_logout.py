"""Public Accounts logout contract through installed package transport."""
import json
import unittest
import requests
from cloudsigma.resource import Accounts
from cloudsigma import errors


class Adapter(requests.adapters.BaseAdapter):
    def __init__(self, status=200, body=b'', failure=None):
        self.status, self.body, self.failure = status, body, failure
        self.seen = []
        self.closed = 0

    def send(self, request, **kwargs):
        self.seen.append((request, kwargs))
        if self.failure:
            raise self.failure
        response = requests.Response()
        response.status_code = self.status
        response._content = self.body
        response.request = request
        response.headers['X-REQUEST-ID'] = 'synthetic-request'
        return response

    def close(self):
        self.closed += 1


class AccountLogoutTests(unittest.TestCase):
    def client(self, session, **kwargs):
        adapter = Adapter(**kwargs)
        session.mount('https://', adapter)
        return Accounts(api_endpoint='https://fixture.invalid/api/2.0/',
                        username='fixture', password='synthetic', session=session,
                        login_method='none'), adapter

    def test_exact_empty_ack(self):
        with requests.Session() as session:
            session.cookies.set('sessionid', 'synthetic-session', domain='fixture.invalid', path='/')
            session.cookies.set('csrftoken', 'synthetic-csrf', domain='fixture.invalid', path='/')
            session.headers['X-CSRFToken'] = 'synthetic-csrf'
            account, adapter = self.client(session)
            self.assertIsNone(account.logout())
            self.assertEqual(len(adapter.seen), 1)
            req, opts = adapter.seen[0]
            self.assertEqual(req.method, 'POST')
            self.assertEqual(req.url, 'https://fixture.invalid/api/2.0/accounts/action/?do=logout')
            self.assertEqual(json.loads(req.body), {})
            self.assertEqual(req.headers['Content-Type'], 'application/json')
            self.assertNotIn('Authorization', req.headers)
            self.assertIn('sessionid=synthetic-session', req.headers['Cookie'])
            self.assertIn('csrftoken=synthetic-csrf', req.headers['Cookie'])
            self.assertEqual(req.headers['X-CSRFToken'], 'synthetic-csrf')
            self.assertIs(account.c.http, session)
            self.assertEqual(account.c.username, 'fixture')
            self.assertEqual(account.c.password, 'synthetic')
            self.assertEqual(account.c.login_method, 'none')
            self.assertEqual(opts['timeout'], 15)
            self.assertEqual(account.c.resp.status_code, 200)
            self.assertEqual(session.cookies.get('sessionid'), 'synthetic-session')
            self.assertEqual(session.cookies.get('csrftoken'), 'synthetic-csrf')
            self.assertIsNone(account.logout())
            self.assertEqual(len(adapter.seen), 2)
            self.assertEqual(adapter.closed, 0)
            self.assertEqual(session.cookies.get('sessionid'), 'synthetic-session')
            self.assertTrue(all('Authorization' not in req.headers for req, _ in adapter.seen))

    def test_existing_json_response_policy(self):
        for status in (200, 201, 202):
            with self.subTest(status=status), requests.Session() as session:
                account, adapter = self.client(session, status=status, body=b'{"other":123}')
                self.assertEqual(account.logout(), {'other': 123})
                self.assertEqual(len(adapter.seen), 1)

    def test_errors(self):
        for status, cls in [(302, errors.ApiClientError), (400, errors.ClientError),
                            (401, errors.AuthError), (403, errors.PermissionError),
                            (404, errors.ClientError), (409, errors.ClientError),
                            (429, errors.ClientError), (500, errors.ServerError)]:
            with self.subTest(status=status), requests.Session() as session:
                account, adapter = self.client(session, status=status, body=b'fixture')
                with self.assertRaises(cls) as caught:
                    account.logout()
                self.assertEqual(caught.exception.status_code, status)
                self.assertEqual(account.c.resp.status_code, status)
                self.assertEqual(adapter.closed, 0)
                self.assertEqual(len(adapter.seen), 1)

    def test_transport_identity(self):
        for cls in (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            with self.subTest(cls=cls), requests.Session() as session:
                failure = cls('synthetic')
                account, adapter = self.client(session, failure=failure)
                with self.assertRaises(cls) as caught:
                    account.logout()
                self.assertIs(caught.exception, failure)
                self.assertEqual(len(adapter.seen), 1)

    def test_nonempty_invalid_json_not_swallowed(self):
        for status, body in [(200, b' '), (200, b'not json'), (201, b''), (202, b'')]:
            with self.subTest(status=status, body=body), requests.Session() as session:
                account, adapter = self.client(session, status=status, body=body)
                with self.assertRaises(ValueError):
                    account.logout()
                self.assertEqual(len(adapter.seen), 1)
