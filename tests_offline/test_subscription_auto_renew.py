import json
import unittest

import requests

from cloudsigma.resource import Subscriptions


class Wire:
    def __init__(self):
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps({'objects': [{'result': 'success'}]}).encode()
        response.headers['X-REQUEST-ID'] = 'synthetic-request'
        response.request = requests.Request(method, url).prepare()
        return response

    def __getattr__(self, method):
        return lambda url, **kwargs: self.request(method.upper(), url, **kwargs)


class SubscriptionActionTests(unittest.TestCase):
    def test_auto_renew_routes_documented_action(self):
        wire = Wire()
        resource = Subscriptions(
            api_endpoint='https://next.cloudsigma.com/api/2.0/',
            username='synthetic', password='synthetic', login_method='basic')
        resource.c._session = wire

        self.assertEqual(resource.auto_renew('subscription-1'),
                         {'result': 'success'})
        self.assertEqual(wire.calls[0][0], 'POST')
        self.assertEqual(
            wire.calls[0][1],
            'https://next.cloudsigma.com/api/2.0/subscriptions/subscription-1/action/')
        self.assertEqual(wire.calls[0][2]['params'], {'do': 'auto_renew'})
        self.assertEqual(json.loads(wire.calls[0][2]['data']), {})


if __name__ == '__main__':
    unittest.main()
