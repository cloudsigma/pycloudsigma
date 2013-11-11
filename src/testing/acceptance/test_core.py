import json
import os
from nose.plugins.attrib import attr
from testing.utils import DumpResponse

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

        self._wait_for_open_socket(ip1, 22, timeout=60, close_on_success=True)
        self._wait_for_open_socket(ip2, 22, timeout=40, close_on_success=True)

        from fabric.api import settings as fabric_settings
        from fabric import tasks, api

        fab_kwargs = {
            "warn_only": True,
            "abort_on_prompts": True,
            "use_ssh_config": p_pass is None
        }
        LOG.debug('Using fabric config {}'.format(fab_kwargs))
        if p_pass is not None:
            fab_kwargs['password'] = p_pass
            LOG.debug('Using a password to SSH to the servers ( not using ssh config )')

        with fabric_settings(**fab_kwargs):
            LOG.debug('Changing hostnames and restarting avahi on guest 1')
            set_hostname = 'hostname {} && service avahi-daemon restart'
            tasks.execute(
                api.run,
                set_hostname.format("atom1"),
                hosts=["root@%s" % ip1]
            )

            LOG.debug('Changing hostnames and restarting avahi on guest 2')
            tasks.execute(
                api.run,
                set_hostname.format("atom2"),
                hosts=["root@%s" % ip2]
            )

            LOG.debug('Ping the two hosts via private network')
            ping_res = tasks.execute(
                api.run,
                "ping atom2.local -c 1",
                hosts=["root@%s" % ip1]
            )
            self.assertEqual(ping_res.values()[0].return_code, 0, 'Could not ping host atom2 from atom1')

            LOG.debug('Halt both servers')
            tasks.execute(
                api.run,
                "halt",
                hosts=["root@%s" % ip1, "root@%s" % ip2]
            )

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

    def get_single_ctx_val(self, command, expected_val, fab_kwargs, ip1, fabric_settings, tasks, api):
        with fabric_settings(**fab_kwargs):
            # TODO: Remove this retry when proper guest context client is implemented
            res_string = None
            for retry in xrange(5):
                if retry > 0:
                    LOG.warning('Retrying guest context single value execution {}'.format(retry))
                ctx_val_res = tasks.execute(
                    api.run,
                    command,
                    hosts=["root@%s" % ip1]
                )

                res_string = ctx_val_res.values()[0]
                if res_string == expected_val:
                    break
        return res_string

    def get_full_ctx(self, command, fab_kwargs, ip1, fabric_settings, tasks, api):
        with fabric_settings(**fab_kwargs):
            res_string = ''
            # TODO: Remove this retry when proper guest context client is implemented
            ctx_res_json = {}
            for retry in xrange(5):
                if retry > 0:
                    LOG.warning('Retrying guest context whole definition execution {}'.format(retry))
                try:
                    ctx_res = tasks.execute(
                        api.run,
                        command,
                        hosts=["root@%s" % ip1]
                    )
                    res_string = ctx_res.values()[0]
                    ctx_res_json = json.loads(res_string)
                except:
                    continue
                else:
                    break

        return ctx_res_json, res_string

    def dump_ctx_command(self, command, res_string, op_name, dump_path):
        with open(os.path.join(dump_path, 'request_' + op_name), 'w') as dump_file:
            dump_file.write(command)
        with open(os.path.join(dump_path, 'response_' + op_name), 'w') as dump_file:
            dump_file.write(res_string)

    def check_key_retrieval(self, g_def, op_name, ctx_path, dump_path, fab_kwargs, ip1, fabric_settings, tasks, api):
        command = self.command_template.format(ctx_path)
        expected_val = g_def
        for path_el in ctx_path.split('/'):
            if path_el:  # non-empty string
                expected_val = expected_val.get(path_el)
        res_string = self.get_single_ctx_val(command, expected_val, fab_kwargs, ip1, fabric_settings, tasks, api)
        self.assertEqual(res_string, expected_val)
        self.dump_ctx_command(command, res_string, op_name, dump_path)

    def check_all_retrieval(self, g_def, op_name, dump_path, fab_kwargs, ip1, fabric_settings, tasks, api):
        command = self.command_template.format('')
        ctx_res_json, res_string = self.get_full_ctx(command, fab_kwargs, ip1, fabric_settings, tasks, api)
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

        self._wait_for_open_socket(ip1, 22, timeout=60, close_on_success=True)

        from fabric.api import settings as fabric_settings
        from fabric import tasks, api

        fab_kwargs = {
            "warn_only": True,
            "abort_on_prompts": True,
            "use_ssh_config": p_pass is None
        }
        LOG.debug('Using fabric config {}'.format(fab_kwargs))
        if p_pass is not None:
            fab_kwargs['password'] = p_pass
            LOG.debug('Using a password to SSH to the servers ( not using ssh config )')

        dump_path = dump_response.response_dump.dump_path

        #command_template = r"read -t 1 -d $'\004' DISCARD < /dev/ttyS1; " \
        #                   r'echo -en "<\n{}\n>" > /dev/ttyS1 && read -t 3 READVALUE < /dev/ttyS1 && echo $READVALUE'
        self.command_template = r'v=$(read -t 13 READVALUE < /dev/ttyS1 && echo $READVALUE & sleep 1; echo -en "<\n{}\n>" > /dev/ttyS1; wait %1); echo $v'

        LOG.debug('Test the guest context')

        LOG.debug('Check single value retrieval')
        self.check_key_retrieval(g_def, 'context_single_value', 'name', dump_path, fab_kwargs, ip1, fabric_settings,
                                 tasks, api)


        ##########################################
        LOG.debug('Check key retrieval')
        self.check_key_retrieval(g_def, 'context_single_value_ssh_key', '/meta/ssh_public_key', dump_path, fab_kwargs, ip1,
                         fabric_settings, tasks, api)

        ##########################################
        LOG.debug('Check complete context retrieval')
        self.check_all_retrieval(g_def, 'context_all', dump_path, fab_kwargs, ip1, fabric_settings, tasks, api)

        ##########################################
        ##########################################
        ##########################################
        ##########################################
        LOG.debug('Check context dynamic update')
        g_def['name'] += '_renamed'
        g_def['meta']['another_key'] = 'a value or something'

        upd_res = sc.update(g1['uuid'], g_def)
        self.assertEqual(g_def['name'], upd_res['name'])

        LOG.debug('Check single value retrieval')

        self.check_key_retrieval(g_def, 'context_single_value_dynamic', 'name', dump_path, fab_kwargs, ip1,
                                fabric_settings, tasks, api)

        ##########################################
        LOG.debug('Check key retrieval')
        self.check_key_retrieval(g_def, 'context_single_value_another_key_dynamic', '/meta/another_key', dump_path,
                                 fab_kwargs, ip1, fabric_settings, tasks, api)

        ##########################################
        LOG.debug('Check complete context retrieval')
        self.check_all_retrieval(g_def, 'context_all_dynamic', dump_path, fab_kwargs, ip1, fabric_settings, tasks, api)

        ###########################################
        ###########################################
        ###########################################
        with dump_response('update_global_context'):
            gcc.update({'new_global_key': 'new_global_val'})

        LOG.debug('Check global context retrieval')
        command = self.command_template.format('/global_context/new_global_key')
        expected_val = 'new_global_val'
        res_string = self.get_single_ctx_val(command, expected_val, fab_kwargs, ip1, fabric_settings, tasks, api)
        self.assertEqual(res_string, expected_val)
        self.dump_ctx_command(command, res_string, 'global_context_single_value', dump_path)

        self.check_all_retrieval(g_def, 'global_context_all', dump_path, fab_kwargs, ip1, fabric_settings, tasks, api)




        LOG.debug('Stopping guest')
        sc.stop(g1['uuid'])
        self._wait_for_status(g1['uuid'], 'stopped', client=sc, timeout=40)

        LOG.debug('Delete guest')
        sc.delete(g1['uuid'])

        LOG.debug('Delete drive')
        dc.delete(d1['uuid'])
        self._wait_deleted(d1['uuid'], client=dc)



    def test_firewall(self):
        dc = cr.Drive()
        sc = cr.Server()
        fwp = cr.FirewallPolicy()

        puuid, p_pass = self._get_persistent_image_uuid_and_pass()

        LOG.debug('Clone the persistent image')
        d1 = dc.clone(puuid, {'name': 'test_atom_clone_1'})
        self._wait_for_status(d1['uuid'], status='unmounted', timeout=self.TIMEOUT_DRIVE_CLONING, client=dc)

        fw_policy = fwp.create({})

        g_def = {
            "name": "testFirewallServer",
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
                    "firewall_policy": fw_policy['uuid'],
                    "ip_v4_conf": {
                        "ip": None,
                        "conf": "dhcp"
                    },
                    "model": "virtio",
                },
            ],
        }

        guest = sc.create(g_def)
        self._wait_for_status(d1['uuid'], 'mounted', client=dc)

        sc.start(guest['uuid'])

        self._wait_for_status(guest['uuid'], 'running', client=sc)
        guest = sc.get(guest['uuid'])
        ip1 = guest['nics'][0]['runtime']['ip_v4']["uuid"]

        self._wait_for_open_socket(ip1, 22, timeout=60, close_on_success=True)

        fw_policy['rules'] = [
            {
                "ip_proto": "tcp",
                "dst_port": 22,
                "direction": "in",
                "action": "drop",
                "comment": "Block SSH traffic"
            }
        ]

        fwp.update(fw_policy['uuid'], fw_policy)

        self._wait_socket_close(ip1, 22)

        fw_policy['rules'] = []

        fwp.update(fw_policy['uuid'], fw_policy)
        self._wait_for_open_socket(ip1, 22)

        sc.stop(guest['uuid'])
        self._wait_for_status(guest['uuid'], 'stopped', client=sc)
        sc.delete(guest['uuid'])

        fwp.delete(fw_policy['uuid'])
