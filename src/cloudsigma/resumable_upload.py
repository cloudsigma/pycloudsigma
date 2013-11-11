import requests
import os
import datetime
import Queue
import threading
import time
from logging import getLogger

from .resource import Drive, ResourceBase

LOG = getLogger(__name__)

class Upload(ResourceBase):
    resource_name = 'initupload'

    def __init__(self, image_path, drive_uuid=None, chunk_size=5*1024**2, n_threads=4,
                 drive_name=None, drive_media='disk', progress_callback=None, progress_report_interval=1,
                 generic_client_kwargs=None):
        """
        A python implementation of the resummable.js protocol.

        :param image_path:
            An absolute path to the drive image to be uploaded
        :param drive_uuid:
            If given will try to resume the upload to the given drive uuid
        :param chunk_size:
            The size of the chunk in bytes. Default is 5MB.
        :param n_threads:
            Number of parallel upload threads. Default is 4.
        :param drive_name
            The name of the uploaded drive. If not givent it will be set to Upload_<current date time>
        :param drive_media:
                The media of the uploaded drive. If not givent it will be set to "disk"
        :param progress_callback:
            A callback to be called every *progress_report_interval* second with the current progress.
            progress_callback(self.uploaded_size, self.file_size)
        :param progress_report_interval:
            Seconds between *progress_callback* calls. Default is 1 second.
        :param generic_client_kwars:
            Keyword arguments for the GeneriClient __init__
        :return:
        """
        self.generic_client_kwargs = generic_client_kwargs or {}
        super(Upload, self).__init__(**self.generic_client_kwargs)
        self.drive_uuid = drive_uuid
        self._drive_size = None
        self.image_path = image_path
        self.chunk_size = chunk_size
        self.n_threads = n_threads
        self.file_size = os.path.getsize(self.image_path)
        self.create_data = {
            'name': drive_name or 'Upload_{:%Y-%m-%d %H:%M:%S}'.format(datetime.datetime.utcnow()),
            'media': drive_media,
            'size': self.file_size
        }
        self.dc = Drive(**self.generic_client_kwargs)
        self.queue = Queue.Queue()
        self.finished = False
        self.progress_lock = threading.RLock()
        self.uploaded_size = 0
        self.progress_callback = progress_callback
        self.progress_report_interval=progress_report_interval

    @property
    def remote_size(self):
        if self._drive_size:
            return self._drive_size

        drive = self.dc.get(self.drive_uuid)
        self._drive_size = drive['size']

        return self._drive_size

    def upload(self):
        if not self.drive_uuid:
            drive = self.create(self.create_data)
            self.drive_uuid = drive['uuid']

        if self.remote_size != self.file_size:
            raise ValueError('File {} has different size from remote drive {}:'
                             ' {} != {}'.format(self.image_path, self.drive_uuid, self.file_size, self.remote_size))

        self.enqueue_chunks()

        watcher_t = threading.Thread(target=self.queue.join)
        watcher_t.setDaemon(True)
        watcher_t.start()

        self.start_threads()

        LOG.debug('waiting for queue to finish')
        while watcher_t.isAlive():
            self.report_progress()
            time.sleep(self.progress_report_interval)
        self.report_progress()

        LOG.debug('queue to finished')

    def retry(self):
        self.uploaded_size = 0
        self.upload()

    def file_chunks(self):
        """
        Yields tuples (chunk_number, chunk_offset, real_chunk_size).

        ``chunk_number`` is the number of the chunk. Numbering starts from 1.
        ``chunk_offset`` can be used to seek in the file.
        ``real_chunk_size`` is necessary because the last chunk is bigger

        :return: yields (chunk_number, chunk_offset, real_chunk_size) tuples
        """
        n_chunks = self.file_size // self.chunk_size
        if n_chunks > 0:
            for chunk in xrange(n_chunks - 1):  # excludes last chunk and starts from 1. last chunk is bigger
                offset = chunk * self.chunk_size
                yield chunk+1, offset, self.chunk_size

            last_chunk = n_chunks - 1
            last_offset = last_chunk * self.chunk_size
            last_chunk_size = self.file_size - last_offset

            yield last_chunk+1, last_offset, last_chunk_size
        else:  # chunk size bigger than file size
            yield 1, 0, self.file_size

    def enqueue_chunks(self):
        for chunk_number, chunk_offset, real_chunk_size in self.file_chunks():
            self.queue.put((chunk_number, chunk_offset, real_chunk_size))

    def start_threads(self):
        for _ in xrange(self.n_threads):
            download_thread = threading.Thread(target=self.upload_enqueued)
            download_thread.setDaemon(True)
            download_thread.start()

    def upload_enqueued(self):
        while not self.finished:
            chunk_number, chunk_offset, real_chunk_size = self.queue.get()
            try:
                LOG.debug('Uploading chunk {}:{}:{}'.format(chunk_number, chunk_offset, real_chunk_size))
                self.upload_chunk(chunk_number, chunk_offset, real_chunk_size)
                self.update_progress(real_chunk_size)
            except:
                LOG.exception('Error ocurred for chunk {}'.format(chunk_number))
                self.queue.put((chunk_number, chunk_offset, real_chunk_size))
            finally:
                # Always call task_done even on fail because in order to finish the number of put calls should be
                # equal to task_done calls
                self.queue.task_done()



    def upload_chunk(self, chunk_number, chunk_offset, real_chunk_size):
        upload_url = self.c._get_full_url('/{}/{}/upload/'.format('drives', self.drive_uuid))
        with open(self.image_path, 'r') as f:
            f.seek(chunk_offset)
            file_data = f.read(real_chunk_size)
            # do str() on numbers because requests multipart encoding assumes integers are file descriptors
            resumable_js_data = {'resumableChunkNumber': str(chunk_number),
                                 'resumableChunkSize': str(self.chunk_size),
                                 'resumableTotalSize': str(self.file_size),
                                 'resumableIdentifier': os.path.split(self.image_path)[1],
                                 'resumableFilename': os.path.split(self.image_path)[1],
                                 }

            kwargs = {
                'auth': (self.c.username, self.c.password),
                'headers': {
                    'user-agent': 'CloudSigma turlo client',
                }
            }


            res = requests.get(upload_url, params=resumable_js_data, **kwargs)

            if 199 < res.status_code < 300:
                LOG.debug('Chunk {}:{}:{} already uploaded'.format(chunk_number, chunk_offset, real_chunk_size))
                return

            resumable_js_data_multipart = resumable_js_data.items() +[('file', str(file_data))]

            res = requests.post(upload_url, files=resumable_js_data_multipart, **kwargs)
            if 199 < res.status_code < 300:
                LOG.debug('Chunk {}:{}:{} finished uploading'.format(chunk_number, chunk_offset, real_chunk_size))
                return
            else:
                raise Exception('Wrong status {} returned for request '
                                '{}:{}:{}. Response body is:'
                                '\n{}'.format(res.status_code, chunk_number, chunk_offset, real_chunk_size, res.text))


    def update_progress(self, uploaded_size):
        self.progress_lock.acquire()
        self.uploaded_size += uploaded_size
        self.progress_lock.release()

    def report_progress(self):
        if self.progress_callback:
            self.progress_callback(self.uploaded_size, self.file_size)
