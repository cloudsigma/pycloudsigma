from nose.plugins.attrib import attr
from testing.acceptance.common import StatefulResourceTestBase
from testing.utils import DumpResponse
import cloudsigma.resource as cr


@attr('acceptance_test')
class CapabilitiesTest(StatefulResourceTestBase):
    def setUp(self):
        super(CapabilitiesTest, self).setUp()
        self.client = cr.Capabilites()
        self.dump_response = DumpResponse(clients=[self.client])

    @attr('docs_snippets')
    def test_capabilities(self):
        with self.dump_response('capabilities_schema'):
            self.client.get_schema()

        with self.dump_response('capabilities'):
            self.client.list()
