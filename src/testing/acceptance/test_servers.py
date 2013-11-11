import unittest
import time
from nose.plugins.attrib import attr
import socket
import urlparse
from testing.acceptance.common import StatefulResourceTestBase

import cloudsigma.resource as cr
from testing.utils import DumpResponse


@attr('acceptance_test')
class ServerTestBase(StatefulResourceTestBase):
    def setUp(self):
        unittest.TestCase.setUp(self)
        self.client = cr.Server()            # create a resource handle object
        self.dump_response = DumpResponse(clients=[self.client])

    def _create_a_server(self, server_req=None):
        if server_req is None:
            server_req = {
                'name': 'testServerAcc',
                'cpu': 1000,
                'mem': 512 * 1024 ** 2,
                'vnc_password': 'testserver',
            }
        server = self.client.create(server_req)
        self.assertDictContainsSubset(server_req, server, 'Server created with different params')
        self.assertEqual(server['status'], 'stopped', 'Server created with wrong status')
        return server


class ServerTest(ServerTestBase):
    @classmethod
    def tearDownClass(cls):
        # TODO: Clean-up after the tests using the bulk tools
        super(ServerTest, cls).tearDownClass()

    @attr('docs_snippets')
    def test_list_limit(self):
        servers = [self._create_a_server(server_req={
            'name': 'test server %d' % (i,),
            'cpu': 1000,
            'mem': 512 * 1024 ** 2,
            'vnc_password': 'testserver',
            }) for i in xrange(50)]
        with DumpResponse(clients=[self.client])('server_list'):
            servers_list = self.client.list(query_params={'limit': 20})
            self.assertEqual(20, len(servers_list))
        time.sleep(10)
        for server in servers:
            self.client.delete(server['uuid'])

    @attr('docs_snippets')
    def test_server_state_cycle(self):
        """Test simple server create-start-stop-delete cycle
        """
        dump_response = DumpResponse(clients=[self.client])

        with dump_response('server_create_minimal'):
            server = self._create_a_server()

        self._verify_list(server, True)

        with dump_response('server_start'):
            self.client.start(server['uuid'])

        self._wait_for_status(server['uuid'], 'running')

        with dump_response('server_stop'):
            self.client.stop(server['uuid'])

        self._wait_for_status(server['uuid'], 'stopped')

        with dump_response('server_delete'):
            self.client.delete(server['uuid'])

        self._verify_list(server, False)

    @attr('docs_snippets')
    def test_create_full_server(self):
        dv = cr.Drive()
        dump_response = DumpResponse(clients=[self.client])

        drive_def_1 = {
            'name': 'test_drive_1',
            'size': '1024000000',
            'media': 'disk',
        }

        drive_def_2 = {
            'name': 'test_drive_2',
            'size': '1024000000',
            'media': 'cdrom',
        }

        drive1 = dv.create(drive_def_1)
        drive2 = dv.create(drive_def_2)

        self._wait_for_status(drive1['uuid'], 'unmounted', client=dv)
        self._wait_for_status(drive2['uuid'], 'unmounted', client=dv)

        server_definition = {
            "requirements": [],
            "name": "test_acc_full_server",
            "cpus_instead_of_cores": False,
            "tags": [],
            "mem": 256*1024**2,
            "nics": [
                {
                    "ip_v4_conf": {
                        "conf": "dhcp"
                    },
                }
            ],
            "enable_numa": False,
            "cpu": 1000,
            "drives": [
                {
                    "device": "virtio",
                    "dev_channel": "0:0",
                    "drive": drive1['uuid'],
                    "boot_order": 1
                },
                {
                    "device": "ide",
                    "dev_channel": "0:0",
                    "drive": drive2['uuid'],
                },
            ],
            "smp": 1,
            "hv_relaxed": False,
            "hv_tsc": False,
            "meta": {
                "description": "A full server with description"
            },

            "vnc_password": "tester",
        }

        with dump_response('server_create_full'):
            server = self.client.create(server_definition)

        # TODO: Uncomment this when the guest_drive definition order changes reach production
        #self._verify_list(server, True)

        self.client.delete(server['uuid'])

        self._verify_list(server, False)

        dv.delete(drive1['uuid'])
        dv.delete(drive2['uuid'])

        self._wait_deleted(drive1['uuid'], client=dv)
        self._wait_deleted(drive2['uuid'], client=dv)

    @attr('docs_snippets')
    def test_recurse_delete_guest_w_disks(self):
        dv = cr.Drive()
        dump_response = DumpResponse(clients=[self.client])

        drive_def_1 = {
            'name': 'test_drive_1',
            'size': '1024000000',
            'media': 'disk',
        }

        drive_def_2 = {
            'name': 'test_drive_2',
            'size': '1024000000',
            'media': 'cdrom',
        }

        drive1 = dv.create(drive_def_1)
        drive2 = dv.create(drive_def_2)

        self._wait_for_status(drive1['uuid'], 'unmounted', client=dv)
        self._wait_for_status(drive2['uuid'], 'unmounted', client=dv)

        with DumpResponse(clients=[dv], name='server_recurse_del_disks_drives_before'):
            dv.list_detail()

        server_definition = {
            "requirements": [],
            "name": "test_acc_full_server",
            "cpus_instead_of_cores": False,
            "tags": [],
            "mem": 256*1024**2,
            "nics": [
                {
                    "ip_v4_conf": {
                        "conf": "dhcp"
                    },
                }
            ],
            "enable_numa": False,
            "cpu": 1000,
            "drives": [
                {
                    "device": "virtio",
                    "dev_channel": "0:0",
                    "drive": drive1['uuid'],
                    "boot_order": 1
                },
                {
                    "device": "ide",
                    "dev_channel": "0:0",
                    "drive": drive2['uuid'],
                },
            ],
            "smp": 1,
            "hv_relaxed": False,
            "hv_tsc": False,
            "meta": {
                "description": "A full server with description"
            },

            "vnc_password": "tester",
        }

        with dump_response('server_recurse_del_disks_create'):
            server = self.client.create(server_definition)

        # TODO: Uncomment this when the guest_drive definition order changes reach production
        #self._verify_list(server, True)
        with dump_response('server_recurse_del_disks_delete'):
            self.client.delete_with_disks(server['uuid'])

        self._verify_list(server, False)

        self._wait_deleted(drive1['uuid'], client=dv)

        self.assertEqual(dv.get(drive2['uuid'])['status'], 'unmounted')
        with DumpResponse(clients=[dv], name='server_recurse_del_disks_drives_after'):
            dv.list()

        dv.delete(drive2['uuid'])
        self._wait_deleted(drive2['uuid'], client=dv)

    def test_recurse_delete_guest_w_cdroms(self):
        dv = cr.Drive()

        drive_def_1 = {
            'name': 'test_drive_1',
            'size': '1024000000',
            'media': 'disk',
        }

        drive_def_2 = {
            'name': 'test_drive_2',
            'size': '1024000000',
            'media': 'cdrom',
        }

        drive1 = dv.create(drive_def_1)
        drive2 = dv.create(drive_def_2)

        self._wait_for_status(drive1['uuid'], 'unmounted', client=dv)
        self._wait_for_status(drive2['uuid'], 'unmounted', client=dv)

        server_definition = {
            "requirements": [],
            "name": "test_acc_full_server",
            "cpus_instead_of_cores": False,
            "tags": [],
            "mem": 256*1024**2,
            "nics": [
                {
                    "ip_v4_conf": {
                        "conf": "dhcp"
                    },
                }
            ],
            "enable_numa": False,
            "cpu": 1000,
            "drives": [
                {
                    "device": "virtio",
                    "dev_channel": "0:0",
                    "drive": drive1['uuid'],
                    "boot_order": 1
                },
                {
                    "device": "ide",
                    "dev_channel": "0:0",
                    "drive": drive2['uuid'],
                },
            ],
            "smp": 1,
            "hv_relaxed": False,
            "hv_tsc": False,
            "meta": {
                "description": "A full server with description"
            },

            "vnc_password": "tester",
        }


        server = self.client.create(server_definition)

        # TODO: Uncomment this when the guest_drive definition order changes reach production
        #self._verify_list(server, True)

        self.client.delete_with_cdroms(server['uuid'])

        self._verify_list(server, False)

        self._wait_deleted(drive2['uuid'], client=dv)

        self.assertEqual(dv.get(drive1['uuid'])['status'], 'unmounted')
        dv.delete(drive1['uuid'])
        self._wait_deleted(drive1['uuid'], client=dv)

    @attr('docs_snippets')
    def test_recurse_delete_server_w_all_drives(self):
        dv = cr.Drive()
        dump_response = DumpResponse(clients=[self.client])

        drive_def_1 = {
            'name': 'test_drive_1',
            'size': '1024000000',
            'media': 'disk',
        }

        drive_def_2 = {
            'name': 'test_drive_2',
            'size': '1024000000',
            'media': 'cdrom',
        }

        drive1 = dv.create(drive_def_1)
        drive2 = dv.create(drive_def_2)

        self._wait_for_status(drive1['uuid'], 'unmounted', client=dv)
        self._wait_for_status(drive2['uuid'], 'unmounted', client=dv)

        with DumpResponse(clients=[dv], name='server_recurse_del_all_drives_drives_before'):
            dv.list_detail()

        server_definition = {
            "requirements": [],
            "name": "test_acc_full_server",
            "cpus_instead_of_cores": False,
            "tags": [],
            "mem": 256*1024**2,
            "nics": [
                {
                    "ip_v4_conf": {
                        "conf": "dhcp"
                    },
                }
            ],
            "enable_numa": False,
            "cpu": 1000,
            "drives": [
                {
                    "device": "virtio",
                    "dev_channel": "0:0",
                    "drive": drive1['uuid'],
                    "boot_order": 1
                },
                {
                    "device": "ide",
                    "dev_channel": "0:0",
                    "drive": drive2['uuid'],
                },
            ],
            "smp": 1,
            "hv_relaxed": False,
            "hv_tsc": False,
            "meta": {
                "description": "A full server with description"
            },

            "vnc_password": "tester",
        }

        with dump_response('server_recurse_del_all_drives_create'):
            server = self.client.create(server_definition)

        # TODO: Uncomment this when the guest_drive definition order changes reach production
        #self._verify_list(server, True)
        with dump_response('server_recurse_del_all_drives_delete'):
            self.client.delete_with_all_drives(server['uuid'])

        self._verify_list(server, False)



        self._wait_deleted(drive1['uuid'], client=dv)
        self._wait_deleted(drive2['uuid'], client=dv)
        self._wait_deleted(server['uuid'], client=self.client)

        with DumpResponse(clients=[dv], name='server_recurse_del_all_drives_drives_after'):
            dv.list_detail()


    @attr('docs_snippets')
    def test_server_nics(self):
        server = self._create_a_server()

        subs_client = cr.Subscriptions()

        vlan_client = cr.VLAN()
        vlans = vlan_client.list()
        if not vlans:
            subs_client.create({'resource': 'vlan', 'amount': 1, 'period': '1 month'})
            vlans = vlan_client.list()
        vlan_uuid = vlans[0]['uuid']

        ip_client = cr.IP()
        ips = ip_client.list()
        free_ips = [ip for ip in ips if ip['server'] is None]
        if not free_ips:
            subs_client.create({'resource': 'ip', 'amount': 1, 'period': '1 month'})
            ips = ip_client.list()
            free_ips = [ip for ip in ips if ip['server'] is None]

        ip_uuid = free_ips[0]['uuid']

        server['nics'] = [{'vlan': vlan_uuid}]

        with DumpResponse(clients=[self.client], name='server_add_private_nic'):
            server = self.client.update(server['uuid'], server)

        server['nics'] = [{'ip_v4_conf': {'conf': 'dhcp'}, 'model': 'e1000'}]
        with DumpResponse(clients=[self.client], name='server_add_dhcp_nic'):
            server = self.client.update(server['uuid'], server)

        server['nics'] = [{'ip_v4_conf': {'conf': 'dhcp'}, 'model': 'e1000'}, {'vlan': vlan_uuid}]
        server = self.client.update(server['uuid'], server)
        with DumpResponse(clients=[self.client], name='server_get_two_nics'):
            server = self.client.get(server['uuid'])

        server['nics'][0]['ip_v4_conf'] = {'conf': 'static', 'ip': ip_uuid}
        with DumpResponse(clients=[self.client], name='server_change_nic_to_static'):
            server = self.client.update(server['uuid'], server)

        server['nics'] = [server['nics'][1], server['nics'][0]]
        with DumpResponse(clients=[self.client], name='server_rearrange_nics'):
            server = self.client.update(server['uuid'], server)

        private_mac = server['nics'][0]['mac']
        server['nics'] = [{'ip_v4_conf': {'conf': 'dhcp'}, 'mac': private_mac}]
        with DumpResponse(clients=[self.client], name='server_del_and_change_nic'):
            server = self.client.update(server['uuid'], server)

        server['nics'] = [{'ip_v4_conf': {'conf': 'manual'}}]
        with DumpResponse(clients=[self.client], name='server_add_manual_nic'):
            server = self.client.update(server['uuid'], server)

        self.client.delete(server['uuid'])

    @attr('docs_snippets')
    def test_server_runtime(self):
        dv = cr.Drive()
        drive_def_1 = {
            'name': 'test_drive_1',
            'size': '1024000000',
            'media': 'disk',
        }
        drive1 = dv.create(drive_def_1)
        self._wait_for_status(drive1['uuid'], 'unmounted', client=dv)
        
        server_def = {
            'name': 'testServerAcc',
            'cpu': 1000,
            'mem': 512 * 1024 ** 2,
            'vnc_password': 'testserver',
            'drives': [
                {
                    "device": "virtio",
                    "dev_channel": "0:0",
                    "drive": drive1['uuid'],
                    "boot_order": 1
                },

            ],
            "nics": [
                {
                    "ip_v4_conf": {
                        "ip": None,
                        "conf": "dhcp"
                    },
                    "model": "virtio",
                }
            ],
        }

        server = self.client.create(server_def)

        self._verify_list(server, True)

        self.client.start(server['uuid'])

        self._wait_for_status(server['uuid'], 'running')

        with DumpResponse(clients=[self.client], name='server_get_running'):
            server_def = self.client.get(server['uuid'])

        self.assertEqual(server_def['runtime']['nics'][0]['interface_type'], 'public')
        self.assertIsNotNone(server_def['runtime']['nics'][0]['ip_v4'])

        # check runtime call
        runtime = self.client.runtime(server['uuid'])
        self.assertEqual(runtime['nics'][0]['interface_type'], 'public')
        self.assertIsNotNone(runtime['nics'][0]['ip_v4'])

        self.client.stop(server['uuid'])
        self._wait_for_status(server['uuid'], 'stopped')

        self.client.delete(server['uuid'])
        self._verify_list(server, False)

        dv.delete(drive1['uuid'])
        self._wait_deleted(drive1['uuid'], client=dv)

    def _open_vnc_tunnel(self):
        server = self._create_a_server()
        self.client.start(server['uuid'])
        self._wait_for_status(server['uuid'], 'running')

        with self.dump_response('server_open_vnc'):
            open_vnc_resp = self.client.open_vnc(server['uuid'])

        self.assertDictContainsSubset({'result': 'success', 'uuid': server['uuid']}, open_vnc_resp)

        #Parsing vnc address and port from vnc_url
        vnc_args = urlparse.urlparse(open_vnc_resp['vnc_url']).netloc.split(":")
        vnc_address = (str(vnc_args[0]), int(vnc_args[1]))
        
        return server, vnc_address

    def _close_vnc_tunnel(self, server):
        with self.dump_response('server_close_vnc'):
            close_vnc_resp = self.client.close_vnc(server['uuid'])

        self.assertDictContainsSubset({'result': 'success', 'uuid': server['uuid'], 'action': 'close_vnc'},
                                      close_vnc_resp)

        self.client.stop(server['uuid'])
        self._wait_for_status(server['uuid'], 'stopped')

        self.client.delete(server['uuid'])
        self._verify_list(server, False)
        
    @attr('docs_snippets')
    def test_vnc_tunnel_open_close(self):
        server, _ = self._open_vnc_tunnel()
        time.sleep(3)        
        self._close_vnc_tunnel(server)
    
    def test_vnc_tunnel(self):
        server, vnc_address = self._open_vnc_tunnel()
       
        vnc_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        vnc_sock.settimeout(10)

        now = time.time()

        while now + 15 >= time.time():
            try:
                #Check if we can connect to VNC address
                vnc_sock.connect(vnc_address)
            except:
                time.sleep(1)
            else:
                break

        #Checking if VNC initial handshake is sent
        vnc_ver = vnc_sock.recv(16)
        self.assertRegexpMatches(vnc_ver, 'RFB \d+\.\d+\\n')
        vnc_sock.close()
    
        self._close_vnc_tunnel(server)

    @attr('docs_snippets')
    def test_get_schema(self):
        with DumpResponse(clients=[self.client], name='server_schema'):
            self.client.get_schema()

    @attr('docs_snippets')
    def test_server_list(self):

        server_req = [
            {
                'name': 'test_server_%i' % i,
                'cpu': 1000,
                'mem': 512 * 1024 ** 2,
                'vnc_password': 'testserver',
            } for i in range(5)
        ]

        with self.dump_response('server_create_bulk'):
            servers = self.client.create(server_req)

        with self.dump_response('server_list'):
            self.client.list()

        with self.dump_response('server_list_detail'):
            self.client.list_detail()

        for server in servers:
            self.client.delete(server['uuid'])

        remaining_servers = [srv['uuid'] for srv in self.client.list()]

        for server in servers:
            self.assertNotIn(server['uuid'], remaining_servers)

    @attr('docs_snippets')
    def test_server_edit(self):
        server_def = {
            'name': 'test_server_1',
            'cpu': 1000,
            'mem': 512 * 1024 ** 2,
            'vnc_password': 'testserver',
        }

        server = self._create_a_server(server_req=server_def)

        # Test simple update
        server_def['name'] = 'test_server_updated'
        server_def['cpu'] = 2000
        server_def['vnc_password'] = 'updated_password'

        with self.dump_response('server_edit_minimal'):
            updated_server = self.client.update(server['uuid'], server_def)

        self.assertDictContainsSubset(server_def, updated_server)

        server_def['meta'] = {'meta_key1': 'value1', 'meta_key2': 'value2'}
        with self.dump_response('server_add_meta'):
            self.client.update(server['uuid'], server_def)
        updated_server['meta'] = {'meta_key2': 'value2', 'meta_key3': 'value3'}
        with self.dump_response('server_edit_meta'):
            updated_server = self.client.update(server['uuid'], updated_server)

        self.assertTrue('meta_key1' not in updated_server['meta'])
        self.assertTrue(updated_server['meta']['meta_key3'] == 'value3')

        del server_def['meta']
        self.client.update(server['uuid'], server_def)

        dv = cr.Drive()

        drive_def_1 = {
            'name': 'test_drive_1',
            'size': '1024000000',
            'media': 'disk',
        }

        drive = dv.create(drive_def_1)
        self._wait_for_status(drive['uuid'], 'unmounted', client=dv)

        #Test attach drive
        server_def['drives'] = [
            {
                "device": "virtio",
                "dev_channel": "0:0",
                "drive": drive['uuid'],
                "boot_order": 1
            },
        ]

        with self.dump_response('server_attach_drive'):
            updated_server = self.client.update(server['uuid'], server_def)

        self.assertEqual(
            server_def['drives'][0]['drive'],
            updated_server['drives'][0]['drive']['uuid'],
            'The updated server and the update definition do not match'
        )

        self.client.delete(updated_server['uuid'])

        dv.delete(drive['uuid'])

        self._wait_deleted(drive['uuid'], client=dv)

    def test_bulk_start_stop_and_usage(self):

        # Check if usage is correct
        usage_client = cr.CurrentUsage()
        curr_cpu_usage = usage_client.list()['usage']['cpu']['using']

        server_req = [{
                          'name': 'test_start_stop_server_%i' % i,
                          'cpu': 500,
                          'mem': 512 * 1024 ** 2,
                          'vnc_password': 'testserver',
                      } for i in range(40)]

        # Creating 40 servers
        servers = self.client.create(server_req)
        cpu_usage = sum(g['cpu'] for g in server_req) + curr_cpu_usage

        # Starting the servers
        for server in servers:
            self.client.start(server['uuid'])

        time.sleep(2)           # give a bit of time for usage to update
        self.assertEqual(cpu_usage, usage_client.list()['usage']['cpu']['using'])

        # Wait for status running
        for server in servers:
            self._wait_for_status(server['uuid'], 'running')

        # Stop the servers
        for server in servers:
            self.client.stop(server['uuid'])

        # Wait for them to stop
        for server in servers:
            self._wait_for_status(server['uuid'], 'stopped', timeout=45)

        # Delete them
        for server in servers:
            self.client.delete(server['uuid'])

    @attr('docs_snippets')
    def test_server_clone(self):
        server = self._create_a_server()

        with DumpResponse(clients=[self.client], name='server_get_clone_source'):
            server = self.client.get(server['uuid'])

        with DumpResponse(clients=[self.client], name='server_clone'):
            clone = self.client.clone(server['uuid'], {'name': 'test cloned server name', 'random_vnc_password': True})

        self.client.delete(server['uuid'])
        self.client.delete(clone['uuid'])

    def test_server_clone_with_drive(self):
        dv = cr.Drive()
        drive_def_1 = {
            'name': 'test_drive_1',
            'size': '1024000000',
            'media': 'disk',
        }
        drive1 = dv.create(drive_def_1)
        self._wait_for_status(drive1['uuid'], 'unmounted', client=dv)

        dv = cr.Drive()
        drive_def_2 = {
            'name': 'test_drive_2',
            'size': '1024000000',
            'media': 'cdrom',
        }
        drive2 = dv.create(drive_def_2)
        self._wait_for_status(drive2['uuid'], 'unmounted', client=dv)

        server_def = {
            'name': 'testServerAcc',
            'cpu': 1000,
            'mem': 512 * 1024 ** 2,
            'vnc_password': 'testserver',
            'drives': [
                {
                    "device": "virtio",
                    "dev_channel": "0:0",
                    "drive": drive1['uuid'],
                    "boot_order": 1
                },
                {
                    "device": "virtio",
                    "dev_channel": "0:1",
                    "drive": drive2['uuid'],
                    "boot_order": 2
                },

            ],
            "nics": [
                {
                    "ip_v4_conf": {
                        "ip": None,
                        "conf": "dhcp"
                    },
                    "model": "virtio",
                }
            ],
        }

        server = self.client.create(server_def)

        clone = self.client.clone(server['uuid'], {'name': 'cloned server name', 'random_vnc_password': True})

        for mount in clone['drives']:
            drive_uuid = mount['drive']['uuid']
            self._wait_for_status(drive_uuid, 'mounted', client=dv)

        self.assertNotEqual(clone['drives'][0]['drive']['uuid'], server['drives'][0]['drive']['uuid'])
        self.assertEqual(clone['drives'][1]['drive']['uuid'], server['drives'][1]['drive']['uuid'])

        self.client.delete_with_all_drives(server['uuid'])
        self.client.delete_with_disks(clone['uuid'])

        self._wait_deleted(server['drives'][0]['drive']['uuid'], client=dv)
        self._wait_deleted(server['drives'][1]['drive']['uuid'], client=dv)
        self._wait_deleted(clone['drives'][0]['drive']['uuid'], client=dv)

    def test_server_clone_with_avoid_drive(self):
        dv = cr.Drive()
        drive_def_1 = {
            'name': 'test_drive_1',
            'size': '1024000000',
            'media': 'disk',
        }
        drive1 = dv.create(drive_def_1)
        self._wait_for_status(drive1['uuid'], 'unmounted', client=dv)

        dv = cr.Drive()
        drive_def_2 = {
            'name': 'test_drive_2',
            'size': '1024000000',
            'media': 'cdrom',
        }
        drive2 = dv.create(drive_def_2)
        self._wait_for_status(drive2['uuid'], 'unmounted', client=dv)

        server_def = {
            'name': 'testServerAcc',
            'cpu': 1000,
            'mem': 512 * 1024 ** 2,
            'vnc_password': 'testserver',
            'drives': [
                {
                    "device": "virtio",
                    "dev_channel": "0:0",
                    "drive": drive1['uuid'],
                    "boot_order": 1
                },
                {
                    "device": "virtio",
                    "dev_channel": "0:1",
                    "drive": drive2['uuid'],
                    "boot_order": 2
                },

            ],
            "nics": [
                {
                    "ip_v4_conf": {
                        "ip": None,
                        "conf": "dhcp"
                    },
                    "model": "virtio",
                }
            ],
        }

        server = self.client.create(server_def)

        clone = self.client.clone(server['uuid'], {'name': 'cloned server name', 'random_vnc_password': True},
                                  avoid=[server['uuid']])

        for mount in clone['drives']:
            drive_uuid = mount['drive']['uuid']
            self._wait_for_status(drive_uuid, 'mounted', client=dv)

        self.assertNotEqual(clone['drives'][0]['drive']['uuid'], server['drives'][0]['drive']['uuid'])
        self.assertEqual(clone['drives'][1]['drive']['uuid'], server['drives'][1]['drive']['uuid'])

        self.client.delete_with_all_drives(server['uuid'])
        self.client.delete_with_disks(clone['uuid'])

        self._wait_deleted(server['drives'][0]['drive']['uuid'], client=dv)
        self._wait_deleted(server['drives'][1]['drive']['uuid'], client=dv)
        self._wait_deleted(clone['drives'][0]['drive']['uuid'], client=dv)


@attr('stress_test')
class ServerStressTest(StatefulResourceTestBase):
    SERVER_COUNT = 60

    def setUp(self):
        super(ServerStressTest, self).setUp()
        self.server_client = cr.Server()
        self.drive_client = cr.Drive()

    def test_create_start_test_io(self):
        """Servers create, start, test drive io and stop"""

        server_req = []
        puuid, ppass = self._get_persistent_image_uuid_and_pass()

        cloned = []
        for num in range(self.SERVER_COUNT):
            cloned.append(self.drive_client.clone(puuid, {'name': "stress_atom_clone_{}".format(num)}))

        for i, drive in enumerate(cloned):
            server_req.append({
                'name': 'stress_drive_iops_%i' % i,
                'cpu': 500,
                'mem': 512 * 1024 ** 2,
                'vnc_password': 'testserver',
                'drives': [
                    {
                        "device": "virtio",
                        "dev_channel": "0:0",
                        "drive": drive['uuid'],
                        "boot_order": 1
                    },
                ],
                'nics': [
                    {
                        "ip_v4_conf": {
                            "ip": None,
                            "conf": "dhcp"
                        },
                        "model": "virtio",
                    }
                ],

            })

        servers = self.server_client.create(server_req)
        sip_map = {}

        for cloning_drive in cloned:
            self._wait_for_status(cloning_drive['uuid'], status='mounted', client=self.drive_client, timeout=120*1000)

        for server in servers:
            self.server_client.start(server['uuid'])

        for server in servers:
            self._wait_for_status(server['uuid'], status='running', client=self.server_client)

        for server in self.server_client.list_detail():
            sip_map[server['uuid']] = server['runtime']['nics'][0]['ip_v4']

        for server in servers:
            self.server_client.stop(server['uuid'])


