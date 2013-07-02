import unittest
from nose.plugins.attrib import attr

import cloudsigma.resource as cr

from testing.utils import DumpResponse


@attr('docs_snippets', 'acceptance_test')
class BillingDocs(unittest.TestCase):

    def test_discount(self):
        client = cr.Discount()
        with DumpResponse(clients=[client])('discount_list'):
            discount = client.get()
        with DumpResponse(clients=[client])('discount_schema'):
            client.get_schema()

    def test_pricing(self):
        client = cr.Pricing()
        with DumpResponse(clients=[client])('pricing_list'):
            pricing = client.list(query_params={'limit': 5})

        with DumpResponse(clients=[client])('pricing_schema'):
            client.get_schema()


    def test_balance(self):
        client = cr.Balance()
        with DumpResponse(clients=[client])('balance_list'):
            balance = client.get()
        with DumpResponse(clients=[client])('balance_schema'):
            client.get_schema()

    def test_currentusage(self):
        client = cr.CurrentUsage()
        with DumpResponse(clients=[client])('currentusage_list'):
            currentusage = client.get()
        with DumpResponse(clients=[client])('currentusage_schema'):
            client.get_schema()

    def test_ledger(self):
        client = cr.Ledger()
        with DumpResponse(clients=[client])('ledger_list'):
            ledger = client.get()
        with DumpResponse(clients=[client])('ledger_schema'):
            client.get_schema()

    def test_licenses(self):
        client = cr.Licenses()
        with DumpResponse(clients=[client])('licenses_list'):
            licenses = client.get()
        with DumpResponse(clients=[client])('licenses_schema'):
            client.get_schema()
