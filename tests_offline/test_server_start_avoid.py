"""Public server-start compute placement hints; no placement guarantee."""
import json
import unittest
from urllib.parse import parse_qs, urlsplit
import requests
from cloudsigma.resource import Server


class Adapter(requests.adapters.BaseAdapter):
    def __init__(self):
        self.requests = []

    def send(self, request, **kwargs):
        self.requests.append(request)
        response = requests.Response()
        response.status_code = 202
        response._content = b'{"uuid":"server-1","status":"starting"}'
        response.request = request
        return response

    def close(self):
        pass


class ServerStartAvoidTests(unittest.TestCase):
    def check_start(self, avoid, expected, allocation=None, legacy=False):
        with requests.Session() as session:
            adapter = Adapter()
            session.mount('https://', adapter)
            server = Server(api_endpoint='https://fixture.invalid/api/2.0/',
                            username='fixture', password='synthetic', session=session)
            if legacy:
                result = server.start('server-1', allocation)
            else:
                result = server.start('server-1', allocation, avoid=avoid)
            self.assertEqual(result, {'uuid': 'server-1', 'status': 'starting'})
            self.assertEqual(len(adapter.requests), 1)
            request = adapter.requests[0]
            self.assertEqual(request.method, 'POST')
            self.assertEqual(urlsplit(request.url).path, '/api/2.0/servers/server-1/action/')
            self.assertEqual(parse_qs(urlsplit(request.url).query), expected)
            self.assertEqual(json.loads(request.body),
                             {'allocation_method': allocation} if allocation else {})

    def test_ordered_compute_avoid(self):
        for avoid, value in [('server-2', 'server-2'),
                             (['server-3', 'server-2'], 'server-3,server-2'),
                             (('server-2', 'server-3'), 'server-2,server-3')]:
            with self.subTest(avoid=avoid):
                self.check_start(avoid, {'do': ['start'], 'avoid': [value]}, 'auto')

    def test_optional_and_legacy_start(self):
        for avoid in (None, [], ''):
            with self.subTest(avoid=avoid):
                self.check_start(avoid, {'do': ['start']})
        self.check_start(None, {'do': ['start']}, 'auto', legacy=True)
