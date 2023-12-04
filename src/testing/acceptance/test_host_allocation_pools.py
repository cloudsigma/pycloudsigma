from nose.plugins.attrib import attr
from cloudsigma import resource
from cloudsigma.resource import HostAllocationPools
from testing.acceptance.common import VpcTestsBase, check_if_vpc_is_enabled
from cloudsigma.errors import ClientError
from unittest import SkipTest


class HostAllocationPoolsTest(VpcTestsBase):

    def setUp(self):
        super(HostAllocationPoolsTest, self).setUp()
        self.server_client = resource.Server()
        self.client = HostAllocationPools()
        self.client_2 = HostAllocationPools(**self.get_other_account())

    def get_list(self):
        try:
            return self.client.list()
        except ClientError as e:
            raise SkipTest("hostallocationpools API calls are not enabled")

    @attr('docs_snippets')
    def test_listing(self):
        check_if_vpc_is_enabled()
        self._create_vpc_subscription()
        vpc_list = self.vpc_client.list()
        vpc_pools = [vpc['allocation_pool'] for vpc in vpc_list]

        pool_list = self.get_list()
        self.assertEqual(len(pool_list), len(vpc_pools))
        self.assertTrue(len(pool_list) > 0)
        for pool in pool_list:
            self.assertIn('uuid', pool)
            self.assertIn('name', pool)
            self.assertIn('description', pool)
            self.assertIn('cpu_alloc', pool)
            self.assertIn('cpu_alloc_last_resort', pool)
            self.assertIn(pool['uuid'], vpc_pools)

        pools_2 = self.client_2.list()
        self.assertTrue(len(pools_2) == 0)

    @attr('docs_snippets')
    def test_update(self):
        check_if_vpc_is_enabled()
        self._create_vpc_subscription()
        pool_list = self.get_list()
        self.assertTrue(len(pool_list) > 0)

        pool = pool_list[0]
        from time import time
        t = int(time())

        edited_name = 'my host allocation pool name {}'.format(t)
        edited_description = 'my host allocation pool description {}'.format(t)

        edited_data = {
            'name': edited_name,
            'description': edited_description,
            'cpu_alloc': 1,
            'cpu_alloc_last_resort': 2,
        }

        self.client.update(pool['uuid'], edited_data)

        edited_pool = self.client.get(pool['uuid'])
        self.assertEqual(edited_name, edited_pool['name'])
        self.assertEqual(edited_description, edited_pool['description'])
        self.assertEqual('1.000', edited_pool['cpu_alloc'])
        self.assertEqual('2.000', edited_pool['cpu_alloc_last_resort'])
        with self.assertRaises(ClientError):
            self.client_2.update(pool['uuid'], edited_data)

    def test_invalid_values(self):
        check_if_vpc_is_enabled()
        self._create_vpc_subscription()
        pool_list = self.get_list()
        self.assertTrue(len(pool_list) > 0)

        pool = pool_list[0]
        from time import time
        t = int(time())

        edited_name = 'my host allocation pool name {}'.format(t)
        edited_description = 'my host allocation pool description {}'.format(t)

        edited_data = {
            'name': edited_name,
            'description': edited_description,
            'cpu_alloc': "aaaaa",
            'cpu_alloc_last_resort': 2,
        }

        with self.assertRaises(ClientError):
            self.client.update(pool['uuid'], edited_data)

        edited_data = {
            'name': edited_name,
            'description': edited_description,
            'cpu_alloc': 2,
            'cpu_alloc_last_resort': "value",
        }

        with self.assertRaises(ClientError):
            self.client.update(pool['uuid'], edited_data)
