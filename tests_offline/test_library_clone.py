"""Named library clone request; synthetic acknowledgment, not completion."""
import json
import unittest
from urllib.parse import parse_qs, urlsplit
import requests
from cloudsigma.resource import LibDrive
from cloudsigma.errors import ClientError


class Adapter(requests.adapters.BaseAdapter):
    def __init__(self, status=202):
        self.requests = []
        self.status = status

    def send(self, request, **kwargs):
        self.requests.append(request)
        response = requests.Response()
        response.status_code = self.status
        response._content = (b'{"objects":[{"uuid":"owned-drive","name":"clone"}]}'
                             if self.status == 202 else
                             b'[{"error_type":"notfound","error_message":"missing"}]')
        response.request = request
        return response

    def close(self):
        pass


class LibraryCloneTests(unittest.TestCase):
    def test_clone_optional_definition(self):
        for data in (None, {}, {'name': 'clone', 'size': 1207959631,
                               'meta': {'purpose': 'fixture'}}):
            with self.subTest(data=data), requests.Session() as session:
                adapter = Adapter()
                session.mount('https://', adapter)
                library = LibDrive(api_endpoint='https://fixture.invalid/api/2.0/',
                                   username='fixture', password='synthetic', session=session)
                result = library.clone('library-drive', data)
                self.assertEqual(result, {'uuid': 'owned-drive', 'name': 'clone'})
                self.assertEqual(len(adapter.requests), 1)
                request = adapter.requests[0]
                self.assertEqual(request.method, 'POST')
                self.assertEqual(urlsplit(request.url).path,
                                 '/api/2.0/libdrives/library-drive/action/')
                self.assertEqual(parse_qs(urlsplit(request.url).query), {'do': ['clone']})
                self.assertEqual(json.loads(request.body), data or {})

    def test_clone_error_and_default_call(self):
        with requests.Session() as session:
            adapter = Adapter(404)
            session.mount('https://', adapter)
            library = LibDrive(api_endpoint='https://fixture.invalid/api/2.0/',
                               username='fixture', password='synthetic', session=session)
            with self.assertRaises(ClientError):
                library.clone('missing-library-drive')
            self.assertEqual(len(adapter.requests), 1)
            self.assertEqual(json.loads(adapter.requests[0].body), {})
