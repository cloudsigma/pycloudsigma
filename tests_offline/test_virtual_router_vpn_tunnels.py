import json
import unittest

import requests

from cloudsigma.resource import VpnTunnels


class Wire:
    def __init__(self):
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps({'objects': [{'uuid': 'tunnel-1'}]}).encode()
        response.headers['X-REQUEST-ID'] = 'synthetic-request'
        response.request = requests.Request(method, url).prepare()
        return response

    def __getattr__(self, method):
        return lambda url, **kwargs: self.request(method.upper(), url, **kwargs)


class VpnTunnelTests(unittest.TestCase):
    def test_documented_crud_routes(self):
        wire = Wire()
        resource = VpnTunnels(
            api_endpoint='https://next.cloudsigma.com/api/2.0/',
            username='synthetic', password='synthetic', login_method='basic')
        resource.c._session = wire

        self.assertEqual(resource.list(), [{'uuid': 'tunnel-1'}])
        self.assertEqual(resource.get('tunnel-1'), {'uuid': 'tunnel-1'})
        self.assertEqual(resource.create({'name': 'synthetic'}),
                         {'uuid': 'tunnel-1'})
        self.assertEqual(resource.update('tunnel-1', {'name': 'updated'}),
                         {'uuid': 'tunnel-1'})
        resource.delete('tunnel-1')

        self.assertEqual(
            [(method, url) for method, url, _ in wire.calls], [
                ('GET', 'https://next.cloudsigma.com/api/2.0/tunnels/'),
                ('GET', 'https://next.cloudsigma.com/api/2.0/tunnels/tunnel-1/'),
                ('POST', 'https://next.cloudsigma.com/api/2.0/tunnels/'),
                ('PUT', 'https://next.cloudsigma.com/api/2.0/tunnels/tunnel-1/'),
                ('DELETE', 'https://next.cloudsigma.com/api/2.0/tunnels/tunnel-1/'),
            ])


if __name__ == '__main__':
    unittest.main()
