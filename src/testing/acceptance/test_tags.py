from nose.plugins.attrib import attr
from testing.acceptance.common import StatefulResourceTestBase
from testing.utils import DumpResponse
import cloudsigma.resource as cr


@attr('acceptance_test')
class tagsTest(StatefulResourceTestBase):
    def setUp(self):
        super(tagsTest, self).setUp()
        self.client = cr.Tags()
        self.dump_response = DumpResponse(clients=[self.client])

        tags = self.client.list()

        for tag in tags:
            self.client.delete(tag['uuid'])

    @attr('docs_snippets')
    def test_tags(self):
        with self.dump_response('tags_schema'):
            self.client.get_schema()

        sc = cr.Server()
        server1 = sc.create({'name': 'test_server1', 'cpu': 1000, 'mem': 512*1024**2, 'vnc_password': 'pass'})
        server2 = sc.create({'name': 'test_server2', 'cpu': 1000, 'mem': 512*1024**2, 'vnc_password': 'pass'})

        dc = cr.Drive()
        drive = dc.create({'name': 'test_drive', 'size': 1000**3, 'media': 'disk'})

        ip = cr.IP().list()[0]
        vlan = cr.VLAN().list()[0]

        with self.dump_response('tags_create'):
            tag1 = self.client.create({'name': 'MyGroupOfThings'})

        with self.dump_response('tags_create_with_resource'):
            tag2 = self.client.create({'name': 'TagCreatedWithResource',
                                       'resources': [server1['uuid'], server2['uuid'], drive['uuid'], ip['uuid'],
                                                     vlan['uuid']]})
        with self.dump_response('tags_list'):
            self.client.list()

        with self.dump_response('tags_list_detail'):
            self.client.list_detail()

        with self.dump_response('tags_get'):
            self.client.get(tag2['uuid'])

        with self.dump_response('tags_update_resources'):
            self.client.update(tag2['uuid'], {'name': 'TagCreatedWithResource', 'resources': [server1['uuid'],
                                                                                              drive['uuid']]})

        server2['tags'] = [tag1['uuid'], tag2['uuid']]
        with DumpResponse(clients=[sc], name='tags_update_tag_from_resource'):
            sc.update(server2['uuid'], server2)

        with self.dump_response('tags_list_resource'):
            self.client.servers(tag1['uuid'])

        dc.delete(drive['uuid'])
        sc.delete(server1['uuid'])
        sc.delete(server2['uuid'])

        with self.dump_response('tags_delete'):
            self.client.delete(tag1['uuid'])
        self.client.delete(tag2['uuid'])
