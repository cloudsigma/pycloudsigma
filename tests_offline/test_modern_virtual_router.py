import json
import unittest

import requests

from cloudsigma.virtual_router import VirtualRouter


class Wire:
    def __init__(self, body):
        self.body = body
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps(self.body).encode()
        response.headers['X-REQUEST-ID'] = 'synthetic-request'
        response.request = requests.Request(method, url).prepare()
        return response

    def __getattr__(self, method):
        return lambda url, **kwargs: self.request(method.upper(), url, **kwargs)


class ModernVirtualRouterTests(unittest.TestCase):
    def make(self, body):
        resource = VirtualRouter(
            api_endpoint='https://next.cloudsigma.com/api/2.0/',
            username='synthetic', password='synthetic', login_method='basic')
        wire = Wire(body)
        resource.c._session = wire
        return resource, wire

    def test_list_tunnels_reads_modern_router_configuration(self):
        tunnel = {'name': 'office-a', 'native_security': {'mode': 'vti'},
                  'future_field': {'provider_owned': True}}
        resource, wire = self.make({'objects': [{
            'uuid': 'router-1', 'configuration': {'vpn': {'tunnels': [tunnel]}}
        }]})

        self.assertEqual(resource.list_tunnels('router-1'), [tunnel])
        self.assertEqual(wire.calls[0][0], 'GET')
        self.assertEqual(wire.calls[0][1],
                         'https://next.cloudsigma.com/api/2.0/virtual_routers/router-1/')
        self.assertFalse(wire.calls[0][2]['allow_redirects'])

    def test_tunnel_container_validation(self):
        for body in ({}, {'objects': [{'configuration': {}}]},
                     {'objects': [{'configuration': {'vpn': {}}}]},
                     {'objects': [{'configuration': {'vpn': {'tunnels': {}}}}]},
                     {'objects': [{'configuration': {'vpn': {'tunnels': [1]}}}]}):
            resource, wire = self.make(body)
            with self.assertRaises(ValueError):
                resource.list_tunnels('router-1')
            self.assertEqual(len(wire.calls), 1)

    def test_scoped_actions_forward_body_and_action(self):
        body = {'objects': [{'accepted': True}]}
        resource, wire = self.make(body)
        action_body = {'name': 'office-a', 'provider_extension': {'x': 1}}
        self.assertEqual(resource.add_ipsec_tunnel('router-1', action_body),
                         {'accepted': True})
        self.assertEqual(resource.edit_ipsec_tunnel('router-1', action_body),
                         {'accepted': True})
        self.assertEqual(resource.remove_ipsec_tunnel(
            'router-1', {'name': 'office-a'}), {'accepted': True})
        self.assertEqual([call[2]['params'] for call in wire.calls], [
            {'do': 'add_ipsec_tunnel'}, {'do': 'edit_ipsec_tunnel'},
            {'do': 'remove_ipsec_tunnel'}])
        self.assertEqual(json.loads(wire.calls[0][2]['data']), action_body)
        self.assertEqual(json.loads(wire.calls[1][2]['data']), action_body)

    def test_capabilities_and_status_routes(self):
        resource, wire = self.make({'objects': [{'ready': True}]})
        resource.ipsec_capabilities('router-1')
        resource.ipsec_status('router-1')
        self.assertEqual([call[1] for call in wire.calls], [
            'https://next.cloudsigma.com/api/2.0/virtual_routers/router-1/ipsec/capabilities/',
            'https://next.cloudsigma.com/api/2.0/virtual_routers/router-1/ipsec/status/',
        ])


if __name__ == '__main__':
    unittest.main()
