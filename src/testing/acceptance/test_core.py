import json
import os
import re
from nose.plugins.attrib import attr
from testing.utils import DumpResponse
from invoke.exceptions import UnexpectedExit
from . import common

from cloudsigma import resource as cr
from cloudsigma import generic as gc
from unittest import SkipTest
import logging

LOG = logging.getLogger(__name__)

@attr('acceptance_test')
class TestCoreFuncs(common.StatefulResourceTestBase):

    def test_servers_operations(self):

        dc = cr.Drive()
        sc = cr.Server()
        vc = cr.VLAN()

        puuid, p_pass = self._get_persistent_image_uuid_and_pass()

        LOG.debug('Get a vlan from the account')
        all_vlans = vc.list()
        if not all_vlans:
            raise SkipTest('There is no vlan in the acceptance test account')
        vlan = all_vlans[0]

        LOG.debug('Clone the persistent image')
        d1 = dc.clone(puuid, {'name': 'test_atom_clone_1'})
        self._wait_for_status(d1['uuid'], status='unmounted', timeout=self.TIMEOUT_DRIVE_CLONING, client=dc)

        g_def = {
            "name": "test_server",
            "cpu": 1000,
            "mem": 1024 ** 3,
            'vnc_password': 'testserver',
            'drives': [
                {
                    "device": "virtio",
                    "dev_channel": "0:0",
                    "drive": d1['uuid'],
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
                },
                {
                    "model": "virtio",
                    "vlan": vlan['uuid'],

                }
            ],
        }

        LOG.debug('Creating guest with drive')
        g1 = sc.create(g_def)
        self._wait_for_status(d1['uuid'], 'mounted', client=dc)

        LOG.debug('Clone the guest')
        g2 = sc.clone(g1['uuid'])
        self._wait_for_status(g2['uuid'], 'stopped', client=sc)

        LOG.debug('Check if the drive is active ( mounted )')
        d2_uuid = g2['drives'][0]['drive']['uuid']
        self._wait_for_status(d2_uuid, 'mounted', client=dc)

        LOG.debug('Start both guests')
        sc.start(g1['uuid'])
        sc.start(g2['uuid'])

        self._wait_for_status(g1['uuid'], 'running', client=sc)
        self._wait_for_status(g2['uuid'], 'running', client=sc)

        LOG.debug('Refetch guest configurations')
        g1 = sc.get(g1['uuid'])
        g2 = sc.get(g2['uuid'])

        LOG.debug('Get the assigned ips')
        ip1 = g1['nics'][0]['runtime']['ip_v4']["uuid"]
        ip2 = g2['nics'][0]['runtime']['ip_v4']["uuid"]

        self._wait_for_open_socket(ip1, 22, timeout=300, close_on_success=True)
        self._wait_for_open_socket(ip2, 22, timeout=300, close_on_success=True)

        from fabric import Connection

        LOG.debug('Using a password to SSH to the servers ( not using ssh config )')

        self.ssh_host1 = "root@" + ip1
        connection_host1 = Connection(host=self.ssh_host1,
                                      connect_kwargs={"password": p_pass})

        self.ssh_host2 = "root@" + ip2
        connection_host2 = Connection(host=self.ssh_host2,
                                      connect_kwargs={"password": p_pass})

        LOG.debug('Changing hostnames and restarting avahi on guest 1')

        self.run_command = 'hostname {} && service avahi-daemon restart'.format("atom1")
        self.cmd_exec_res = connection_host1.run(self.run_command).stderr.replace('\n', '')
        print(self.cmd_exec_res)

        LOG.debug('Changing hostnames and restarting avahi on guest 2')

        self.run_command = 'hostname {} && service avahi-daemon restart'.format("atom2")
        self.cmd_exec_res = connection_host2.run(self.run_command).stderr.replace('\n', '')
        print(self.cmd_exec_res)

        #LOG.debug('Ping the two hosts via private network')

        #self.run_command = 'ping atom2.local -c 1'
        #cmd_exec_res = connection_host1.run(self.run_command).stdout.replace('\n', '')
        #self.assertEqual(cmd_exec_res, 0, 'Could not ping host atom2 from atom1')

        LOG.debug('poweroff both servers')

        self.run_command = 'poweroff'
        with self.assertRaises(UnexpectedExit):
            self.cmd_exec_res = connection_host1.run(self.run_command)
        print(self.cmd_exec_res)

        self.run_command = 'poweroff'
        with self.assertRaises(UnexpectedExit):
            self.cmd_exec_res = connection_host2.run(self.run_command)
        print(self.cmd_exec_res)

        LOG.debug('Wait for complete shutdown')
        self._wait_for_status(g1['uuid'], 'stopped', client=sc, timeout=40)
        self._wait_for_status(g2['uuid'], 'stopped', client=sc)

        LOG.debug('Deleting both guests')
        sc.delete(g1['uuid'])
        sc.delete(g2['uuid'])

        LOG.debug('Deleting both drives')
        dc.delete(d1['uuid'])
        dc.delete(d2_uuid)

        self._wait_deleted(d1['uuid'], client=dc)
        self._wait_deleted(d2_uuid, client=dc)

    def get_single_ctx_val(self, command, expected_val, connection):
        # TODO: Remove this retry when proper guest context client is implemented
        res_string = None
        for retry in range(5):
            if retry > 0:
                LOG.warning('Retrying guest context single value execution {}'.format(retry))
            ctx_val_res = connection.run(command)
            res_string = ctx_val_res.stdout.replace('\n', '')
            if res_string == expected_val:
                break
        return res_string

    def get_full_ctx(self, command, connection):
        #
        res_string = ''
        # TODO: Remove this retry when proper guest context client is implemented
        ctx_res_json = {}
        for retry in range(5):
            if retry > 0:
                LOG.warning('Retrying guest context whole definition execution {}'.format(retry))
            try:
                ctx_res = connection.run(command)
                res_string = ctx_res.stdout.replace('\n', '')
                res_string = re.sub('"{', "{", res_string)
                res_string = re.sub('}"', "}", res_string)
                ctx_res_json = json.loads(res_string)
            except:
                continue
            else:
                break

        return ctx_res_json, res_string

    def dump_ctx_command(self, command, res_string, op_name,
                         dump_path):
        with open(os.path.join(dump_path, 'request_' + op_name), 'w') as dump_file:
            dump_file.write(command)
        with open(os.path.join(dump_path, 'response_' + op_name), 'w') as dump_file:
            dump_file.write(res_string)

    def check_key_retrieval(self, g_def, op_name, ctx_path, dump_path,
                            connection):
        command = self.command_template.format(ctx_path)
        expected_val = g_def
        for path_el in ctx_path.split('/'):
            if path_el:  # non-empty string
                expected_val = expected_val.get(path_el)
        res_string = self.get_single_ctx_val(command, expected_val, connection)
        self.assertEqual(res_string, expected_val)
        self.dump_ctx_command(command, res_string, op_name, dump_path)

    def check_all_retrieval(self, g_def, op_name, dump_path, connection):
        command = self.command_template.format('')
        ctx_res_json, res_string = self.get_full_ctx(command, connection)

        for k, v in g_def.items():
            if not isinstance(v, (list, dict)):
                self.assertEqual(v, ctx_res_json[k])
        self.dump_ctx_command(command, res_string, op_name, dump_path)

    @attr('docs_snippets')
    def test_guest_context(self):
        dc = cr.Drive()
        sc = cr.Server()
        gcc = cr.GlobalContext()
        dump_response = DumpResponse(clients=[sc, dc, gcc])
        # ensure empty global context
        gcc.update({})

        puuid, p_pass = self._get_persistent_image_uuid_and_pass()
        LOG.debug('Clone the persistent image')
        d1 = dc.clone(puuid, {'name': 'test_clone_1'})
        from uuid import uuid4
        g_def = {
            "name": "test_server",
            "cpu": 1000,
            "mem": 1024 ** 3,
            'vnc_password': str(uuid4())[:18].replace('-', ''),
            'drives': [
                {
                    "device": "virtio",
                    "dev_channel": "0:0",
                    "drive": d1['uuid'],
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
                },
            ],
            "meta": {
                "ssh_public_key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCy4XpmD3kEfRZ+LCwFh3Xmqrkm7rSiDu8v+ZCTOA3vlNjmy/ZOc3vy9Zr+IhWPP4yipiApkGRsBM63tTgnxqUUn/WU7qkbBNktZBcs5p7Mj/zO4ZHkk4VoTczFzHlPGwuak2P4wTftEj7sU8IRutaAbMoKj4AMuFF50j4sIgF7P5b5FtTIM2b5HSW8BlDz10b67+xsj6s3Jv05xxbBs+RWj+v7D5yjMVeeErXoSui8dlHpUu6QOVKn8LLmdpxvehc6ns8yW7cbQvWmLjOICMnm6BXdVtOKWBncDq9FGLmKF3fUeZZPbv79Z7dyZs+xGZGMHbpaNHpuY9QhNS/hQ5D5 dave@hal"
            }
        }

        LOG.debug('Creating guest with drive')

        with dump_response('guest_for_context'):
            g1 = sc.create(g_def)

        self._wait_for_status(d1['uuid'], 'mounted', client=dc)

        sc.start(g1['uuid'])

        self._wait_for_status(g1['uuid'], 'running', client=sc)

        LOG.debug('Refetch guest configurations')

        g1 = sc.get(g1['uuid'])

        LOG.debug('Get the assigned ips')
        ip1 = g1['nics'][0]['runtime']['ip_v4']["uuid"]

        self._wait_for_open_socket(ip1, 22, timeout=300, close_on_success=True)

        from fabric import Connection

        self.ssh_host = "root@" + ip1
        connection = Connection(host=self.ssh_host,
                                connect_kwargs={"password": p_pass})

        LOG.debug('Using a password to SSH to the servers ( not using ssh config )')

        dump_path = dump_response.response_dump.dump_path

        #command_template = r"read -t 1 -d $'\004' DISCARD < /dev/ttyS1; " \
        #                   r'echo -en "<\n{}\n>" > /dev/ttyS1 && read -t 3 READVALUE < /dev/ttyS1 && echo $READVALUE'
        self.command_template = r'v=$(read -t 13 READVALUE < /dev/ttyS1 && echo $READVALUE & sleep 1; echo -en "<\n{}\n>" > /dev/ttyS1; wait %1); echo $v'

        LOG.debug('Test the guest context')

        LOG.debug('Check single value retrieval')

        self.check_key_retrieval(g_def, 'context_single_value', 'name',
                                 dump_path, connection)

        LOG.debug('Check key retrieval')
        self.check_key_retrieval(g_def, 'context_single_value_ssh_key',
                                 '/meta/ssh_public_key', dump_path, connection)

        LOG.debug('Check complete context retrieval')
        self.check_all_retrieval(g_def, 'context_all', dump_path, connection)

        LOG.debug('Check context dynamic update')
        g_def['name'] += '_renamed'
        g_def['meta']['another_key'] = 'a value or something'

        upd_res = sc.update(g1['uuid'], g_def)
        self.assertEqual(g_def['name'], upd_res['name'])

        LOG.debug('Check single value retrieval')

        self.check_key_retrieval(g_def, 'context_single_value_dynamic', 'name',
                                 dump_path, connection)

        LOG.debug('Check key retrieval')
        self.check_key_retrieval(g_def,
                                 'context_single_value_another_key_dynamic',
                                 '/meta/another_key', dump_path, connection)

        LOG.debug('Check complete context retrieval')
        self.check_all_retrieval(g_def, 'context_all_dynamic',
                                 dump_path, connection)

        with dump_response('update_global_context'):
            gcc.update({'new_global_key': 'new_global_val'})

        LOG.debug('Check global context retrieval')
        command = self.command_template.format(
            '/global_context/new_global_key')
        expected_val = 'new_global_val'
        res_string = self.get_single_ctx_val(command, expected_val, connection)
        self.assertEqual(res_string, expected_val)
        self.dump_ctx_command(command, res_string,
                              'global_context_single_value', dump_path)

        self.check_all_retrieval(g_def,
                                 'global_context_all', dump_path, connection)

        LOG.debug('Stopping guest')
        sc.stop(g1['uuid'])
        self._wait_for_status(g1['uuid'], 'stopped', client=sc, timeout=40)

        LOG.debug('Delete guest')
        sc.delete(g1['uuid'])

        LOG.debug('Delete drive')
        dc.delete(d1['uuid'])

        self._wait_deleted(d1['uuid'], client=dc)

    # removed test_firewall because of flaky CloudSigma REST API.
