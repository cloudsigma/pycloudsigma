from nose.plugins.attrib import attr
from cloudsigma import resource
from cloudsigma.resource import HostAvailabilityZones
from testing.acceptance.common import StatefulResourceTestBase
from cloudsigma.errors import ClientError
from unittest import SkipTest


class HostAvailabilityZoneTest(StatefulResourceTestBase):

    def setUp(self):
        super(HostAvailabilityZoneTest, self).setUp()
        self.server_client = resource.Server()
        self.client = HostAvailabilityZones()

    def get_list(self):
        try:
            return self.client.list()
        except ClientError:
            raise SkipTest("hostavailabilityzones API calls are not enabled")

    @attr('docs_snippets')
    def test_listing(self):
        zones = self.get_list()
        self.assertTrue(len(zones) > 0)
        for zone in zones:
            self.assertIn('uuid', zone)
            self.assertIn('name', zone)

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

        for key, value in list(server_req.items()):
            if key != 'vnc_password':
                self.assertEqual(
                    server[key], value, 'Key "{}" has a different value.'.format(key))

        self.assertEqual(server['status'], 'stopped',
                         'Server created with wrong status')
        return server

    def _try_to_start_in_a_zone(self, zone):
        server = self._create_a_server(
            server_req_extra={'allocation_pool': zone['uuid']})
        self.server_client.start(server['uuid'])
        self._wait_for_status(
            server['uuid'], 'running', client=self.server_client, timeout=120)

        server = self.server_client.get(server['uuid'])
        self.assertIn(zone['uuid'], server['allocation_pool'])
        self.assertEqual('running', server['status'])

        self.server_client.stop(server['uuid'])
        self._wait_for_status(
            server['uuid'], 'stopped', client=self.server_client, timeout=120)

    def test_start_a_server_in_an_availability_zone(self):
        zones = self.get_list()
        for zone in zones:
            self._try_to_start_in_a_zone(zone)
