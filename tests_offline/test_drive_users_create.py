"""DriveUsers singleton correction and explicit legacy shape compatibility."""
import copy
import json
import unittest
import requests
from cloudsigma.resource import DriveUsers, Drive, Server
from cloudsigma import errors
from test_drive_users_update_amount import Adapter, UUID, RESULT


class DriveUsersCreateTests(unittest.TestCase):
    def client(self, session, status=201, failure=None, cls=DriveUsers):
        adapter = Adapter(status, failure)
        session.mount('https://', adapter)
        return cls(api_endpoint='https://fixture.invalid/api/2.0/',
                   username='fixture', password='synthetic', session=session), adapter

    def test_documented_singleton(self):
        with requests.Session() as session:
            resource, adapter = self.client(session)
            data = {'drive': UUID, 'amount': 5}
            self.assertEqual(resource.create(data), RESULT)
            self.assertEqual(data, {'drive': UUID, 'amount': 5})
            self.assertEqual(len(adapter.seen), 1)
            req, options = adapter.seen[0]
            self.assertEqual(req.method, 'POST')
            self.assertEqual(req.url, 'https://fixture.invalid/api/2.0/driveusers/')
            self.assertEqual(json.loads(req.body), {'drive': UUID, 'amount': 5})
            self.assertEqual(req.headers['Content-Type'], 'application/json')
            self.assertIn('Authorization', req.headers)
            self.assertEqual(options['timeout'], 15)

    def test_presence_and_query(self):
        for amount in (0, False, -1, 9007199254740993, None):
            with self.subTest(amount=amount), requests.Session() as session:
                resource, adapter = self.client(session)
                data = {'drive': UUID, 'amount': amount, 'extension': {'enabled': False, 'empty': []}}
                before = copy.deepcopy(data)
                query = {'synthetic': 'a b'}
                resource.create(data, query)
                req = adapter.seen[0][0]
                self.assertEqual(json.loads(req.body), before)
                self.assertIs(type(json.loads(req.body)['amount']), type(amount))
                self.assertEqual(req.url, 'https://fixture.invalid/api/2.0/driveusers/?synthetic=a+b')
                self.assertEqual(data, before)
                self.assertEqual(query, {'synthetic': 'a b'})

    def test_legacy_shapes(self):
        item = {'drive': UUID, 'amount': 5}
        for data in ([item], (item,), [], (), {'objects': [item], 'extension': False}, {'objects': []}):
            with self.subTest(data=data), requests.Session() as session:
                resource, adapter = self.client(session)
                before = copy.deepcopy(data)
                self.assertEqual(resource.create(data, {'legacy': 0}), RESULT)
                expected = data if isinstance(data, dict) else {'objects': list(data)}
                self.assertEqual(json.loads(adapter.seen[0][0].body), expected)
                self.assertEqual(data, before)
                self.assertTrue(adapter.seen[0][0].url.endswith('?legacy=0'))
        with requests.Session() as session:
            resource, adapter = self.client(session)
            for data in (None, False, 1, 'bad'):
                with self.assertRaises(TypeError):
                    resource.create(data)
            self.assertEqual(adapter.seen, [])

    def test_unrelated_creates_and_updates(self):
        for cls in (Drive, Server):
            with self.subTest(cls=cls), requests.Session() as session:
                resource, adapter = self.client(session, cls=cls)
                resource.create({'name': 'fixture'})
                self.assertEqual(json.loads(adapter.seen[0][0].body), {'objects': [{'name': 'fixture'}]})
        with requests.Session() as session:
            resource, adapter = self.client(session, status=200)
            resource.update(UUID, {'amount': 0, 'extension': False})
            resource.update_amount(UUID, 0)
            self.assertEqual([json.loads(r.body) for r, _ in adapter.seen],
                             [{'amount': 0, 'extension': False}, {'amount': 0}])
            self.assertEqual([r.method for r, _ in adapter.seen], ['PUT', 'PUT'])

    def test_errors(self):
        for status, error in ((403, errors.PermissionError), (404, errors.ClientError),
                              (500, errors.ServerError), (302, errors.ApiClientError)):
            with self.subTest(status=status), requests.Session() as session:
                resource, adapter = self.client(session, status=status)
                with self.assertRaises(error) as caught:
                    resource.create({'drive': UUID, 'amount': 5})
                self.assertEqual(caught.exception.status_code, status)
                self.assertEqual(caught.exception.request_id, 'synthetic-request')
                self.assertEqual(len(adapter.seen), 1)

    def test_transport_error(self):
        failure = requests.exceptions.Timeout('synthetic timeout')
        with requests.Session() as session:
            resource, adapter = self.client(session, failure=failure)
            with self.assertRaises(requests.exceptions.Timeout) as caught:
                resource.create({'drive': UUID, 'amount': 5})
            self.assertIs(caught.exception, failure)
            self.assertEqual(len(adapter.seen), 1)
