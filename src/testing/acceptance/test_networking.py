from nose.plugins.attrib import attr
from testing.acceptance.common import StatefulResourceTestBase

import cloudsigma.resource as cr
from testing.utils import DumpResponse


@attr('acceptance_test')
class VLANBasicTest(StatefulResourceTestBase):
    def setUp(self):
        super(VLANBasicTest, self).setUp()
        self.client = cr.VLAN()
        self.dump_response = DumpResponse(clients=[self.client])

    @attr('docs_snippets')
    def test_vlan_listing_get_and_update(self):
        with self.dump_response('vlan_schema'):
            self.client.get_schema()

        with self.dump_response('vlan_list'):
            self.client.list()

        with self.dump_response('vlan_list_detail'):
            res = self.client.list_detail()

        vlan_uuid = res[0]['uuid']
        with self.dump_response('vlan_get'):
            self.client.get(vlan_uuid)

        with self.dump_response('vlan_update'):
            self.client.update(vlan_uuid, {'meta': {'name': 'my vlan', 'custom_field': 'some custom data'}})

        self.client.update(vlan_uuid, {'meta': {}})


@attr('acceptance_test')
class IPBasicTest(StatefulResourceTestBase):
    def setUp(self):
        super(IPBasicTest, self).setUp()
        self.client = cr.IP()
        self.dump_response = DumpResponse(clients=[self.client])

    @attr('docs_snippets')
    def test_ip_listing_get_and_update(self):
        with self.dump_response('ip_schema'):
            self.client.get_schema()

        with self.dump_response('ip_list'):
            self.client.list()

        with self.dump_response('ip_list_detail'):
            res = self.client.list_detail()

        ip_uuid = res[0]['uuid']
        with self.dump_response('ip_get'):
            self.client.get(ip_uuid)

        with self.dump_response('ip_update'):
            self.client.update(ip_uuid, {'meta': {'name': 'my ip', 'custom_field': 'some custom data'}})

        self.client.update(ip_uuid, {'meta': {}})
