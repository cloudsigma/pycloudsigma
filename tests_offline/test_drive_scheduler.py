"""Documented scheduler attachment only; no scheduler creation or live effects."""
import json
import unittest
from urllib.parse import parse_qs, urlsplit
import requests
from cloudsigma.resource import Drive
from cloudsigma.errors import ClientError

DRIVE = '34f9c721-ec23-4f5c-86ab-2839f687f14e'
POLICY = '103de42c-17a1-40ea-bc0f-521789168bbf'
RESULT = {'uuid': DRIVE, 'backup_scheduler': {'uuid': POLICY,
          'resource_uri': '/api/2.0/backupschedulers/' + POLICY + '/'},
          'jobs': [], 'status': 'unmounted'}


class Adapter(requests.adapters.BaseAdapter):
    def __init__(self, status):
        self.requests = []
        self.status = status

    def send(self, request, **kwargs):
        self.requests.append(request)
        response = requests.Response()
        response.status_code = self.status
        response._content = json.dumps(RESULT if self.status == 202 else
            [{'error_type': 'notfound', 'error_message': 'missing'}]).encode()
        response.request = request
        return response

    def close(self):
        pass


class DriveSchedulerTests(unittest.TestCase):
    def exercise(self, status):
        with requests.Session() as session:
            adapter = Adapter(status)
            session.mount('https://', adapter)
            drive = Drive(api_endpoint='https://fixture.invalid/api/2.0/',
                          username='fixture', password='synthetic', session=session)
            if status == 202:
                self.assertEqual(drive.set_scheduler(DRIVE, POLICY), RESULT)
            else:
                with self.assertRaises(ClientError):
                    drive.set_scheduler(DRIVE, POLICY)
            self.assertEqual(len(adapter.requests), 1)
            request = adapter.requests[0]
            self.assertEqual(request.method, 'POST')
            self.assertEqual(urlsplit(request.url).path,
                             '/api/2.0/drives/' + DRIVE + '/action/')
            self.assertEqual(parse_qs(urlsplit(request.url).query),
                             {'do': ['set_scheduler']})
            self.assertEqual(json.loads(request.body), {'backup_policy_uuid': POLICY})

    def test_link_acknowledgment(self):
        self.exercise(202)

    def test_missing_drive_error(self):
        self.exercise(404)
