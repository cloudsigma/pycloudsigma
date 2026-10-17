"""Backup scheduler collection deletion acknowledgment, never completion."""
import json
import unittest
import requests
from cloudsigma.scheduler_reads import BackupSchedulerReads
from cloudsigma import errors

IDS = ['b137e217-42b6-4ecf-8575-d72efc2d3dbd',
       'e035a488-8587-4a15-ab25-9b7343236bc9',
       'feded33c-106f-49fa-a1c4-be5c718ad1b5']


class Adapter(requests.adapters.BaseAdapter):
    def __init__(self, status=204, failure=None):
        self.seen = []
        self.status = status
        self.failure = failure

    def send(self, request, **kwargs):
        self.seen.append((request, kwargs))
        if self.failure:
            raise self.failure
        response = requests.Response()
        response.status_code = self.status
        response._content = b'' if self.status == 204 else b'[{"error_type":"fixture"}]'
        response.headers['X-REQUEST-ID'] = 'synthetic-request'
        response.request = request
        return response

    def close(self):
        pass


class SchedulerDeleteManyTests(unittest.TestCase):
    def setup_client(self, session, status=204, failure=None, cls=BackupSchedulerReads):
        adapter = Adapter(status, failure)
        session.mount('https://', adapter)
        resource = cls(api_endpoint='https://fixture.invalid/api/2.0/',
                       username='fixture', password='synthetic', session=session)
        return resource, adapter

    def test_documented_collection_request(self):
        for cls in (BackupSchedulerReads,):
            with self.subTest(cls=cls), requests.Session() as session:
                resource, adapter = self.setup_client(session, cls=cls)
                ids = list(IDS)
                self.assertIsNone(resource.delete_many(ids))
                self.assertEqual(ids, IDS)
                self.assertEqual(len(adapter.seen), 1)
                request, options = adapter.seen[0]
                self.assertEqual(request.method, 'DELETE')
                self.assertEqual(request.url, 'https://fixture.invalid/api/2.0/backupschedulers/')
                self.assertEqual(json.loads(request.body), {'objects': [
                    {'uuid': IDS[0]}, {'uuid': IDS[1]}, {'uuid': IDS[2]}]})
                self.assertEqual(request.headers['Content-Type'], 'application/json')
                self.assertIn('Authorization', request.headers)
                self.assertEqual(options['timeout'], 15)

    def test_order_and_duplicates(self):
        with requests.Session() as session:
            resource, adapter = self.setup_client(session)
            resource.delete_many((IDS[2], IDS[0], IDS[2]))
            self.assertEqual(json.loads(adapter.seen[0][0].body), {
                'objects': [{'uuid': IDS[2]}, {'uuid': IDS[0]}, {'uuid': IDS[2]}]})

    def test_invalid_input_no_dispatch(self):
        invalid = [None, [], (), IDS[0], {}, iter(IDS), [IDS[0], None],
                   [IDS[0], ''], [IDS[0], '../x'], [IDS[0], 'a/b'],
                   [IDS[0], 'a?b'], [IDS[0], 'a#b'], [IDS[0], '%2f'],
                   [IDS[0], 'x\n'], [IDS[0], b'bytes']]
        with requests.Session() as session:
            resource, adapter = self.setup_client(session)
            for value in invalid:
                with self.subTest(value=value), self.assertRaises(ValueError):
                    resource.delete_many(value)
            self.assertEqual(adapter.seen, [])

    def test_http_errors(self):
        for status, error in [(403, errors.PermissionError), (404, errors.ClientError),
                              (500, errors.ServerError), (302, errors.ApiClientError)]:
            with self.subTest(status=status), requests.Session() as session:
                resource, adapter = self.setup_client(session, status)
                with self.assertRaises(error) as caught:
                    resource.delete_many(IDS)
                self.assertEqual(caught.exception.status_code, status)
                self.assertEqual(caught.exception.request_id, 'synthetic-request')
                self.assertEqual(len(adapter.seen), 1)

    def test_transport_error(self):
        failure = requests.exceptions.Timeout('synthetic timeout')
        with requests.Session() as session:
            resource, adapter = self.setup_client(session, failure=failure)
            with self.assertRaises(requests.exceptions.Timeout) as caught:
                resource.delete_many(IDS)
            self.assertIs(caught.exception, failure)
            self.assertEqual(len(adapter.seen), 1)

    def test_legacy_singleton_has_no_body(self):
        with requests.Session() as session:
            resource, adapter = self.setup_client(session)
            self.assertIsNone(resource.delete(IDS[0]))
            request = adapter.seen[0][0]
            self.assertIsNone(request.body)
            self.assertEqual(request.url, 'https://fixture.invalid/api/2.0/backupschedulers/' + IDS[0] + '/')
