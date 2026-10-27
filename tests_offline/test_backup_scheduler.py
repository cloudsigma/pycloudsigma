import json
import unittest

import requests

from cloudsigma.resource import BackupScheduler


class Wire:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        status, body = self.responses.pop(0)
        response = requests.Response()
        response.status_code = status
        response._content = b'' if body is None else json.dumps(body).encode()
        response.headers['X-REQUEST-ID'] = 'synthetic-request'
        response.request = requests.Request(method, url).prepare()
        return response

    def __getattr__(self, method):
        return lambda url, **kwargs: self.request(method.upper(), url, **kwargs)


class BackupSchedulerTests(unittest.TestCase):
    def test_documented_crud_routes_and_envelopes(self):
        responses = [
            (200, {'objects': [{'uuid': 'scheduler-1', 'type': 'snapshot'}],
                   'meta': {'limit': 1, 'offset': 0, 'total_count': 1}}),
            (200, {'objects': [{'uuid': 'scheduler-1', 'type': 'snapshot',
                                'retention_policy': {'rules': []}}]}),
            (201, {'objects': [{'uuid': 'scheduler-2', 'type': 'backup'}]}),
            (200, {'objects': [{'uuid': 'scheduler-2', 'type': 'backup'}]}),
            (204, None),
        ]
        wire = Wire(responses)
        resource = BackupScheduler(
            api_endpoint='https://next.cloudsigma.com/api/2.0/',
            username='synthetic',
            password='synthetic',
            login_method='basic',
        )
        resource.c._session = wire

        self.assertEqual(resource.list({'type': 'snapshot'}), [
            {'uuid': 'scheduler-1', 'type': 'snapshot'}])
        self.assertEqual(resource.get('scheduler-1'), {
            'uuid': 'scheduler-1', 'type': 'snapshot',
            'retention_policy': {'rules': []}})
        self.assertEqual(resource.create({'name': 'synthetic'}), {
            'uuid': 'scheduler-2', 'type': 'backup'})
        self.assertEqual(resource.update(
            'scheduler-2', {'is_enabled': False}), {
                'uuid': 'scheduler-2', 'type': 'backup'})
        self.assertIsNone(resource.delete('scheduler-2'))

        self.assertEqual(
            [(method, url) for method, url, _ in wire.calls],
            [
                ('GET', 'https://next.cloudsigma.com/api/2.0/backupschedulers/'),
                ('GET', 'https://next.cloudsigma.com/api/2.0/backupschedulers/scheduler-1/'),
                ('POST', 'https://next.cloudsigma.com/api/2.0/backupschedulers/'),
                ('PUT', 'https://next.cloudsigma.com/api/2.0/backupschedulers/scheduler-2/'),
                ('DELETE', 'https://next.cloudsigma.com/api/2.0/backupschedulers/scheduler-2/'),
            ],
        )
        self.assertEqual(wire.calls[0][2]['params'], {'type': 'snapshot', 'limit': 0})
        self.assertEqual(json.loads(wire.calls[2][2]['data']), {
            'objects': [{'name': 'synthetic'}]})
        self.assertEqual(json.loads(wire.calls[3][2]['data']), {
            'is_enabled': False})


if __name__ == '__main__':
    unittest.main()
