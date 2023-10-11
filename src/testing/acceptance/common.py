from __future__ import division
from past.utils import old_div
import cloudsigma.resource as cr
from cloudsigma import errors
import unittest
from nose.plugins.attrib import attr
import time
import logging
from cloudsigma.conf import config
from unittest import SkipTest
from cloudsigma.resource import Nodes, Vpc
from cloudsigma import resource
import datetime
import requests
import copy
from copy import deepcopy
import simplejson
from future.moves.urllib.parse import urlparse

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


def wrap_with_log_hook(log_level, next_hook=None):
    if not next_hook:  # noop next hook
        next_hook = lambda r, *args, **kwargs: None

    if not log_level:  # no log level so no logging, just return next hook
        return next_hook

    level = getattr(logging, log_level, None)
    if not level:
        LOG.error('Wrong log_lgevel {}'.format(log_level))
        return next_hook

    def log_hook(response, *args, **kwargs):
        request = response.request
        req_msg = '-----RECONSTRUCTED-REQUEST:\n' \
                  '{req.method} {req.path_url} HTTP/1.1\r\n{headers}\r\n\r\n{body}' \
                  '\n-----RECONSTRUCTED-REQUEST-END'.format(req=request,
                                                            headers='\r\n'.join('{}: {}'.format(k, v)
                                                                                for k, v
                                                                                in request.headers.items()),
                                                            body=request.body if request.body else '')
        resp_msg = '-----RECONSTRUCTED-RESPONSE:\n' \
                   'HTTP/1.1 {resp.status_code} {resp.reason}\r\n{headers}\r\n\r\n{body}' \
                   '\n-----RECONSTRUCTED-RESPONSE-END'.format(resp=response,
                                                              headers='\r\n'.join('{}: {}'.format(k, v)
                                                                                  for k, v
                                                                                  in response.headers.items()),
                                                              body=response.content if response.content else '')
        LOG.log(level, '{}\n\n{}'.format(req_msg, resp_msg))

        next_hook(response, *args, **kwargs)
    return log_hook


@attr('acceptance_test')
class StatefulResourceTestBase(unittest.TestCase):
    TIMEOUT_DRIVE_CREATED = 2 * 60
    TIMEOUT_DRIVE_CLONING = 20 * 60
    TIMEOUT_DRIVE_DELETED = 3 * 60

    def setUp(self):
        unittest.TestCase.setUp(self)
        self.client = cr.ResourceBase()  # create a resource handle object
        self._clean_servers()
        self._clean_drives()
        self._clean_keypairs(ignore_errors=True)
        self._clean_tags(ignore_errors=True)
        self._clean_acls(ignore_errors=True)

    def tearDown(self):
        self._clean_servers()
        self._clean_drives()
        self._clean_keypairs(ignore_errors=True)
        self._clean_tags(ignore_errors=True)
        self._clean_acls(ignore_errors=True)

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


class GenericClient(object):

    """Handles all low level HTTP, authentication, parsing and error handling.
    """
    LOGIN_METHOD_BASIC = 'basic'
    LOGIN_METHOD_SESSION = 'session'
    LOGIN_METHOD_NONE = 'none'
    LOGIN_METHODS = (
        LOGIN_METHOD_BASIC,
        LOGIN_METHOD_SESSION,
        LOGIN_METHOD_NONE,
    )

    def __init__(self, api_endpoint=None, username=None, password=None, login_method=LOGIN_METHOD_BASIC,
                 request_log_level=None):
        try:
            self.api_endpoint = api_endpoint if api_endpoint else config['api_endpoint']
            self.username = username if username else config['username']
            self.password = password if password else config['password']
            self.login_method = config.get('login_method', login_method)
            assert self.login_method in self.LOGIN_METHODS, 'Invalid value %r for login_method' % (login_method,)

            self._session = None
            self.resp = None
            self.response_hook = None
            self.request_log_level = request_log_level if request_log_level else config.get('request_log_level', None)
            if self.request_log_level:
                self.request_log_level = self.request_log_level.upper()

            if login_method == self.LOGIN_METHOD_SESSION:
                self._login_session()
        except KeyError as exc:
            raise errors.ClientConfigError(
                'Missing key {!r} from configuration file {}'.format(exc.message, config.filename)
            )

    def _login_session(self):
        self.login_method = self.LOGIN_METHOD_SESSION
        self._session = requests.Session()
        full_url = self._get_full_url('/accounts/action/')
        kwargs = self._get_req_args(query_params={'do': 'login'})
        data = simplejson.dumps({"username": self.username, "password": self.password})
        res = self.http.post(full_url, data=data, **kwargs)
        self._process_response(res)
        csrf_token = res.cookies['csrftoken']
        self._session.headers.update({'X-CSRFToken': csrf_token, 'Referer': self._get_full_url('/')})

    def _get_full_url(self, url):
        api_endpoint = urlparse.urlparse(self.api_endpoint)
        if url.startswith(api_endpoint.path):
            full_url = list(api_endpoint)
            full_url[2] = url
            full_url = urlparse.urlunparse(full_url)
        else:
            if url[0] == '/':
                url = url[1:]
            full_url = urlparse.urljoin(self.api_endpoint, url)

        if not full_url.endswith("/"):
            full_url += "/"

        return full_url

    def _process_response(self, resp, return_list=False):
        resp_data = None
        request_id = resp.headers.get('X-REQUEST-ID', None)
        if resp.status_code in (200, 201, 202):
            resp_data = copy.deepcopy(resp.json())
            if 'objects' in resp_data:
                resp_data = resp_data['objects']
                if len(resp_data) == 1 and not return_list:
                    resp_data = resp_data[0]
        elif resp.status_code == 401:
            raise errors.AuthError(request_id, status_code=resp.status_code)
        elif resp.status_code == 403:
            raise errors.PermissionError(resp.text, status_code=resp.status_code, request_id=request_id)
        elif resp.status_code / 100 == 4:
            raise errors.ClientError(resp.text, status_code=resp.status_code, request_id=request_id)
        elif resp.status_code / 100 == 5:
            raise errors.ServerError(resp.text, status_code=resp.status_code, request_id=request_id)

        return resp_data

    def _get_req_args(self, body=None, query_params=None):
        kwargs = {}
        if self.login_method == self.LOGIN_METHOD_BASIC:
            kwargs['auth'] = (self.username, self.password)

        kwargs['headers'] = {
            'content-type': 'application/json',
            'user-agent': 'CloudSigma turlo client',
        }

        if query_params:
            if 'params' not in kwargs:
                kwargs['params'] = {}
            kwargs['params'].update(query_params)

        kwargs['hooks'] = {
            'response': wrap_with_log_hook(self.request_log_level, self.response_hook)
        }

        return kwargs

    @property
    def http(self):
        if self._session:
            return self._session
        return requests

    def get(self, url, query_params=None, return_list=False):
        kwargs = self._get_req_args(query_params=query_params)
        self.resp = self.http.get(self._get_full_url(url), **kwargs)
        return self._process_response(self.resp, return_list)

    def put(self, url, data, query_params=None, return_list=False):
        kwargs = self._get_req_args(body=data, query_params=query_params)
        self.resp = self.http.put(self._get_full_url(url), data=simplejson.dumps(data), **kwargs)
        return self._process_response(self.resp, return_list)

    def post(self, url, data, query_params=None, return_list=False):
        kwargs = self._get_req_args(body=data, query_params=query_params)
        self.resp = self.http.post(self._get_full_url(url), data=simplejson.dumps(data), **kwargs)
        return self._process_response(self.resp, return_list)

    def delete(self, url, query_params=None):
        self.resp = self.http.delete(self._get_full_url(url), **self._get_req_args(query_params=query_params))
        return self._process_response(self.resp)


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
