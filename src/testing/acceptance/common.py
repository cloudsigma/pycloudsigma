__author__ = 'islavov'
import cloudsigma.resource as cr
import cloudsigma.errors as errors
import unittest
from nose.plugins.attrib import attr
import time
import logging
from cloudsigma.conf import config
from unittest import SkipTest

LOG = logging.getLogger(__name__)


@attr('acceptance_test')
class StatefulResourceTestBase(unittest.TestCase):
    TIMEOUT_DRIVE_CLONING = 20*60
    TIMEOUT_DRIVE_DELETED = 3*60

    def setUp(self):
        unittest.TestCase.setUp(self)
        self.client = cr.ResourceBase()            # create a resource handle object
        self._clean_servers()
        self._clean_drives()

    def tearDown(self):
        self._clean_servers()
        self._clean_drives()

    def _get_persistent_image_uuid_and_pass(self):
        # Get a good persistant test image
        p_name = config.get('persistent_drive_name')
        p_pass = config.get('persistent_drive_ssh_password')

        if p_name is None:
            raise SkipTest('A persistent_drive_name must be stated in the client configuration to execute this test')

        puuid = None
        av_drives = cr.Drive().list_detail()
        for drive in av_drives:
            if p_name in drive['name']:
                puuid = drive['uuid']
                break

        if puuid is None:
            raise SkipTest("There is no drive matching {}".format(p_name))
        return puuid, p_pass

    def _get_persistent_image_uuid_and_pass(self):
        # Get a good persistant test image
        p_name = config.get('persistent_drive_name')
        p_pass = config.get('persistent_drive_ssh_password')

        if p_name is None:
            raise SkipTest('A persistent_drive_name must be stated in the client configuration to execute this test')

        puuid = None
        av_drives = cr.Drive().list_detail()
        for drive in av_drives:
            if drive['name'].startswith(p_name) or p_name == drive['uuid']:
                puuid = drive['uuid']
                LOG.debug('Drive %r selected for persistent image', drive)
                break

        if puuid is None:
            raise SkipTest("There is no drive matching {}".format(p_name))
        return puuid, p_pass

    def _verify_list(self, resource, should_be_found, client=None):
        TIMEOUT = 20
        WAIT_STEP = 3

        if client is None:
            client = self.client

        count_waited = 0
        while True:
            resources = client.list_detail()
            if should_be_found:
                self.assertGreaterEqual(len(resources), 1, 'Resource listing fails')
            resource_found = False
            for x in resources:
                if x['uuid'] == resource['uuid']:
                    self.assertDictContainsSubset(resource, x)
                    resource_found = True
            if should_be_found == resource_found:
                break

            self.assertLessEqual(count_waited, TIMEOUT/WAIT_STEP, 'Resource list didn\'t update as expected for %d seconds' % (TIMEOUT,))
            time.sleep(WAIT_STEP)
            count_waited += 1

    def _wait_for_status(self, uuid, status, client=None, timeout=40):
        WAIT_STEP = 3

        if client is None:
            client = self.client

        count_waited = 0
        while True:
            resource = client.get(uuid)
            if resource['status'] == status:
                break
            self.assertLessEqual(count_waited, timeout/WAIT_STEP, 'Resource didn\'t reach state "%s" for %d seconds' % (status, timeout))
            time.sleep(WAIT_STEP)
            count_waited += 1

    def _wait_deleted(self, uuid, client=None, timeout=TIMEOUT_DRIVE_DELETED):
        WAIT_STEP = 3

        if client is None:
            client = self.client

        count_waited = 0
        while True:
            try:
                client.get(uuid)
            except errors.ClientError as exc:
                if exc[0] == 404:
                    break
                else:
                    raise
            self.assertLessEqual(count_waited, timeout/WAIT_STEP, 'Resource did not delete %d seconds' % (timeout))
            time.sleep(WAIT_STEP)
            count_waited += 1

    def _wait_for_open_socket(self, host, port, timeout=15, close_on_success=False):
        import socket
        import time

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)

        now = time.time()
        connected = False
        while now + timeout >= time.time():
            try:
                #Check if we can connect to socket
                sock.connect((host, port))
            except:
                time.sleep(1)
            else:
                connected = True
                break

        self.assertTrue(connected, "Socket to {}:{} failed to open in {} seconds".format(
            host,
            port,
            timeout,
        ))

        if close_on_success:
            sock.close()

        return sock

    def _wait_socket_close(self, host, port, timeout=15):
        import socket
        import time

        now = time.time()
        closed = False
        while now + timeout >= time.time():
            try:
                #Check if we can connect to socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                sock.connect((host, port))
            except:
                closed = True
                break
            else:
                sock.close()
                time.sleep(1)
        self.assertTrue(closed, "We can still open connection to {}:{} after {} seconds".format(
            host,
            port,
            timeout,
        ))

    def _clean_servers(self):
        """
        Removes all the servers in the acceptance test account ( containing 'test' keyword )

        :return:
        """
        server_client = cr.Server()

        stopping = []
        deleting = []
        inter = []
        for server in server_client.list_detail():
            if 'test' in server['name']:
                status = server['status']
                if status == 'running':
                    server_client.stop(server['uuid'])
                    stopping.append(server['uuid'])
                elif status == 'stopped':
                    server_client.delete(server['uuid'])
                    deleting.append(server['uuid'])
                else:
                    inter.append(server['uuid'])

        for uuid in stopping:
            try:
                self._wait_for_status(uuid, 'stopped', client=server_client)
            except:
                LOG.exception("Server {} did not stop in time".format(uuid))
            else:

                server_client.delete(uuid)
                deleting.append(uuid)

        for uuid in deleting:
            try:
                self._wait_deleted(uuid, client=server_client)
            except:
                LOG.exception("Server {} did not delete in time".format(uuid))

        if len(inter) != 0:
            LOG.error('The servers {} are stuck in intermediate states. Cannot remove them.'.format(inter))

    def _clean_drives(self):
        """
        Removes all the drives in the acceptance test account ( containing 'test' keyword )

        :return:
        """
        drive_client = cr.Drive()

        mounted = []
        deleting = []
        inter = []
        for drive in drive_client.list_detail():
            if 'test' in drive['name']:
                status = drive['status']
                if status == 'mounted':
                    mounted.append(drive['uuid'])
                elif status == 'unmounted':
                    drive_client.delete(drive['uuid'])
                    deleting.append(drive['uuid'])
                else:
                    inter.append(drive['uuid'])

        for uuid in deleting:
            try:
                self._wait_deleted(uuid, client=drive_client)
            except:
                LOG.exception("Drive {} did not delete in time".format(uuid))

        if mounted:
            LOG.error('The drives {} are still mounted and cannot be deleted'.format(mounted))

        if inter:
            LOG.error('The drives {} are stuck in intermediate states and cannot be deleted.'.format(inter))
