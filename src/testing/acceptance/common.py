from __future__ import division
from cloudsigma.generic import GenericClient
import datetime
from cloudsigma import resource
from cloudsigma.resource import Nodes, Vpc
from unittest import SkipTest
from cloudsigma.conf import config
import logging
import time
from nose.plugins.attrib import attr
import unittest
from cloudsigma import errors
import cloudsigma.resource as cr
from past.utils import old_div
from copy import deepcopy
from future import standard_library
standard_library.install_aliases()


LOG = logging.getLogger(__name__)


@attr('acceptance_test')
class StatefulResourceTestBase(unittest.TestCase):
    TIMEOUT_DRIVE_CREATED = 2 * 60
    TIMEOUT_DRIVE_CLONING = 20 * 60
    TIMEOUT_DRIVE_DELETED = 3 * 60

    def setUp(self):
        unittest.TestCase.setUp(self)
        # Create a resource handle object
        self.client = cr.ResourceBase()
        self._clean_servers()
        self._clean_drives()

    def tearDown(self):
        self._clean_servers()
        self._clean_drives()

    def get_cpu_type(self):
        return config.get('guest_cpu_type') \
            if 'guest_cpu_type' in config else 'amd'

    def _get_persistent_image_uuid_and_pass(self):
        # Get a good persistent test image
        p_name = config.get('persistent_drive_name')
        p_pass = config.get('persistent_drive_ssh_password')

        if p_name is None:
            raise SkipTest(
                'A persistent_drive_name must be stated in the '
                'client configuration to execute this test'
            )

        def _filter_drives(av_drives):
            for drive in av_drives:
                if p_name in drive['name'] and drive['status'] in \
                        ('mounted', 'unmounted', 'cloning_src',):
                    return drive['uuid']
            return None

        puuid = _filter_drives(cr.Drive().list_detail())
        if puuid is None:
            puuid = _filter_drives(cr.LibDrive().list_detail())
            if puuid is not None:
                client_drives = cr.Drive()
                clone_drive_def = {
                    'name': p_name,
                }
                cloned_drive = client_drives.clone(puuid, clone_drive_def)
                self._wait_for_status(
                    cloned_drive['uuid'],
                    'unmounted',
                    timeout=self.TIMEOUT_DRIVE_CLONING,
                    client=client_drives
                )
                puuid = cloned_drive['uuid']

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
                self.assertGreaterEqual(
                    len(resources), 1, 'Resource listing fails'
                )
            resource_found = False
            for x in resources:
                if x['uuid'] == resource['uuid']:
                    self.assertDictContainsSubset(resource, x)
                    resource_found = True
            if should_be_found == resource_found:
                break

            self.assertLessEqual(
                count_waited,
                old_div(TIMEOUT, WAIT_STEP),
                'Resource list didn\'t update as expected for %d seconds' % (
                    TIMEOUT,
                )
            )
            time.sleep(WAIT_STEP)
            count_waited += 1

    def _wait_for_status(self, uuid, status, client=None, timeout=60):
        WAIT_STEP = 3

        if client is None:
            client = self.client

        count_waited = 0
        while True:
            resource = client.get(uuid)
            if resource['status'] == status:
                break
            self.assertLessEqual(
                count_waited,
                old_div(timeout, WAIT_STEP),
                'Resource didn\'t reach state "%s" for %d seconds' % (
                    status,
                    timeout
                )
            )
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
                if exc.status_code == 404:
                    break
                else:
                    raise
            self.assertLessEqual(
                count_waited,
                old_div(timeout, WAIT_STEP),
                'Resource did not delete %d seconds' % (timeout)
            )
            time.sleep(WAIT_STEP)
            count_waited += 1

    def _wait_for_open_socket(
            self,
            host,
            port,
            timeout=15,
            close_on_success=False
    ):
        import socket
        import time

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)

        now = time.time()
        connected = False
        while now + timeout >= time.time():
            try:
                # Check if we can connect to socket
                sock.connect((host, port))
            except:
                time.sleep(1)
            else:
                connected = True
                break

        self.assertTrue(
            connected,
            "Socket to {}:{} failed to open in {} seconds".format(
                host,
                port,
                timeout,
            )
        )

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
                # Check if we can connect to socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                sock.connect((host, port))
            except:
                closed = True
                break
            else:
                sock.close()
                time.sleep(1)
        self.assertTrue(
            closed,
            "We can still open connection to {}:{} after {} seconds".format(
                host,
                port,
                timeout,
            )
        )

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
            LOG.error(
                'The servers {} are stuck in intermediate states. '
                'Cannot remove them.'.format(inter)
            )

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
                elif status in ('unmounted', 'uploading'):
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
            LOG.error(
                'The drives {} are still mounted and cannot be deleted'.format(
                    mounted
                )
            )

        if inter:
            LOG.error(
                'The drives {} are stuck in intermediate states'
                ' and cannot be deleted.'.format(
                    inter
                )
            )

    def get_other_account(self):
        if not config.get('username2'):
            raise unittest.SkipTest('Missing second account for ACL tests')
        return dict(
            username=config['username2'], password=config['password2']
        )

    def assertDictContainsSubset(
            self, expected, actual, msg=None, exclude=None):
        if exclude is None:
            exclude = []

        expected_2 = deepcopy(expected)
        actual_2 = deepcopy(actual)
        for item in exclude:
            if item in expected_2:
                del expected_2[item]
            if item in actual_2:
                del actual_2[item]
        super(StatefulResourceTestBase, self).assertDictContainsSubset(
            expected_2, actual_2, msg)


class VpcTestsBase(StatefulResourceTestBase):

    def setUp(self):
        super(VpcTestsBase, self).setUp()
        self.vpc_client = Vpc()
        self.vpc_client_2 = Vpc(**self.get_other_account())
        self.sub_client = resource.Subscriptions()
        self.nodes_client = Nodes()
        self.resource_name = 'dedicated_host_6148'
        self.vpc_resource_name = 'vpc'
        self.DEFAULT_STATE = 'active'
        self.DEFAULT_STATUS = 'active'

    def _create_vpc_subscription(self):
        list = self.vpc_client.list()
        if len(list) == 0:
            now = datetime.datetime.now()
            future_date = now + datetime.timedelta(days=365)
            self.sub_client.create({
                "amount": "1",
                "resource": self.vpc_resource_name,
                "auto_renew": True,
                "start_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": future_date.strftime("%Y-%m-%d %H:%M:%S")})

        list = self.vpc_client.list()
        if len(list) == 0:
            SkipTest("It was not possible to create a VPC subscription")
        return list[0]

    def _create_node_subscription(self):
        list = self.nodes_client.list()
        if len(list) == 0:
            now = datetime.datetime.now()
            future_date = now + datetime.timedelta(days=365)
            self.sub_client.create({
                "amount": "1",
                "resource": self.resource_name,
                "auto_renew": True,
                "start_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": future_date.strftime("%Y-%m-%d %H:%M:%S")})

        list = self.nodes_client.list()
        if len(list) == 0:
            SkipTest("It was not possible to create a node subscription")
        return list[0]

    def _configure_vpc_and_node(self, vpc, node):
        node_in_vpc = False
        for n in vpc['nodes']:
            if n['uuid'] == node['uuid']:
                node_in_vpc = True
                break

        if not node_in_vpc:
            vpc['nodes'] = [node['uuid']]
            self.vpc_client.update(vpc['uuid'], vpc)

    def _create_subscriptions(self):
        vpc = self._create_vpc_subscription()
        node = self._create_node_subscription()
        self._configure_vpc_and_node(vpc, node)

    def check_nodes(self, vpc, expected):
        self.assertEqual(len(vpc['nodes']), len(expected))
        for node in vpc['nodes']:
            self.assertIn(node['uuid'], expected)
            n = self.nodes_client.get(node['uuid'])
            self.assertEqual(n['vpc']['uuid'], vpc['uuid'])
            self.assertEqual(n['status'], self.DEFAULT_STATUS)


def is_vpc_enabled():
    gc = GenericClient(login_method=GenericClient.LOGIN_METHOD_SESSION)
    ret = gc.get('cloud_status')
    if 'vpc' in ret:
        return ret['vpc']
    else:
        return False


def is_vpc_test_enabled():
    try:
        value = config.get('vpc_test_enabled')
        return value.lower() == 'true'
    except:
        return False


def check_if_vpc_is_enabled():
    if not is_vpc_test_enabled():
        raise SkipTest('VPC acceptance tests are disabled')

    if not is_vpc_enabled():
        raise SkipTest('VPC API calls are disabled')


def get_paas_providers():
    gc = GenericClient(login_method=GenericClient.LOGIN_METHOD_SESSION)
    ret = gc.get('cloud_status')
    if 'paas' in ret:
        return ret['paas']
    else:
        return []
