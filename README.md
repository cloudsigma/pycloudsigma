# CloudSigma Python Library

## Config file

In order for the CloudSigma library to be able to authenticate with the server, you need to provide your credentials. These are set in the file `~/.cloudsigma.conf`. Here's a sample version of the file that talks to the Las Vegas datacenter. If you instead want to use the Zürich datacenter, simply replace 'lvs' with 'zrh' in the api_endpoint and ws_endpoint.

    api_endpoint = https://lvs.cloudsigma.com/api/2.0/
    ws_endpoint = wss://direct.lvs.cloudsigma.com/websocket
    username = user@domain.com
    password = secret

    # Only needed for the integration/unit tests.
    persistent_drive_name=foobar
    persistent_drive_ssh_password=sshsecret

Since this file includes credentials, it is highly recommended that you set the permission of the file to 600 (`chmod 600 ~/.cloudsigma.conf`)


## Installation

    pip install cloudsigma

## Using pycloudsigma

#### Create a drive

    import cloudsigma
    drive = cloudsigma.resource.Drive()
    test_disk = { 'name': 'test_drive', 'size': 1024000000, 'media': 'disk'}
    my_test_disk = drive.create(test_disk)
    print my_test_disk

### Create a server without a drive

    server = cloudsigma.resource.Server()
    test_server = { 'name': 'My Test Server', 'cpu': 1000, 'mem': 512 * 1024 ** 2, 'vnc_password': 'test_server' }
    my_test_server = server.create(test_server)
    print my_test_server


### Attach a drive the drive to the server

We could of course have attached this above, but in order to keep things simple, let's do this in to phases.

    test_server['drives'] = [ { 'boot_order': 1, 'dev_channel': '0:0', 'device': 'virtio', 'drive': my_test_disk['uuid'] } ]
    server.update(my_test_server['uuid'], test_server)

### Start the server

    server.start(my_test_server['uuid'])

### Stop the server

    server.stop(my_test_server['uuid'])

### Reading Meta Data

CloudSigma supports the notion of exposing meta data to guests. Using the Python library, this can be done very easily. **Please note** that you do not need to provide any credentials (or information) in `~/.cloudsigma.com` in order to use this feature. This data is read directly from `/dev/ttyS1`. More information on how to this works can be found [here](https://lvs.cloudsigma.com/docs/server_context.html#setting-up-the-virtual-serial-port).

By default, various system information is exposed, but it is also possible to push user-defined data, such as an SSH-key to the guest.

Here's snippet that demonstrates how to read the meta meta data from a given server using the python library:

    import cloudsigma
    metadata = cloudsigma.metadata.GetServerMetadata().get()

    from pprint import pprint
    pprint(metadata)
    {u'cpu': 1000,
     u'cpus_instead_of_cores': False,
     u'drives': [{u'boot_order': 1,
                  u'dev_channel': u'0:0',
                  u'device': u'virtio',
                  u'drive': {u'affinities': [],
                             u'allow_multimount': False,
                             u'licenses': [],
                             u'media': u'disk',
                             u'meta': {u'description': u'This is my test disk.'},
                             u'name': u'SomeName',
                             u'size': 21474836480,
                             u'tags': [],
                             u'uuid': u'19757XXX-8173-46ba-8822-YYYYc6bZZZZ'}}],
     u'enable_numa': False,
     u'hv_relaxed': False,
     u'hv_tsc': False,
     u'mem': 536870912,
     u'meta': {u'description': u'This is my test server.'},
     u'name': u'vpn',
     u'nics': [{u'boot_order': None,
                u'ip_v4_conf': {u'conf': u'dhcp',
                                u'ip': {u'gateway': u'123.123.123.123',
                                        u'meta': {},
                                        u'nameservers': [u'123.123.123.123',
                                                         u'123.123.123.123',
                                                         u'8.8.8.8'],
                                        u'netmask': 24,
                                        u'tags': [],
                                        u'uuid': u'123.123.123.123'}},
                u'ip_v6_conf': None,
                u'mac': u'22:bd:c4:XX:XX:XX',
                u'model': u'virtio',
                u'vlan': None}],
     u'requirements': [],
     u'smp': 1,
     u'tags': [],
     u'uuid': u'6cc0XXX-d024-4ecf-b0de-83dbc29ZZZ',
     u'vnc_password': u'NotMyPassword'}

For more examples on how to read and write meta data, please visit our [API Documentation](https://autodetect.cloudsigma.com/docs/meta.html#examples).

## Sample application: Monitor websocket activity

Here's a sample application that listens to activity on the websocket. You can run this application to see activity from the web interface.

    from cloudsigma.generic import GenericClient
    from cloudsigma.resource import Websocket
    from cloudsigma.errors import ClientError

    ws = Websocket(timeout=None)
    client = GenericClient()

    print "Display Websocket activity.\nExit with ^C."

    while True:
        try:
            get_action = ws.ws.recv()
            action_uri = get_action['resource_uri']
            print 'Received Action: %s' % get_action
            print 'Result:\n%s' % client.get(action_uri)
        except ClientError as e:
            print 'Error retrieving: %s' % e

## Running the tests

There must be a VM available by the name that matches `persistent_drive_name`. This VM should be a server with SSH installed, where one can be log in as `root` with the password set in `persistent_drive_ssh_password`.

