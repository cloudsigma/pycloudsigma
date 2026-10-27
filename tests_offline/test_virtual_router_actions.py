import json
import unittest

import requests

from cloudsigma.resource import VirtualRouters


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


class VirtualRouterActionTests(unittest.TestCase):
    def test_get_keys_and_export_key_routes(self):
        wire = Wire()
        resource = VirtualRouters(
            api_endpoint='https://next.cloudsigma.com/api/2.0/',
            username='synthetic', password='synthetic', login_method='basic')
        resource.c._session = wire

        self.assertEqual(resource.get_keys('router-1'), {'result': 'success'})
        self.assertEqual(resource.export_key('router-1', 'key-1'),
                         {'result': 'success'})
        self.assertEqual([(m, u, k['params']) for m, u, k in wire.calls], [
            ('POST', 'https://next.cloudsigma.com/api/2.0/virtualrouters/router-1/action/',
             {'do': 'get_keys'}),
            ('POST', 'https://next.cloudsigma.com/api/2.0/virtualrouters/router-1/action/',
             {'do': 'export_key', 'key_uuid': 'key-1'}),
        ])
        for _, _, kwargs in wire.calls:
            self.assertEqual(json.loads(kwargs['data']), {})


if __name__ == '__main__':
    unittest.main()
