"""Local byte fidelity only; fake opener is not provider/transport acceptance."""
import pathlib
import tempfile
from unittest import TestCase, mock
import urllib.error
import urllib.request

from cloudsigma.upload_client import CSUploader


class UploaderChunkBytesTests(TestCase):
    def make_uploader(self, path, chunk_size=4):
        uploader = CSUploader('https://example.invalid/api/2.0', str(path),
                              chunk_size, 'synthetic', 'synthetic')
        uploader.drive_url = 'https://example.invalid/api/2.0/drives/fixture/'
        uploader.size = path.stat().st_size
        return uploader

    def check_chunks(self, payload, size, chunks):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'image.raw'
            path.write_bytes(payload)
            uploader = self.make_uploader(path, size)
            self.assertEqual(list(uploader.file_chunks()), chunks)
            bodies = []
            with mock.patch.object(uploader, 'get_chunk_upload_link',
                                   return_value='/fixture-chunk') as link:
                # Real Request construction; replace only the opener send boundary.
                with mock.patch.object(uploader.opener, 'open') as urlopen:
                    for number, offset, count in chunks:
                        self.assertIsNone(uploader.upload_chunk(number, offset, count))
                        link.assert_called_with(number)
                        request = urlopen.call_args.args[0]
                        self.assertIsInstance(request, urllib.request.Request)
                        self.assertIs(type(request.data), bytes)
                        self.assertEqual(request.data, payload[offset:offset + count])
                        self.assertEqual(request.full_url, 'https://example.invalid/fixture-chunk')
                        self.assertEqual(request.get_method(), 'POST')
                        self.assertEqual(dict(request.header_items()), {
                            'Content-type': 'application/octet-stream',
                            'Accept': 'application/json'})
                        bodies.append(request.data)
                    self.assertEqual(urlopen.call_count, len(chunks))
                self.assertEqual(link.call_count, len(chunks))
            self.assertEqual(b''.join(bodies), payload)
            self.assertEqual(uploader.uploaded_size, len(payload))
            self.assertEqual(path.read_bytes(), payload)

    def test_binary_multi_chunk_merged_remainder(self):
        self.check_chunks(b'\x00\xff\xfeA\r\nB\x80C\x00D', 4,
                          [(0, 0, 4), (1, 4, 7)])

    def test_newlines_and_multibyte_byte_offsets(self):
        self.check_chunks('A\r\né\rZ\nQQ'.encode('utf-8'), 3,
                          [(0, 0, 3), (1, 3, 3), (2, 6, 4)])

    def test_exact_multiple_last_valid_chunk(self):
        self.check_chunks(b'\x00\xff\r\nAB\x80Z', 4, [(0, 0, 4), (1, 4, 4)])

    def test_smaller_than_chunk(self):
        self.check_chunks(b'\x00\xff\r\n', 16, [(0, 0, 4)])

    def test_ascii_body_is_bytes_not_text(self):
        self.check_chunks(b'plain text', 16, [(0, 0, 10)])

    def test_existing_link_error_and_skip_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'image.raw'
            path.write_bytes(b'1234')
            uploader = self.make_uploader(path)
            for code in (416, 403):
                error = urllib.error.HTTPError('https://example.invalid', code, 'fixture', {}, None)
                with mock.patch.object(uploader, 'get_chunk_upload_link', side_effect=error):
                    with mock.patch.object(uploader.opener, 'open') as urlopen:
                        if code == 416:
                            self.assertIsNone(uploader.upload_chunk(0, 0, 4))
                            self.assertEqual(uploader.uploaded_size, 4)
                        else:
                            with self.assertRaises(urllib.error.HTTPError) as caught:
                                uploader.upload_chunk(0, 0, 4)
                            self.assertIs(caught.exception, error)
                            self.assertEqual(uploader.uploaded_size, 4)
                        urlopen.assert_not_called()

    def test_send_error_does_not_advance_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'image.raw'
            path.write_bytes(b'1234')
            uploader = self.make_uploader(path)
            error = OSError('synthetic send failure')
            with mock.patch.object(uploader, 'get_chunk_upload_link', return_value='/fixture'):
                with mock.patch.object(uploader.opener, 'open', side_effect=error) as urlopen:
                    with self.assertRaises(OSError) as caught:
                        uploader.upload_chunk(0, 0, 4)
                    self.assertIs(caught.exception, error)
                    self.assertEqual(urlopen.call_count, 1)
            self.assertEqual(uploader.uploaded_size, 0)
