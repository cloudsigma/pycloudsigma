import unittest
from nose.plugins.attrib import attr
from testing.utils import DumpResponse
import cloudsigma.resource as resource


@attr('acceptance_test')
class FirewallPolicyTest(unittest.TestCase):
    def setUp(self):
        unittest.TestCase.setUp(self)
        self.client = resource.FirewallPolicy()
        self.dump_response = DumpResponse(clients=[self.client])
        self.base_policy = {
            "name": "My awesome policy",
            "rules": [
                {
                    "dst_ip": "23",
                    "direction": "out",
                    "action": "drop",
                    "comment": "Drop traffic from the VM to IP address 23.0.0.0/32"
                },
                {
                    "src_ip": "172.66.32.0/24",
                    "ip_proto": "tcp",
                    "dst_port": "22",
                    "direction": "in",
                    "action": "accept",
                    "comment": "Allow SSH traffic to the VM from our office in Dubai"
                },
                {
                    "ip_proto": "tcp",
                    "dst_port": "22",
                    "direction": "in",
                    "action": "drop",
                    "comment": "Drop all other SSH traffic to the VM"
                },
                {
                    "src_ip": "!172.66.32.55",
                    "ip_proto": "udp",
                    "direction": "in",
                    "action": "drop",
                    "comment": "Drop all UDP traffic to the VM, not originating from 172.66.32.55"
                },
                {
                    "ip_proto": "tcp",
                    "dst_port": "!1:1024",
                    "direction": "in",
                    "action": "drop",
                    "comment": "Drop any traffic, to the VM with destination port not between 1-1024"
                }
            ]
        }
        self._clean_policies()

    def tearDown(self):
        self._clean_policies()

    def _clean_policies(self):
        policies = self.client.list_detail()
        server_client = resource.Server()
        deleted_servers = []
        for policy in policies:
            for server in policy['servers']:
                if server['uuid'] not in deleted_servers:
                    deleted_servers.append(server['uuid'])
                    server_client.delete(server['uuid'])
            self.client.delete(policy['uuid'])

    @attr('docs_snippets')
    def test_get_schema(self):
        with self.dump_response('fwpolicy_schema'):
            self.client.get_schema()

    @attr('docs_snippets')
    def test_crud_policy(self):
        base_policy = self.base_policy.copy()

        with self.dump_response('fwpolicy_create_minimal'):
            min_policy = self.client.create({})

        self.assertDictContainsSubset({}, min_policy)

        with self.dump_response('fwpolicy_create_full'):
            full_policy = self.client.create(base_policy)

        # Test if applied rules look like the ones returned from the API
        # The dict is subset will not work, because API alters/normalizes some of the data
        for idx, rules in enumerate(base_policy['rules']):
            for key in rules:
                match_a = str(full_policy['rules'][idx][key])
                match_b = rules[key]
                print match_a, match_b
                self.assertTrue(match_a.startswith(match_b))

        with self.dump_response('fwpolicy_list'):
            res = self.client.list()

        with self.dump_response('fwpolicy_list_detail'):
            res = self.client.list_detail()

        self.assertEqual(len(res), 2)

        updated_policy = full_policy.copy()
        updated_policy['rules'] = [updated_policy['rules'][0]]

        with self.dump_response('fwpolicy_get'):
            self.client.get(full_policy['uuid'])

        with self.dump_response('fwpolicy_update'):
            up_pol = self.client.update(full_policy['uuid'], updated_policy)

        self.assertEqual(len(up_pol['rules']), 1)

        with self.dump_response('fwpolicy_delete'):
            self.client.delete(full_policy['uuid'])

        self.client.delete(min_policy['uuid'])

        res = self.client.list()
        self.assertEqual(len(res), 0)

    @attr('docs_snippets')
    def test_server_fw_rules(self):
        policy = self.client.create(self.base_policy)

        server_def = {
            'name': 'FirewalledServer',
            'cpu': 1000,
            'mem': 512 * 1024 ** 2,
            'vnc_password': 'testserver',
            "nics": [
                {
                    "firewall_policy": policy['uuid'],
                    "ip_v4_conf": {
                        "ip": None,
                        "conf": "dhcp"
                    },
                    "model": "virtio",
                }
            ],
        }
        server_client = resource.Server()
        with DumpResponse(clients=[server_client])("fwpolicy_server_attach"):
            server = server_client.create(server_def)

        self.assertEqual(server['nics'][0]['firewall_policy']['uuid'], policy['uuid'])

        self.client.delete(policy['uuid'])

        server = server_client.get(server['uuid'])
        self.assertIsNone(server['nics'][0]['firewall_policy'])

        server_client.delete(server['uuid'])
