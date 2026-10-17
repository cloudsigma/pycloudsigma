"""Local file -> native Requests multipart bytes, not provider acceptance."""
import base64
from email import policy
from email.parser import BytesParser
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import requests
from requests.adapters import BaseAdapter
from cloudsigma.resumable_upload import Upload


class RecordingAdapter(BaseAdapter):
    def __init__(self, statuses):
        self.statuses = iter(statuses)
        self.calls = []

    def send(self, request, **kwargs):
        self.calls.append(request)
        response = requests.Response()
        response.status_code = next(self.statuses)
        response._content = b'fixture response'
        response.request = request
        response.url = request.url
        return response

    def close(self):
        pass


class ResumableChunkBytesTests(unittest.TestCase):
    def exercise(self, payload, chunk_size, expected_chunks, statuses=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'image.raw'
            path.write_bytes(payload)
            uploader = Upload(str(path), drive_uuid='drive-fixture',
                              chunk_size=chunk_size,
                              generic_client_kwargs={
                                  'api_endpoint': 'https://upload.invalid/api/2.0/',
                                  'username': 'fixture-user',
                                  'password': 'fixture-password',
                                  'login_method': 'basic'})
            self.addCleanup(uploader.c._session.close)
            self.addCleanup(uploader.dc.c._session.close)
            self.assertEqual(list(uploader.file_chunks()), expected_chunks)
            adapter = RecordingAdapter(statuses or [404, 201] * len(expected_chunks))
            # Keep Requests' actual Session/prepare/send and multipart encoder.
            # Replace only adapter lookup, so even module-level get/post use it.
            with patch.object(requests.Session, 'get_adapter', return_value=adapter):
                for number, offset, size in expected_chunks:
                    uploader.upload_chunk(number, offset, size)
            self.assertEqual(path.read_bytes(), payload)
            self.assertEqual(uploader.uploaded_size, 0)  # worker owns progress
            return adapter.calls

    def assert_chunks(self, payload, chunk_size, chunks):
        calls = self.exercise(payload, chunk_size, chunks)
        self.assertEqual(len(calls), 2 * len(chunks))
        reconstructed = []
        for index, (number, offset, size) in enumerate(chunks):
            get, post = calls[2 * index:2 * index + 2]
            expected_fields = {
                'resumableChunkNumber': str(number),
                'resumableChunkSize': str(chunk_size),
                'resumableTotalSize': str(len(payload)),
                'resumableIdentifier': 'image.raw',
                'resumableFilename': 'image.raw',
            }
            self.assertEqual(get.method, 'GET')
            self.assertEqual(parse_qs(urlsplit(get.url).query),
                             {k: [v] for k, v in expected_fields.items()})
            self.assertIsNone(get.body)
            self.assertEqual(post.method, 'POST')
            self.assertEqual(post.url, 'https://upload.invalid/api/2.0/drives/drive-fixture/upload/')
            self.assertEqual(get.url.split('?')[0], post.url)
            for request in (get, post):
                self.assertEqual(request.headers['User-Agent'], 'CloudSigma turlo client')
                auth = base64.b64encode(b'fixture-user:fixture-password').decode('ascii')
                self.assertEqual(request.headers['Authorization'], 'Basic ' + auth)
            self.assertIsInstance(post.body, bytes)
            self.assertEqual(int(post.headers['Content-Length']), len(post.body))
            content_type = post.headers['Content-Type']
            self.assertTrue(content_type.startswith('multipart/form-data; boundary='))
            message = BytesParser(policy=policy.default).parsebytes(
                b'Content-Type: ' + content_type.encode('ascii') + b'\r\n\r\n' + post.body)
            parts = list(message.iter_parts())
            names = [p.get_param('name', header='content-disposition') for p in parts]
            self.assertEqual(names, list(expected_fields) + ['file'])
            for part, (name, value) in zip(parts, expected_fields.items()):
                self.assertEqual(part.get_filename(), name)  # preserve legacy files= shape
                self.assertEqual(part.get_payload(decode=True), value.encode('ascii'))
            self.assertEqual(parts[-1].get_filename(), 'file')
            actual = parts[-1].get_payload(decode=True)
            expected = payload[offset:offset + size]
            self.assertEqual(actual, expected)
            self.assertNotEqual(actual, str(expected).encode('utf-8'))
            reconstructed.append(actual)
        self.assertEqual(b''.join(reconstructed), payload)

    def test_nul_invalid_utf8_and_last_merged_remainder(self):
        self.assert_chunks(b'\x00\xff\xfeABC\x80\x00\xffZ!', 4, [(1, 0, 4), (2, 4, 7)])

    def test_crlf_and_cr_exact_multiple_last_valid_chunk(self):
        self.assert_chunks(b'A\r\nB\rC\nD', 4, [(1, 0, 4), (2, 4, 4)])

    def test_multibyte_split_at_byte_boundary(self):
        self.assert_chunks('é雪🌍z'.encode('utf-8'), 3,
                           [(1, 0, 3), (2, 3, 3), (3, 6, 4)])

    def test_smaller_than_chunk(self):
        self.assert_chunks(b'\x00\xff', 8, [(1, 0, 2)])

    def test_plain_ascii(self):
        self.assert_chunks(b'plain ascii', 20, [(1, 0, 11)])

    def test_successful_probe_skips_post(self):
        calls = self.exercise(b'abc', 8, [(1, 0, 3)], [204])
        self.assertEqual([request.method for request in calls], ['GET'])

    def test_unsuccessful_post_preserves_error_policy(self):
        with self.assertRaisesRegex(Exception, 'Wrong status 500 returned for request 1:0:3'):
            self.exercise(b'abc', 8, [(1, 0, 3)], [404, 500])
