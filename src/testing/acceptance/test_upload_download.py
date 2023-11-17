from builtins import str
from builtins import chr
from time import sleep
import tempfile
import random
import struct
from subprocess import Popen, PIPE
import filecmp
import logging

import os
from nose.plugins.attrib import attr
from cloudsigma.errors import ClientError

import cloudsigma.resource as cr
from testing.acceptance.common import StatefulResourceTestBase
from cloudsigma.generic import GenericClient
from cloudsigma import upload_client
from testing.utils import DumpResponse


LOG = logging.getLogger(__name__)


@attr('acceptance_test')
class UploadTest(StatefulResourceTestBase):

    def setUp(self):
        super(UploadTest, self).setUp()
        gc = GenericClient()
        self.username = gc.username
        self.password = gc.password
        self.api_endpoint = gc.api_endpoint

        self.file_size = 10 * 1024 ** 2 + random.randrange(0, 1024)  # 10.something MiB
        self.file_path = self.generate_file()
        self.downloaded_path = tempfile.mktemp(prefix='test_download_')

    def del_file(self, path):
        try:
            os.remove(path)
        except OSError as exc:
            if "No such file or directory" not in exc.message:
                raise

    def generate_file(self):
        fd, path = tempfile.mkstemp(prefix='drive_upload_test')

        os.fdopen(fd).close()
        with open(path, 'r+b') as f:
            written = 0
            # write 64 bit random values
            data = struct.pack('=Q', random.randrange(0, 2 ** 64)) * 128 * 4
            while written + 1024 * 4 <= self.file_size:
                f.write(data)
                written += 1024 * 4

            # write 8 bit  random values until we reach required size
            while written < self.file_size:
                f.write(chr(random.randrange(0, 2 ** 8)).encode('latin-1'))
                written += 1

        self.addCleanup(self.del_file, path)
        return path

    def run_subprocess(self, cmd_list):
        p = Popen(cmd_list, stdout=PIPE)

        check_retry = 0
        while p.poll() is None and check_retry < 5 * 60:  # wait max 5 minutes
            sleep(5)
            check_retry += 5

        if p.poll() is None:
            p.terminate()
            return_code = None
        else:
            return_code = p.returncode
        self.assertIsNotNone(return_code, 'Subprocess did not finish in time. Return code {!r}'.format(return_code))

        p_stdout = p.stdout.read()
        p_stderr = p.stderr.read() if p.stderr else ''
        self.assertTrue(return_code == 0, 'Subprocess finished with an error. '
                                          'Return code {!r}.\nOUT:{}\nERR:{}'.format(return_code, p_stdout, p_stderr))

        return p_stdout.strip(), p_stderr.strip()

    def do_upload(self):
        client_path = upload_client.__file__
        if client_path.endswith('.pyc'):
            client_path = client_path[:-1]
        cmd_args = [
            'python', client_path, '-u', self.username, '-p', self.password,
            '-a', self.api_endpoint, '-s', str(1024 ** 2), self.file_path
        ]

        return self.run_subprocess(cmd_args)

    def do_curl_upload(self):
        from cloudsigma.conf import config
        curl_upload_endpoint = config['curl_upload_endpoint']
        cmd_args = [
            'curl',
            '-X', 'POST',
            '-u', '{}:{}'.format(self.username, self.password),
            '-H', 'Content-Type: application/octet-stream',
            '-T', self.file_path,
            '-v',
            '{}/drives/upload/'.format(curl_upload_endpoint)
        ]

        LOG.debug('cURL upload command is: {}'.format(' '.join(cmd_args)))
        return self.run_subprocess(cmd_args)

    def do_download(self, uuid):
        download_url = '{}/drives/{}/download/'.format(self.api_endpoint.rstrip('/'), uuid)
        cmd_args = [
            'curl', '-L',
            '-u', '{}:{}'.format(self.username, self.password),
            '-o', self.downloaded_path,
            '-w', '%{http_code}',
            '-r', '0-{:d}'.format(self.file_size - 1),
            '-v',
            download_url
        ]
        sleep(180)

        LOG.debug('cURL download command is: {}'.format(' '.join(cmd_args)))
        p_stdout, p_stderr = self.run_subprocess(cmd_args)
        self.addCleanup(self.del_file, self.downloaded_path)
        status = int(p_stdout)

        LOG.debug('Download finished with status {}'.format(status))
        self.assertTrue(200 <= status <= 299,
                        'Download returned an error status {}. STDERR:\n{}'.format(status, p_stderr))

    def compare_upload_and_download(self):

        downloaded_size = os.stat(self.downloaded_path).st_size
        if downloaded_size != self.file_size:
            with open(self.downloaded_path) as downloaded:
                # check zeroes till the end of file
                downloaded.seek(self.file_size)
                remaining_len = downloaded_size - self.file_size
                self.assertTrue(remaining_len > 0)
                while remaining_len - 8 >= 0:
                    value = struct.unpack('=Q', downloaded.read(8))
                    self.assertEqual(value[0], 0)
                    remaining_len -= 8

                while remaining_len > 0:
                    self.assertEqual(ord(downloaded.read(1)), 0)
                    remaining_len -= 0

                # truncate to compare with original
                downloaded.truncate(self.file_size)

        cmp_res = filecmp.cmp(self.file_path, self.downloaded_path, shallow=False)
        self.assertTrue(cmp_res, 'Uploaded and downloaded files are not the same')

    def test_upload_and_download(self):
        uuid, p_stderr = self.do_upload()
        self.addCleanup(self._clean_drives, [uuid])
        self._wait_for_status(uuid, 'unmounted', cr.Drive())
        self.do_download(uuid)
        self.compare_upload_and_download()

    def test_curl_upload_and_download(self):
        uuid, p_stderr = self.do_curl_upload()
        self.addCleanup(self._clean_drives, [uuid])
        self._wait_for_status(uuid, 'unmounted', cr.Drive())
        self.do_download(uuid)
        self.compare_upload_and_download()

    @staticmethod
    def dump_octet_stream_req(path, name, response):
        request = response.request
        req_msg = '{req.method} {req.path_url} HTTP/1.1\r\n{headers}\r\n\r\n{body}' \
                  ''.format(req=request,
                            headers='\r\n'.join('{}: {}'.format(k, v) for k, v in list(request.headers.items())),
                            body='...\r\n\r\n{disk image raw bytes}\r\n\r\n...')
        resp_msg = 'HTTP/1.1 {resp.status_code} {resp.reason}\r\n{headers}\r\n\r\n{body}' \
                   ''.format(resp=response,
                             headers='\r\n'.join('{}: {}'.format(k, v) for k, v in list(response.headers.items())),
                             body=response.content if response.content else '')

        with open(os.path.join(path, 'request_{}'.format(name)), 'w') as f:
            f.write(req_msg)

        with open(os.path.join(path, 'response_{}'.format(name)), 'w') as f:
            f.write(resp_msg)

    @attr('docs_snippets')
    def test_upload_protocol_gen_docs(self):
        iu = cr.InitUpload()
        dc = cr.Drive()
        dr = DumpResponse(clients=[iu, dc])
        with dr('init_upload'):
            drive = iu.create({'media': 'disk'}, image_path=self.file_path)
        uuid = drive['uuid']
        self.addCleanup(self._clean_drives, [uuid])
        dump_path = dr.response_dump.dump_path

        with dr('chunk_link_zero'):
            link0 = dc.get_upload_chunk_link(uuid, 0)
        with dr('chunk_link_one'):
            link1 = dc.get_upload_chunk_link(uuid, 1)

        resp = dc.upload_chunk(link0, self.file_path, 0, 5 * 1024 ** 2)
        self.dump_octet_stream_req(dump_path, 'chunk_upload_zero', resp)

        sleep(5)
        with dr('chunk_link_zero_already_uploaded'):
            with self.assertRaises(ClientError) as cm:
                dc.get_upload_chunk_link(uuid, 0)
        self.assertIn('0', cm.exception[0])
        self.assertIn('already uploaded', cm.exception[0])
        self.assertEqual(416, cm.exception[1])

        resp = dc.upload_chunk(link1, self.file_path, 1, 5 * 1024 ** 2)
        self.dump_octet_stream_req(dump_path, 'chunk_upload_one', resp)

        self._wait_for_status(uuid, 'unmounted', client=dc, transitional_states=['uploading'])
        self.do_download(uuid)
        self.compare_upload_and_download()
