"""Finite documented nested singleton preservation; see fixture provenance.

No live service, generic schema validation, or backend ordering policy asserted.
"""
import copy
import json
from pathlib import Path
import unittest
import test_network_reads as network

FIXTURES = Path(__file__).parent / 'fixtures' / 'singleton_nested'


def fixture(kind):
    return json.loads((FIXTURES / (kind + '.json')).read_text())


class SingletonNestedTests(unittest.TestCase):
    # Reuse only adapter/strict JSON helpers, not its eight test methods.
    assert_json_exact = network.NetworkReadTests.assert_json_exact
    read = network.NetworkReadTests.read

    def decoded(self, kind):
        payload = fixture(kind)
        return payload, self.read(kind, 'single', payload)

    def test_ip_populated_contract(self):
        _, result = self.decoded('ip')
        self.assert_json_exact(result['permissions'], ['EDIT', 'LIST', 'ATTACH'])
        self.assert_json_exact(result['nameservers'],
                               ['69.194.139.62', '178.22.66.167', '178.22.71.56'])
        self.assert_json_exact(result['netmask'], 24)
        self.assert_json_exact(result['subscription'],
                               {'id': 7273, 'resource_uri': '/api/2.0/subscriptions/7273/'})
        self.assertIsNone(result['server'])
        self.assertIn('server', result)
        self.assertEqual(result['owner']['uuid'], '5b4a69a3-8e78-4c45-a8ba-8b13f0895e23')

    def test_vlan_populated_contract(self):
        _, result = self.decoded('vlan')
        self.assert_json_exact(result['subscription'],
                               {'id': 12, 'resource_uri': '/api/2.0/subscriptions/12/'})
        self.assert_json_exact(result['permissions'], [])  # owner view
        self.assertEqual(result['owner']['uuid'], 'c2fc9982-cf2e-434a-bf63-e22a27b39f00')
        self.assertIsNone(result['bottom_vlan_tag'])
        for grantee, uid in zip(result['grantees'],
                ['11111111-1111-4111-8111-111111111111', '3516e556-eb0e-4f0c-bf95-8b642194b8fd']):
            self.assert_json_exact(grantee, {'permissions': ['EDIT', 'LIST'],
                'user': {'email': None, 'resource_uri': '/api/2.0/user/' + uid + '/', 'uuid': uid}})
        self.assertEqual(len(result['grantees']), 2)

    def test_tags_and_string_metadata(self):
        for kind in ('ip', 'vlan'):
            _, result = self.decoded(kind)
            self.assert_json_exact(result['tags'], [
                {'uuid': uid, 'resource_uri': '/api/2.0/tags/' + uid + '/'}
                for uid in ['6d302107-fc0b-433a-99b1-9f2d3692eefc',
                            '5a9e6f2b-7927-4f30-88b5-0cc939208549']])
            self.assert_json_exact(result['meta'], {'description': 'nested fixture café', 'empty': ''})

    def test_complete_types_presence_and_order(self):
        for kind in ('ip', 'vlan'):
            payload, result = self.decoded(kind)
            self.assert_json_exact(result, payload)
            self.assertNotIn('not_documented', result)
            # Negative oracle controls: not additional SDK/wire cases.
            bad = copy.deepcopy(result)
            bad['subscription']['id'] = float(bad['subscription']['id'])
            with self.assertRaises(AssertionError): self.assert_json_exact(bad, payload)
            bad = copy.deepcopy(result)
            bad['tags'].reverse()
            with self.assertRaises(AssertionError): self.assert_json_exact(bad, payload)
            bad = copy.deepcopy(result)
            del bad['server' if kind == 'ip' else 'bottom_vlan_tag']
            with self.assertRaises(AssertionError): self.assert_json_exact(bad, payload)
        bad = fixture('vlan')
        del bad['grantees'][0]['user']['email']
        with self.assertRaises(AssertionError): self.assert_json_exact(bad, fixture('vlan'))
        with self.assertRaises(AssertionError): self.assert_json_exact(True, 1)

    def test_ip_decoded_ownership(self):
        self.check_ownership('ip')

    def test_vlan_decoded_ownership(self):
        self.check_ownership('vlan')

    def check_ownership(self, kind):
        payload, result = self.decoded(kind)
        pristine = copy.deepcopy(payload)
        result['owner']['uuid'] = 'changed'
        result['subscription']['id'] = -1
        result['tags'][0]['uuid'] = 'changed'
        result['meta']['description'] = 'changed'
        if kind == 'vlan':
            result['grantees'][0]['permissions'].append('ATTACH')
            result['grantees'][0]['user']['email'] = 'fixture@example.invalid'
            self.assert_json_exact(result['grantees'][1], pristine['grantees'][1])
        else:
            result['nameservers'].reverse()
        self.assertEqual(result['tags'][0]['uuid'], 'changed')
        self.assert_json_exact(result['tags'][1], pristine['tags'][1])
        self.assert_json_exact(payload, pristine)
        self.assert_json_exact(self.read(kind, 'single', payload), pristine)
