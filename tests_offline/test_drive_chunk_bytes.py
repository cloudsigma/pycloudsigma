"""Existing Drive chunk byte slicing only; no upload transport qualification."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import requests
from cloudsigma.resource import Drive


class DriveChunkBytesTests(unittest.TestCase):
    def check_chunks(self, image, size, expected):
        with tempfile.TemporaryDirectory() as directory, requests.Session() as session:
            path = Path(directory) / 'image.raw'
            path.write_bytes(image)
            drive = Drive(api_endpoint='https://fixture.invalid/api/2.0/',
                          username='fixture', password='synthetic', session=session)
            for number, chunk in enumerate(expected):
                with self.subTest(number=number), patch(
                        'cloudsigma.resource.requests.post') as post:
                    sentinel = object()
                    post.return_value = sentinel
                    result = drive.upload_chunk('/chunk-fixture/', str(path), number, size)
                    self.assertIs(result, sentinel)
                    post.assert_called_once_with(
                        'https://fixture.invalid/api/2.0/chunk-fixture/', data=chunk,
                        headers={'User-Agent': 'CloudSigma turlo client',
                                 'Content-Type': 'application/octet-stream',
                                 'Accept': 'application/json'})
                    self.assertIs(type(post.call_args.kwargs['data']), bytes)
            self.assertEqual(path.read_bytes(), image)

    def test_arbitrary_binary_merged_final_chunk(self):
        # Existing documented chunk policy: 10 bytes / 4 -> 4 then 6.
        self.check_chunks(b'\x00\xff\xfeA\x80B\x00\r\nZ', 4,
                          [b'\x00\xff\xfeA', b'\x80B\x00\r\nZ'])

    def test_newlines_not_normalized(self):
        self.check_chunks(b'A\r\nB\rC\nD', 4, [b'A\r\nB', b'\rC\nD'])

    def test_smaller_than_chunk(self):
        self.check_chunks(b'\xff\x00', 4, [b'\xff\x00'])

    def test_exact_multiple_last_valid_boundary(self):
        self.check_chunks(b'abcdefgh', 4, [b'abcd', b'efgh'])

    def test_read_failure_does_not_dispatch(self):
        with requests.Session() as session:
            drive = Drive(api_endpoint='https://fixture.invalid/api/2.0/',
                          username='fixture', password='synthetic', session=session)
            with tempfile.TemporaryDirectory() as directory, patch(
                    'cloudsigma.resource.requests.post') as post:
                with self.assertRaises(FileNotFoundError):
                    drive.upload_chunk('/chunk-fixture/', str(Path(directory)/'absent'), 0, 4)
                post.assert_not_called()
