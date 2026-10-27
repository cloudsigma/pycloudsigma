"""Local urllib preprocessing only; not upload protocol/provider qualification."""
import datetime
import io
import json
from unittest import TestCase, mock
import urllib.error
import urllib.request

from cloudsigma.upload_client import CSUploader, UploadError


def preprocess(request):
    handler = urllib.request.HTTPHandler()
    director = urllib.request.OpenerDirector()
    director.add_handler(handler)
    return handler.http_request(request)


class RecordingOpener:
    def __init__(self, body, status=200, error=None):
        self.body, self.status, self.error = body, status, error
        self.requests = []

    def open(self, request):
        # Execute the real stdlib body/type and Content-Length processing.
        # No OpenerDirector transport dispatch or sockets are used.
        self.requests.append(request)
        preprocess(request)
        if self.error:
            raise self.error
        response = io.BytesIO(self.body)
        response.getcode = lambda: self.status
        return response


class UploaderJSONBytesTests(TestCase):
    def uploader(self, opener):
        # Preserve the real constructor and Basic-auth opener construction.
        client = CSUploader('https://example.invalid/api/2.0/',
                            '/unused/image', 4096, 'synthetic-user', 'synthetic-pass')
        self.assertTrue(any(isinstance(h, urllib.request.HTTPBasicAuthHandler)
                            for h in client.opener.handlers))
        client.opener = opener
        client.size = 9007199254740993
        client.drive_url = 'https://example.invalid/api/2.0/drives/synthetic-id/'
        return client

    def assert_request(self, opener, url, expected):
        self.assertEqual(len(opener.requests), 1)
        request = opener.requests[0]
        self.assertEqual(request.full_url, url)
        self.assertEqual(request.get_method(), 'POST')
        self.assertIsInstance(request.data, bytes)
        self.assertEqual(request.data, expected)
        self.assertEqual(request.get_header('Content-length'), str(len(expected)))
        self.assertEqual(request.get_header('Content-type'), 'application/json')
        self.assertEqual(request.get_header('Accept'), 'application/json')
        self.assertIsNone(request.get_header('Authorization'))
        return request

    def test_init_ascii(self):
        opener = RecordingOpener(b'{"objects":[{"uuid":"synthetic-id"}]}', 201)
        client = self.uploader(opener)
        fixed_time = datetime.datetime(2026, 1, 2, 3, 4, 5)
        with mock.patch('cloudsigma.upload_client.datetime.datetime') as clock:
            clock.utcnow.return_value = fixed_time
            self.assertEqual(client.init_upload(), 'synthetic-id')
        self.assert_request(opener, 'https://example.invalid/api/2.0/initupload/',
                            b'{"name": "Upload_2026-01-02 03:04:05", "size": 9007199254740993, "media": "disk"}')

    def test_init_non_ascii_preserves_default_json_escaping(self):
        opener = RecordingOpener(b'{"objects":[{"uuid":"synthetic-id"}]}')
        client = self.uploader(opener)
        fixed_time = datetime.datetime(2026, 1, 2, 3, 4, 5)
        with mock.patch('cloudsigma.upload_client.datetime.datetime') as clock:
            clock.utcnow.return_value = fixed_time
            self.assertEqual(client.init_upload('dísk雪'), 'synthetic-id')
        request = self.assert_request(opener, 'https://example.invalid/api/2.0/initupload/',
            b'{"name": "Upload_2026-01-02 03:04:05", "size": 9007199254740993, "media": "d\\u00edsk\\u96ea"}')
        self.assertEqual(json.loads(request.data)['media'], 'dísk雪')

    def test_link_body_and_auth_refresh(self):
        opener = RecordingOpener(b'{"link":"/synthetic-upload?token=fixture"}')
        client = self.uploader(opener)
        with mock.patch.object(client, 'init_auth', return_value=opener) as auth:
            self.assertEqual(client.get_chunk_upload_link(7), '/synthetic-upload?token=fixture')
        auth.assert_called_once_with()
        self.assert_request(opener,
            'https://example.invalid/api/2.0/drives/synthetic-id/action/?do=upload_chunk',
            b'{"chunk_number": 7, "chunk_size": 4096}')

    def test_init_unsuccessful_status_preserved(self):
        client = self.uploader(RecordingOpener(b'fixture failure', 503))
        with self.assertRaisesRegex(UploadError, 'Wrong response status code 503'):
            client.init_upload()

    def test_link_http_error_identity_preserved(self):
        error = urllib.error.HTTPError('https://example.invalid/', 416, 'fixture', {}, None)
        opener = RecordingOpener(b'', error=error)
        client = self.uploader(opener)
        with mock.patch.object(client, 'init_auth', return_value=opener):
            with self.assertRaises(urllib.error.HTTPError) as raised:
                client.get_chunk_upload_link(7)
        self.assertIs(raised.exception, error)

    def test_stdlib_rejects_text_body_before_transport(self):
        request = urllib.request.Request('https://example.invalid/', data='{}')
        with self.assertRaisesRegex(TypeError, 'POST data should be bytes'):
            preprocess(request)
