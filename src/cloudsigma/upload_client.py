from __future__ import division
from future import standard_library
standard_library.install_aliases()
from builtins import str
from builtins import next
from builtins import range
from builtins import object
from past.utils import old_div
import time
import urllib.request, urllib.error, urllib.parse
import argparse
import threading
import queue
import sys
import datetime
import urllib.parse
import logging
import itertools
import json

import os


LOG = logging.getLogger(__name__)

INIT_HEADERS = {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

UPLOAD_HEADERS = {
    'Content-Type': 'application/octet-stream',
    'Accept': 'application/json'
}


class UploadError(Exception):
    pass


def console_progress():
    spinner_pos = itertools.cycle(range(3))

    def output_progress(uploaded, total):
        pos_char = {0: '/', 1: '-', 2: '\\'}
        progress = '{uploaded:0.1f} of {total:0.1f} MB ({percent:.0%})'.format(uploaded=old_div(uploaded, 1024.0 ** 2),
                                                                               total=old_div(total, 1024.0 ** 2),
                                                                               percent=old_div(1.0 * uploaded, total))
        sys.stderr.write('\r{progress} {spinner}'.format(progress=progress, spinner=pos_char[next(spinner_pos) % 3]))
        sys.stderr.flush()

    return output_progress


class CSUploader(object):

    def __init__(self, api_url, image_path, chunk_size, username, password, uuid=None,
                 n_threads=5, progress_callback=None):
        self.api_url = api_url
        self.image_path = image_path
        self.chunk_size = chunk_size
        self.username = username
        self.password = password
        self.uuid = uuid
        self.drive_url = None
        self.n_threads = n_threads
        self.progress_callback = progress_callback
        self.queue = queue.Queue()
        self.spinner_pos = 0
        self.opener = self.init_auth()

        self.progress_lock = threading.RLock()
        self.uploaded_size = 0

    def start(self):
        self.init_drive_url_or_create_drive()
        LOG.info('Uploading {image_path} to {drive_url}'.format(drive_url=self.drive_url, image_path=self.image_path))
        LOG.info('Total size is {size:0.1f} MB. '
                 'Number of chunks {n_chunks}.'.format(size=old_div(self.size, 1024.0 ** 2),
                                                       n_chunks=self.size // self.chunk_size))

        self.enqueue_chunks()

        watcher_t = threading.Thread(target=self.queue.join)
        watcher_t.setDaemon(True)
        watcher_t.start()

        self.start_threads()

        while watcher_t.isAlive():
            self.report_progress()
            time.sleep(0.5)
        self.report_progress()

        return self.uuid

    def init_drive_url_or_create_drive(self):
        self.size = os.path.getsize(self.image_path)
        if self.uuid:
            LOG.info('Resuming upload for drive {}'.format(self.uuid))
            self.drive_url = '{}/drives/{}/'.format(self.api_url.rstrip('/'), self.uuid)
            remote_size = self.get_drive_size()
            if self.size != remote_size:
                raise UploadError('Image file size {} differs from drive size {}'.format(self.size, remote_size))
        else:
            self.uuid = self.init_upload()
            LOG.info('Initialized an upload for drive with {uuid}.'.format(uuid=self.uuid))
            self.drive_url = '{}/drives/{}/'.format(self.api_url.rstrip('/'), self.uuid)

    def init_upload(self, media='disk'):
        url = '{}/initupload/'.format(self.api_url.rstrip('/'))
        data = {
            'name': 'Upload_{:%Y-%m-%d %H:%M:%S}'.format(datetime.datetime.utcnow()),
            'size': self.size,
            'media': media
        }
        str_data = json.dumps(data)
        req = urllib.request.Request(url, data=str_data, headers=INIT_HEADERS)
        response = self.opener.open(req)
        status = response.getcode()
        body = response.read()
        if not 200 <= status <= 299:
            raise UploadError('Wrong response status code {}. Response was {}'.format(status, body))
        response_data = json.loads(body)

        return response_data['objects'][0]['uuid']

    def file_chunks(self):
        """
        Yields tuples (chunk_number, chunk_offset, real_chunk_size).

        ``chunk_number`` is the number of the chunk. Numbering starts from 1.
        ``chunk_offset`` can be used to seek in the file.
        ``real_chunk_size`` is necessary because the last chunk is bigger

        :return: yields (chunk_number, chunk_offset, real_chunk_size) tuples
        """
        n_chunks = self.size // self.chunk_size
        if n_chunks > 0:
            for chunk in range(n_chunks - 1):  # excludes las chunk and starts from 1. last chunk is bigger
                offset = chunk * self.chunk_size
                yield chunk, offset, self.chunk_size

            last_chunk = n_chunks - 1
            last_offset = last_chunk * self.chunk_size
            last_chunk_size = self.size - last_offset

            yield last_chunk, last_offset, last_chunk_size
        else:  # chunk size bigger than file size
            yield 0, 0, self.size

    def enqueue_chunks(self):
        for chunk_number, chunk_offset, real_chunk_size in self.file_chunks():
            self.queue.put((chunk_number, chunk_offset, real_chunk_size))

    def get_drive_size(self):
        req = urllib.request.Request(self.drive_url, headers=INIT_HEADERS)
        response = self.opener.open(req)
        return int(json.loads(response.read())['size'])

    def start_threads(self):
        for _ in range(self.n_threads):
            download_thread = threading.Thread(target=self.upload_enqueued)
            download_thread.setDaemon(True)
            download_thread.start()

    def upload_enqueued(self):
        while True:
            chunk_number, chunk_offset, real_chunk_size = self.queue.get()
            try:
                self.upload_chunk(chunk_number, chunk_offset, real_chunk_size)
            except:
                LOG.exception('Error ocurred for chunk {}'.format(chunk_number))
                self.queue.put((chunk_number, chunk_offset, real_chunk_size))
            finally:
                # Always call task_done even on fail because in order to finish the number of put calls should be
                # equal to task_done calls
                self.queue.task_done()

    def upload_chunk(self, chunk_number, chunk_offset, real_chunk_size):
        try:
            rel_url = self.get_chunk_upload_link(chunk_number)
        except urllib.error.HTTPError as exc:
            if exc.code != 416:
                raise
            LOG.info('skipping chunk {} because it is already uploaded'.format(chunk_number))
            self.update_progress(real_chunk_size)
            return
        parsed = urllib.parse.urlparse(self.drive_url)
        upload_url = '{}://{}/{}'.format(parsed.scheme, parsed.hostname, rel_url.lstrip('/'))
        with open(self.image_path, 'r') as f:
            f.seek(chunk_offset)
            data = f.read(real_chunk_size)
            req = urllib.request.Request(str(upload_url), str(data), headers=UPLOAD_HEADERS)
            self.opener.open(req)
        self.update_progress(real_chunk_size)

    def report_progress(self):
        if self.progress_callback:
            self.progress_callback(self.uploaded_size, self.size)

    def update_progress(self, uploaded_size):
        self.progress_lock.acquire()
        self.uploaded_size += uploaded_size
        self.progress_lock.release()

    def get_chunk_upload_link(self, chunk_number):
        url = '{drive_url}/action/?do=upload_chunk'.format(drive_url=self.drive_url.rstrip('/'))
        data = json.dumps({'chunk_number': chunk_number, 'chunk_size': self.chunk_size})
        req = urllib.request.Request(url, data, headers=INIT_HEADERS)
        self.opener = self.init_auth()
        response = self.opener.open(req)
        response_data = json.loads(response.read())

        return response_data['link']

    def init_auth(self):
        password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        password_mgr.add_password(None, self.api_url, self.username, self.password)
        handler = urllib.request.HTTPBasicAuthHandler(password_mgr)
        return urllib.request.build_opener(handler)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Upload a disk image to CloudSigma drive.')
    parser.add_argument('disk_image', help='Disk image in RAW format.')
    parser.add_argument('drive_uuid', nargs='?', default=None,
                        help='UUID of an already initialized upload. Specify UUID to resume upload.'
                             'If skipped a new drive will be created.')
    parser.add_argument('-a', '--api_url',
                        help='API URL of the drives list. For example: '
                             'https://lvs.cloudsigma.com/api/2.0/', )

    parser.add_argument('-s', '--chunk-size', help='Size of the chunk. Default is 10MB.', type=int,
                        default=10 * 1024 ** 2)
    parser.add_argument('-u', '--username', help='Username (email) of the CloudSigma user.')
    parser.add_argument('-p', '--password', help='Password of the CloudSigma user.')
    args = parser.parse_args()

    api_url = args.api_url

    image_path = args.disk_image
    chunk_size = args.chunk_size
    username = args.username
    password = args.password
    uuid = args.drive_uuid

    logging.basicConfig(format='%(message)s', level=logging.INFO)

    # Register a SIGINT handler so that the upload can be killed with CTRL+C
    import signal

    def handler(signum, frame):
        LOG.info('Interrupted by user')
        sys.exit(1)

    signal.signal(signal.SIGINT, handler)

    try:
        uploader = CSUploader(api_url, image_path, chunk_size, username, password, uuid,
                              progress_callback=console_progress())
        res = uploader.start()
    except:
        LOG.exception('Error')
        sys.exit(1)

    LOG.info('\nUpload finished successfully')

    print(res)
    sys.exit()
