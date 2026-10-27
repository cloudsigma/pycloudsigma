import json
import unittest

import requests

from cloudsigma.resource import RemoteSnapshot, Snapshot


class Wire:
    def __init__(self):
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps({'uuid': 'snapshot-1'}).encode()
        response.headers['X-REQUEST-ID'] = 'synthetic-request'
        response.request = requests.Request(method, url).prepare()
        return response

    def __getattr__(self, method):
        return lambda url, **kwargs: self.request(method.upper(), url, **kwargs)


class SnapshotSingletonQueryTests(unittest.TestCase):
    def test_snapshot_and_remote_snapshot_drive_filters(self):
        wire = Wire()
        for resource, path in ((Snapshot, 'snapshots'),
                               (RemoteSnapshot, 'remotesnapshots')):
            item = resource(
                api_endpoint='https://next.cloudsigma.com/api/2.0/',
                username='synthetic', password='synthetic', login_method='basic')
            item.c._session = wire
            self.assertEqual(
                item.get('snapshot-1', query_params={'drive': 'drive-1'}),
                {'uuid': 'snapshot-1'})
            method, url, kwargs = wire.calls[-1]
            self.assertEqual(method, 'GET')
            self.assertEqual(
                url, 'https://next.cloudsigma.com/api/2.0/%s/snapshot-1/' % path)
            self.assertEqual(kwargs['params'], {'drive': 'drive-1'})


if __name__ == '__main__':
    unittest.main()
