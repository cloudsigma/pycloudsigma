import json
import unittest

import requests

from cloudsigma.resource import Usage


class Wire:
    def __init__(self):
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps({'objects': [{'resource': 'synthetic'}]}).encode()
        response.headers['X-REQUEST-ID'] = 'synthetic-request'
        response.request = requests.Request(method, url).prepare()
        return response

    def __getattr__(self, method):
        return lambda url, **kwargs: self.request(method.upper(), url, **kwargs)


class UsageResourceTests(unittest.TestCase):
    def test_documented_usage_listing_route(self):
        wire = Wire()
        resource = Usage(
            api_endpoint='https://next.cloudsigma.com/api/2.0/',
            username='synthetic', password='synthetic', login_method='basic')
        resource.c._session = wire

        self.assertEqual(
            resource.list(query_params={'poll_time_gt': '2024-04-01',
                                        'poll_time_lt': '2024-04-02'}),
            [{'resource': 'synthetic'}])
        self.assertEqual(len(wire.calls), 1)
        method, url, kwargs = wire.calls[0]
        self.assertEqual(method, 'GET')
        self.assertEqual(url, 'https://next.cloudsigma.com/api/2.0/usage/')
        self.assertEqual(kwargs['params'], {
            'limit': 0,
            'poll_time_gt': '2024-04-01',
            'poll_time_lt': '2024-04-02',
        })


if __name__ == '__main__':
    unittest.main()
