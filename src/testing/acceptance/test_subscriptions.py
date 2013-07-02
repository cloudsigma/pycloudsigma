import os
import unittest
from nose.plugins.attrib import attr

import cloudsigma.resource as cr

from testing.utils import DumpResponse


@attr('acceptance_test')
class BillingBase(unittest.TestCase):

    @attr('docs_snippets')
    def test_subscription_list(self):
        client = cr.Subscriptions()
        with DumpResponse(clients=[client])('subscription_list'):
            client.get()

        with DumpResponse(clients=[client])('subscription_schema'):
            client.get_schema()

    def test_subscription_create(self):
        if os.environ.get('TURLO_MANUAL_TESTS', '0') == '0':
            raise unittest.SkipTest("Subscriptions cannot be deleted by the user so this cannot be cleaned up. Use TURLO_MANUAL_TESTS=1 environment variable")

        client = cr.Subscriptions()
        with DumpResponse(clients=[client])('subscription_create'):
            sub = client.create({"resource": "dssd", "amount": 1000*3 * 10, "period": "1 month"})
