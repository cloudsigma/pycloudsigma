import unittest
from nose.plugins.attrib import attr
import time
import cloudsigma.resource as resources
import cloudsigma.errors as errors


@unittest.skip('Skip until fixed to work properly for slow drive operations')
@attr('acceptance_test')
class ServerTestBase(unittest.TestCase):
    def setUp(self):
        super(ServerTestBase, self).setUp()

    def test_websocket(self):
        ws = resource.Websocket()
        d = resource.Drive().create({"size": 1000 ** 3, "name": "", "media": "disk"})
        ret = ws.wait_obj_type("drives", resource.Drive)
        print ret
        ret = ws.wait_obj_type("drives", resource.Drive)
        print ret
        resource.Drive().delete(ret['uuid'])
        time.sleep(1)
        try:
            ws.wait_obj_type("drives", resource.Drive)
        except errors.ClientError as e:
            if e.args[0] == 404:
                return
            raise
