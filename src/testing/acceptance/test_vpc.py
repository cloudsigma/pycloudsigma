import datetime
import time
from nose.plugins.attrib import attr
from cloudsigma.errors import ClientError
from cloudsigma import resource
from cloudsigma.resource import Nodes
from testing.acceptance.common import VpcTestsBase, check_if_vpc_is_enabled


class VpcTest(VpcTestsBase):

    def setUp(self):
        super(VpcTest, self).setUp()
        self.sub_client = resource.Subscriptions()
        self.tag_resource =  resource.Tags()
        self.acl_resource =  resource.Acls()
        self.server_client = resource.Server()
        self.nodes_client = Nodes()
        self.resource_name = 'dedicated_host_6148'

    @attr('docs_snippets')
    def test_get_vpc_schema(self):
        check_if_vpc_is_enabled()
        self.vpc_client.get_schema()

    @attr('docs_snippets')
    def test_vpc_subscription_1_month_minimum(self):
        check_if_vpc_is_enabled()
        now = datetime.datetime.now()
        future_date = now + datetime.timedelta(days=27)
        with self.assertRaises(ClientError) as ce:
            self.sub_client.create({
                "amount": "1",
                "resource": self.vpc_resource_name,
                "auto_renew": True,
                "start_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": future_date.strftime("%Y-%m-%d %H:%M:%S")})
        self.assertEqual(ce.exception.status_code, 400)

    @attr('docs_snippets')
    def test_vpc_basic_actions_listing_and_get_update(self):
        check_if_vpc_is_enabled()
        self._create_subscriptions()
        res = self.vpc_client.list()
        vpc_0 = res[0]

        node = self.nodes_client.list()
        node_0 = node[0]

        node_uuid = node_0['uuid']
        vpc_uuid = vpc_0['uuid']
        self.vpc_client.get(vpc_uuid)

        vpc_name = 'my vpc {}'.format(time.time())
        vpc_description = 'some custom description {}'.format(time.time())
        vpc = self.vpc_client.update(vpc_uuid, {'name': vpc_name, 'description': vpc_description})
        self.check_nodes(vpc, [node_uuid])

        self.assertEqual(vpc['name'], vpc_name)
        self.assertEqual(vpc['description'], vpc_description)
        self.assertEqual(vpc['status'], self.DEFAULT_STATUS)

        vpc_name = 'my vpc {}'.format(time.time())
        vpc_description = 'some custom description {}'.format(time.time())
        vpc = self.vpc_client.update(vpc_uuid, {'name': vpc_name, 'description': vpc_description, 'nodes':[]})
        self.check_nodes(vpc, [])

        self.assertEqual(vpc['name'], vpc_name)
        self.assertEqual(vpc['description'], vpc_description)
        self.assertEqual(vpc['status'], self.DEFAULT_STATUS)

        vpc_name = 'my vpc {}'.format(time.time())
        vpc_description = 'some custom description {}'.format(time.time())
        vpc = self.vpc_client.update(vpc_uuid, {'name': vpc_name,
                                                'description': vpc_description,
                                                'nodes': vpc_0['nodes']})

        self.assertEqual(vpc['name'], vpc_name)
        self.assertEqual(vpc['description'], vpc_description)
        self.assertEqual(vpc['status'], self.DEFAULT_STATUS)
        self.check_nodes(vpc, [node_uuid])

    @attr('docs_snippets')
    def test_set_invalid_fields(self):
        check_if_vpc_is_enabled()
        self._create_subscriptions()
        res = self.vpc_client.list()
        vpc_0 = res[0]

        vpc_uuid = vpc_0['uuid']
        allocation_pool = "testing_host"
        vpc_name = 'my vpc {}'.format(time.time())
        vpc_description = 'some custom description {}'.format(time.time())
        vpc = self.vpc_client.update(
            vpc_uuid,
            {'name': vpc_name, 'description': vpc_description, 'allocation_pool': allocation_pool})

        self.assertEqual(vpc['allocation_pool'], vpc_0['allocation_pool'])

        vpc_name = 'my vpc {}'.format(time.time())
        vpc_description = 'some custom description {}'.format(time.time())
        vpc['name'] = vpc_name
        vpc['description'] = vpc_description
        vpc['status'] = 'unassigned'

        vpc = self.vpc_client.update(vpc_uuid, vpc)
        self.assertEqual(vpc['name'], vpc_name)
        self.assertEqual(vpc['description'], vpc_description)
        self.assertEqual(vpc['status'], self.DEFAULT_STATUS)

    @attr('docs_snippets')
    def test_set_acl(self):
        check_if_vpc_is_enabled()
        self._create_subscriptions()
        tag, acl = self.create_tag_with_permissions('shared')
        res = self.vpc_client.list()

        vpc = res[0]
        vpc['tags'] = [tag['uuid'], ]
        vpc = self.vpc_client.update(vpc['uuid'], vpc)

        list = self.vpc_client_2.list()
        self.assertEqual(len(list), 1)
        vpc_2 = list[0]
        self.assertEqual(vpc['owner']['uuid'], vpc_2['owner']['uuid'])
        self.assertEqual(vpc['status'], self.DEFAULT_STATUS)

        vpc['tags'] = [ ]
        vpc = self.vpc_client.update(vpc['uuid'], vpc)

        list = self.vpc_client_2.list()
        self.assertEqual(len(list), 0)

        self.tag_resource.delete(tag['uuid'])
        self.acl_resource.delete(acl['uuid'])

    @attr('docs_snippets')
    def test_nodes_cycles(self):
        check_if_vpc_is_enabled()
        self._create_subscriptions()

        nodes = self.nodes_client.list()
        node_0 = nodes[0]
        res = self.vpc_client.list()

        vpc_uuid = res[0]['uuid']
        self.vpc_client.get(vpc_uuid)

        vpc_name = 'my vpc {}'.format(time.time())
        vpc_description = 'some custom description {}'.format(time.time())
        update_data = {
            'name': vpc_name,
            'description': vpc_description,
            'nodes': [nodes[0]['uuid']]
        }
        vpc = self.vpc_client.update(vpc_uuid, update_data)

        self.assertEqual(vpc['name'], vpc_name)
        self.assertEqual(vpc['description'], vpc_description)
        self.assertEqual(vpc['status'], self.DEFAULT_STATUS)
        self.check_nodes(vpc, [node_0['uuid']])

        update_data = {
            'name': vpc_name,
            'description': vpc_description,
            'nodes': []
        }
        vpc = self.vpc_client.update(vpc_uuid, update_data)

        self.assertEqual(vpc['name'], vpc_name)
        self.assertEqual(vpc['description'], vpc_description)
        self.check_nodes(vpc,[])

        vpc_name = 'my vpc {}'.format(time.time())
        vpc_description = 'some custom description {}'.format(time.time())
        update_data = {
            'name': vpc_name,
            'description': vpc_description,
            'nodes': [nodes[0]['uuid']]
        }
        vpc = self.vpc_client.update(vpc_uuid, update_data)

        self.assertEqual(vpc['name'], vpc_name)
        self.assertEqual(vpc['description'], vpc_description)
        self.assertEqual(vpc['status'], self.DEFAULT_STATUS)
        self.check_nodes(vpc, [node_0['uuid']])

    def test_vpc_dedicated_host_workflow(self):
        check_if_vpc_is_enabled()
        self._create_subscriptions()

        nodes = self.nodes_client.list()
        node_0 = nodes[0]
        res = self.vpc_client.list()

        vpc_uuid = res[0]['uuid']
        self.vpc_client.get(vpc_uuid)

        vpc_name = 'my vpc {}'.format(time.time())
        vpc_description = 'some custom description {}'.format(time.time())
        updated_data = {'name': vpc_name, 'description': vpc_description, 'nodes': [nodes[0]['uuid']]}
        vpc = self.vpc_client.update(vpc_uuid, updated_data)

        self.assertEqual(vpc['name'], vpc_name)
        self.assertEqual(vpc['description'], vpc_description)
        self.assertEqual(vpc['status'], self.DEFAULT_STATUS)
        self.check_nodes(vpc, [node_0['uuid']])

    def _create_a_server(self, server_req=None, server_req_extra=None):
        if server_req is None:
            server_req = {
                    'name': 'testServerAcc',
                    'cpu': 1000,
                    'mem': 512 * 1024 ** 2,
                    'vnc_password': 'testserver',
                    'cpu_type': self.get_cpu_type(),
            }

        if server_req_extra is not None:
            server_req.update(server_req_extra)
        server = self.server_client.create(server_req)

        self.assertDictContainsSubset(
            server_req,
            server,
            msg='Edit of server failed',
            exclude=['vnc_password'])
        self.assertEqual(server['status'], 'stopped',
                          'Server created with wrong status')
        return server

    def test_start_a_server_in_a_dedicated_host(self):
        check_if_vpc_is_enabled()
        self._create_subscriptions()
        nodes = self.nodes_client.list()
        node_0 = nodes[0]
        res = self.vpc_client.list()

        vpc_uuid = res[0]['uuid']
        self.vpc_client.get(vpc_uuid)

        vpc_name = 'my vpc {}'.format(time.time())
        vpc_description = 'some custom description {}'.format(time.time())
        updated_data = {'name': vpc_name, 'description': vpc_description, 'nodes': [nodes[0]['uuid']]}
        vpc = self.vpc_client.update(vpc_uuid, updated_data)

        self.assertEqual(vpc['name'], vpc_name)
        self.assertEqual(vpc['description'], vpc_description)
        self.assertEqual(vpc['status'], self.DEFAULT_STATUS)
        self.check_nodes(vpc, [node_0['uuid']])
        self.assertEqual(vpc['status'], self.DEFAULT_STATUS)

        server = self._create_a_server(server_req_extra={'allocation_pool': vpc['allocation_pool']})
        self.server_client.start(server['uuid'])
        self._wait_for_status(server['uuid'], 'running', client=self.server_client)

        server = self.server_client.get(server['uuid'])
        self.assertEqual(vpc['allocation_pool'], server['allocation_pool'])
        self.assertEqual(vpc['status'], self.DEFAULT_STATUS)
        vpc = self.vpc_client.get(vpc_uuid)

        running_servers = []
        for running in vpc['servers']:
            running_servers.append(running['uuid'])

        self.assertIn(server['uuid'], running_servers)
        self.server_client.stop(server['uuid'])
        self._wait_for_status(server['uuid'], 'stopped', client=self.server_client)
