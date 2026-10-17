"""Documented RDS user-count update through actual Requests preparation."""
import json
import unittest
import requests
from cloudsigma.resource import DriveUsers
from cloudsigma import errors

UUID = 'e26fd531-7336-40e7-9a6f-db42e7a6b9f2'
RESULT = {'amount': 5, 'drive': {
    'resource_uri': '/api/2.0/drives/' + UUID + '/', 'uuid': UUID}}


class Adapter(requests.adapters.BaseAdapter):
    def __init__(self, status=200, failure=None):
        self.seen = []
        self.status = status
        self.failure = failure

    def send(self, request, **kwargs):
        self.seen.append((request, kwargs))
        if self.failure:
            raise self.failure
        response = requests.Response()
        response.status_code = self.status
        response._content = json.dumps({'objects': [RESULT]}).encode('utf-8')
        response.headers['X-REQUEST-ID'] = 'synthetic-request'
        response.request = request
        return response

    def close(self):
        pass


class DriveUsersUpdateAmountTests(unittest.TestCase):
    def setup_client(self, session, status=200, failure=None):
        adapter = Adapter(status, failure)
        session.mount('https://', adapter)
        resource = DriveUsers(api_endpoint='https://fixture.invalid/api/2.0/',
                              username='fixture', password='synthetic', session=session)
        return resource, adapter

    def test_documented_update(self):
        with requests.Session() as session:
            resource, adapter = self.setup_client(session)
            self.assertEqual(resource.update_amount(UUID, 5), RESULT)
            self.assertEqual(len(adapter.seen), 1)
            request, options = adapter.seen[0]
            self.assertEqual(request.method, 'PUT')
            self.assertEqual(request.url, 'https://fixture.invalid/api/2.0/driveusers/' + UUID + '/')
            self.assertEqual(json.loads(request.body), {'amount': 5})
            self.assertEqual(request.headers['Content-Type'], 'application/json')
            self.assertIn('Authorization', request.headers)
            self.assertEqual(options['timeout'], 15)

    def test_integer_presence_without_invented_bounds(self):
        # Forwarding policy only: zero/negative/large counts are not API acceptance claims.
        for amount in (0, -1, 9007199254740993):
            with self.subTest(amount=amount), requests.Session() as session:
                resource, adapter = self.setup_client(session)
                resource.update_amount(UUID, amount)
                self.assertEqual(len(adapter.seen), 1)
                self.assertEqual(json.loads(adapter.seen[0][0].body), {'amount': amount})

    def test_invalid_inputs_no_dispatch(self):
        with requests.Session() as session:
            resource, adapter = self.setup_client(session)
            for uuid in (None, '', b'bytes', '../x', 'a/b', 'a?b', 'a#b', '%2f', 'x\n'):
                with self.subTest(uuid=uuid), self.assertRaises(ValueError):
                    resource.update_amount(uuid, 5)
            for amount in (None, True, False, 1.5, '5', [], {}):
                with self.subTest(amount=amount), self.assertRaises(ValueError):
                    resource.update_amount(UUID, amount)
            self.assertEqual(adapter.seen, [])

    def test_http_errors(self):
        for status, error in [(403, errors.PermissionError), (404, errors.ClientError),
                              (500, errors.ServerError), (302, errors.ApiClientError)]:
            with self.subTest(status=status), requests.Session() as session:
                resource, adapter = self.setup_client(session, status)
                with self.assertRaises(error) as caught:
                    resource.update_amount(UUID, 5)
                self.assertEqual(caught.exception.status_code, status)
                self.assertEqual(caught.exception.request_id, 'synthetic-request')
                self.assertEqual(len(adapter.seen), 1)

    def test_transport_error(self):
        failure = requests.exceptions.Timeout('synthetic timeout')
        with requests.Session() as session:
            resource, adapter = self.setup_client(session, failure=failure)
            with self.assertRaises(requests.exceptions.Timeout) as caught:
                resource.update_amount(UUID, 5)
            self.assertIs(caught.exception, failure)
            self.assertEqual(len(adapter.seen), 1)

    def test_inherited_update_unchanged(self):
        with requests.Session() as session:
            resource, adapter = self.setup_client(session)
            definition = {'amount': 5, 'extension': {'value': None}}
            self.assertEqual(resource.update(UUID, definition), RESULT)
            self.assertEqual(json.loads(adapter.seen[0][0].body), definition)
            self.assertEqual(len(adapter.seen), 1)
