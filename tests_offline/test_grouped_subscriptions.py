"""Grouped reads: synthetic opaque JSON, NOT a valid public populated-chain fixture.

Public docs specify route, 200, descendants and end_time semantics, but no
populated descendants representation. These tests make no schema, ordering,
billing, chaining or server acceptance assertion about the synthetic values.
"""
import copy
import json
import unittest
from urllib.parse import parse_qs, urlsplit
import requests
from cloudsigma import resource
from cloudsigma.errors import ClientError

PAGE = {'meta': {'limit': 2, 'offset': 3, 'total_count': 5},
        'objects': [{'descendants': [{'synthetic': [None, 'opaque', {'n': 123}]}],
                     'end_time': '2015-08-26T12:00:00+00:00'},
                    {'descendants': [], 'end_time': None}],
        'synthetic_extension': {'keep': True}}

class Adapter(requests.adapters.BaseAdapter):
    def __init__(self, status=200):
        self.status = status
        self.requests = []
    def send(self, request, **kwargs):
        self.requests.append(request)
        response = requests.Response()
        response.status_code = self.status
        response._content = json.dumps(PAGE if self.status == 200 else
            [{'error_type': 'notexist', 'error_message': 'missing',
              'error_point': None}]).encode()
        response.request = request
        return response
    def close(self):
        pass

class GroupedSubscriptionsTests(unittest.TestCase):
    def exercise(self, method, query, expected, status=200):
        original = copy.deepcopy(query)
        with requests.Session() as session:
            adapter = Adapter(status)
            session.mount('https://', adapter)
            grouped = resource.GroupedSubscriptions(
                api_endpoint='https://fixture.invalid/api/2.0/',
                username='fixture', password='synthetic', session=session)
            if status == 200:
                self.assertEqual(getattr(grouped, method)(query), expected)
            else:
                with self.assertRaises(ClientError):
                    getattr(grouped, method)(query)
            self.assertEqual(query, original)
            self.assertEqual(len(adapter.requests), 1)
            request = adapter.requests[0]
            self.assertEqual(request.method, 'GET')
            self.assertEqual(urlsplit(request.url).path,
                             '/api/2.0/groupedsubscriptions/')
            expected_query = {'limit': ['0']}
            if query:
                expected_query.update({k: [str(v)] for k, v in query.items()})
            self.assertEqual(parse_qs(urlsplit(request.url).query), expected_query)
            self.assertIsNone(request.body)

    def test_list_synthetic_opaque_values(self):
        for query in (None, {'limit': 2, 'offset': 3}):
            with self.subTest(query=query):
                self.exercise('list', query, PAGE['objects'])

    def test_raw_synthetic_complete_page(self):
        for query in (None, {'limit': 2, 'offset': 3}):
            with self.subTest(query=query):
                self.exercise('list_raw', query, PAGE)

    def test_http_error_both_reads(self):
        for method in ('list', 'list_raw'):
            with self.subTest(method=method):
                self.exercise(method, None, None, status=404)
