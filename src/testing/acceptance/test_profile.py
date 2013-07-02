from nose.plugins.attrib import attr
from testing.acceptance.common import StatefulResourceTestBase
from testing.utils import DumpResponse
import cloudsigma.resource as cr
import simplejson as json


def anonymize_profile(response_body):
    data = json.loads(response_body)

    data['email'] = 'user@example.com'
    data['meta'] = {}
    data['first_name'] = 'John'
    data['last_name'] = 'Doe'
    data['bank_reference'] = 'jdoe123'
    data['uuid'] = "6f670b3c-a2e6-433f-aeab-b976b1cdaf03"

    return json.dumps(data)


@attr('acceptance_test')
class ProfileTest(StatefulResourceTestBase):
    def setUp(self):
        super(ProfileTest, self).setUp()
        self.client = cr.Profile()

    @attr('docs_snippets')
    def test_profile(self):

        with DumpResponse(name='profile', clients=[self.client], resp_data_filter=anonymize_profile):
            profile = self.client.get()

        profile['company'] = 'Newly Set Company Name'
        with DumpResponse(name='profile_update', clients=[self.client],
                          resp_data_filter=anonymize_profile,
                          req_data_filter=anonymize_profile):
            self.client.update(profile)

        profile['company'] = ''
        self.client.update(profile)

    @attr('docs_snippets')
    def test_get_schema(self):
        with DumpResponse(name='profile_schema', clients=[self.client]):
            self.client.get_schema()
