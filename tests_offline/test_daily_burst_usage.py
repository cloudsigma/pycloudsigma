"""Named daily burst usage listing; synthetic HTTP, not billing verification."""
import copy
import json
import unittest
from urllib.parse import parse_qs, urlsplit

import requests
from cloudsigma import resource
from cloudsigma.errors import ClientError


PAGE = {'meta': {'limit': 20, 'offset': 0, 'total_count': 2}, 'objects': [
    {'amount': '0.0089', 'date': '2014-11-17', 'resource_type': 'dssd',
     'usage': 322122547200},
    {'amount': '0.0051', 'date': '2014-11-18', 'resource_type': 'dssd',
     'usage': 268435456000}]}


class Adapter(requests.adapters.BaseAdapter):
    def __init__(self, status=200):
        self.status = status
        self.requests = []

    def send(self, request, **kwargs):
        self.requests.append(request)
        response = requests.Response()
        response.status_code = self.status
        response._content = json.dumps(PAGE if self.status == 200 else
            [{'error_type': 'notfound', 'error_message': 'missing'}]).encode()
        response.request = request
        return response

    def close(self):
        pass


class DailyBurstUsageTests(unittest.TestCase):
    def exercise(self, method, query, expected, status=200):
        original = copy.deepcopy(query)
        with requests.Session() as session:
            adapter = Adapter(status)
            session.mount('https://', adapter)
            usage = resource.DailyBurstUsage(
                api_endpoint='https://fixture.invalid/api/2.0/',
                username='fixture', password='synthetic', session=session)
            if status == 200:
                self.assertEqual(getattr(usage, method)(query), expected)
            else:
                with self.assertRaises(ClientError):
                    getattr(usage, method)(query)
            self.assertEqual(query, original)
            self.assertEqual(len(adapter.requests), 1)
            request = adapter.requests[0]
            self.assertEqual(request.method, 'GET')
            self.assertEqual(urlsplit(request.url).path, '/api/2.0/dailyburstusage/')
            expected_query = {'limit': ['0']}
            if query:
                expected_query.update({key: [str(value)] for key, value in query.items()})
            self.assertEqual(parse_qs(urlsplit(request.url).query), expected_query)
            self.assertIsNone(request.body)

    def test_list_default_and_documented_period(self):
        for query in (None, {'date__gt': '2014-11-15', 'date__lt': '2014-11-19'}):
            with self.subTest(query=query):
                self.exercise('list', query, PAGE['objects'])

    def test_raw_page_preserves_meta_and_decimal_strings(self):
        self.exercise('list_raw', {'limit': 20, 'offset': 0,
                      'date__gt': '2014-11-15'}, PAGE)

    def test_http_error_propagates(self):
        self.exercise('list', None, None, status=404)
