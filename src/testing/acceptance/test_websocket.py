import unittest
from nose.plugins.attrib import attr
from cloudsigma import resource
from cloudsigma import errors


@attr('acceptance_test')
class WebsocketTest(unittest.TestCase):
    def setUp(self):
        super(WebsocketTest, self).setUp()

    def test_drive(self):
        ws = resource.Websocket()
        d = resource.Drive().create({"size": 1000 ** 3, "name": "", "media": "disk"})
        ret = ws.wait_obj_wrapper(ws.wait_obj_uri, (d['resource_uri'], resource.Drive), timeout=30,
                                  extra_filter=lambda x: x['status'] == 'unmounted')
        resource.Drive().delete(d['uuid'])
        try:
            ret = ws.wait_obj_wrapper(ws.wait_obj_uri, (d['resource_uri'], resource.Drive), timeout=30,
                                      extra_filter=lambda x: False)
        except errors.ClientError as e:
            if e.args[0] != 404:
                raise

    def test_guest(self):
        ws = resource.Websocket()
        g = resource.Server().create({"cpu": 1000, "name": "", "mem": 256 * 1024 ** 2, "vnc_password": "foo"})
        ret = ws.wait_obj_wrapper(ws.wait_obj_uri, (g['resource_uri'], resource.Server), timeout=30,
                                  extra_filter=lambda x: x['status'] == 'stopped')
        resource.Server().start(g['uuid'])
        ret = ws.wait_obj_wrapper(ws.wait_obj_uri, (g['resource_uri'], resource.Server), timeout=30,
                                  extra_filter=lambda x: x['status'] == 'running')
        resource.Server().stop(g['uuid'])
        ret = ws.wait_obj_wrapper(ws.wait_obj_uri, (g['resource_uri'], resource.Server), timeout=30,
                                  extra_filter=lambda x: x['status'] == 'stopped')
        resource.Server().delete(g['uuid'])
        try:
            g = ws.wait_obj_wrapper(ws.wait_obj_uri, (ret['resource_uri'], resource.Server), timeout=30,
                                    extra_filter=lambda x: False)
        except errors.ClientError as e:
            if e.args[0] != 404:
                raise

    def test_guest_drive(self):
        ws = resource.Websocket()
        g = resource.Server().create({"cpu": 1000, "name": "", "mem": 256 * 1024 ** 2, "vnc_password": "foo"})
        ret = ws.wait_obj_wrapper(ws.wait_obj_uri, (g['resource_uri'], resource.Server), timeout=30,
                                  extra_filter=lambda x: x['status'] == 'stopped')
        d = resource.Drive().create({"size": 1000 ** 3, "name": "", "media": "disk"})
        ret = ws.wait_obj_wrapper(ws.wait_obj_uri, (d['resource_uri'], resource.Drive), timeout=30,
                                  extra_filter=lambda x: x['status'] == 'unmounted')

        resource.Server().update(g['uuid'], {"cpu": 1000, "name": "", "mem": 256 * 1024 ** 2, "vnc_password": "foo",
                                             "drives": [
                                                 {"dev_channel": "0:0", "device": "virtio", "drive": d['uuid']}]})
        ws.wait_obj_uri(g['resource_uri'], resource.Server)
        resource.Drive().delete(d['uuid'])
        resource.Server().delete(g['uuid'])

