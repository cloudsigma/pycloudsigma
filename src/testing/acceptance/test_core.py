__author__ = 'islavov'

from testing.acceptance import common

import cloudsigma.resource as cr
import cloudsigma.generic as gc
from unittest import SkipTest
import logging

LOG = logging.getLogger(__name__)


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
