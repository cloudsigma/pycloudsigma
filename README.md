# CloudSigma's Python Library

## Config file

In order for the CloudSigma library to interact with the API, you need to provide your credentials. These are set in the file `~/.cloudsigma.conf`. Here's a sample version of the file that talks to the Zürich datacenter. If you instead want to use the Frankfurt datacenter, simply replace 'zrh' with 'fra' in the api_endpoint and ws_endpoint. Please note that this is not required in order to read back meta data on the server.


```python
api_endpoint = https://zrh.cloudsigma.com/api/2.0/
ws_endpoint = wss://direct.zrh.cloudsigma.com/websocket
username = user@domain.com
password = secret

# Only needed for the integration/unit tests.
persistent_drive_name=foobar
persistent_drive_ssh_password=sshsecret
```

Since this file includes credentials, it is highly recommended that you set the permission of the file to 600 (`chmod 600 ~/.cloudsigma.conf`)


## Installation


### Mac OS X

```bash
sudo pip install cloudsigma
```

### Ubuntu / Debian

```bash
sudo apt -y install python-pip
pip install cloudsigma
```

### CentOS / RHEL

```bash
yum install -y python3-pip
pip install cloudsigma
```

## Using pycloudsigma

### Imports and definitions

```python
import cloudsigma
from pprint import pprint

drive = cloudsigma.resource.Drive()
server = cloudsigma.resource.Server()
```

#### Create a drive

```python
test_disk = {
    'name': 'test_drive',
    'size': 1073741824 * 1,
    'media': 'disk'
}
my_test_disk = drive.create(test_disk)
```

Print back the result:

```python
pprint(my_test_disk)
{u'affinities': [],
 u'allow_multimount': False,
 u'jobs': [],
 u'licenses': [],
 u'media': u'disk',
 u'meta': {},
 u'mounted_on': [],
 u'name': u'test_drive',
 u'owner': {u'resource_uri': u'/api/2.0/user/b4b9XXX-ba52-4ad0-9837-a2672652XXX/',
            u'uuid': u'b4b9XXX-ba52-4ad0-9837-a2672652XXX'},
 u'resource_uri': u'/api/2.0/drives/5c33e407-23b9-XXX-b007-3a302eXXXX/',
 u'size': 1073741824,
 u'status': u'creating',
 u'storage_type': None,
 u'tags': [],
 u'uuid': u'5c33e407-23b9-XXX-b007-3a302eXXXX'}
```

### Create a server without a drive

```python
test_server = {
    'name': 'My Test Server',
    'cpu': 1000,
    'mem': 512 * 1024 ** 2,
    'vnc_password': 'test_server'
}
my_test_server = server.create(test_server)
```

Print back the result:

```python
pprint(my_test_server)
{u'context': True,
 u'cpu': 1000,
 u'cpus_instead_of_cores': False,
 u'drives': [],
 u'enable_numa': False,
 u'hv_relaxed': False,
 u'hv_tsc': False,
 u'mem': 536870912,
 u'meta': {},
 u'name': u'My Test Server',
 u'nics': [],
 u'owner': {u'resource_uri': u'/api/2.0/user/b4b9XXX-ba52-4ad0-9837-a2672652XXX/',
            u'uuid': u'b4b9XXX-ba52-4ad0-9837-a2672652XXX'},
 u'requirements': [],
 u'resource_uri': u'/api/2.0/servers/4d5bXXX-4da0-43cd-83aY-18b047014XXXX/',
 u'runtime': None,
 u'smp': 1,
 u'status': u'stopped',
 u'tags': [],
 u'uuid': u'4d5bXXX-4da0-43cd-83aY-18b047014XXXX',
 u'vnc_password': u'test_server'}
```

### Attach a drive the drive and a NIC to the server

We could of course have attached this above, but in order to keep things simple, let's do this in to phases.

Attach the drive:

```python
my_test_server['drives'] = [{
    'boot_order': 1,
    'dev_channel': '0:0',
    'device': 'virtio',
    'drive': my_test_disk['uuid']
}]
```

Attach a public network interface:

```python
my_test_server['nics']  = [{
    'ip_v4_conf': {
        'conf': 'dhcp',
        'ip': None
    },
    'model': 'virtio',
    'vlan': None
}]
```

**Optional**: Add a user-defined SSH key:

```python
my_test_server['meta'] = {'ssh_public_key': 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDoHuFV7Skbu9G1iVokXBdB+zN4wEbqGKijlExUPmxuB6MXDBWCmXUEmMRLerTm3a8QMA+8Vyech0/TWQscYvs8xzM/HkRAqKwhhjPMRlfHgy+QKjRD8P989AYMnNcSYe8DayElFXoLYKwsDmoUcsnbf5H+f6agiBkWqz5odb8fvc2rka0X7+p3tDyKFJRt2OugPqLR9fhWddie65DBxAcycnScoqLW0+YAxakfWlKDUqwerIjuRN2VJ7T7iHywcXhvAU060CEtpWW7bE9T/PIoj/N753QDLYrmqtvqAQqU0Ss5rIqS8bYJXyM0zTKwIuncek+k+b9ButBf/Nx5ehjN vagrant@precise64'}
```

Push the settings:

```python
server.update(my_test_server['uuid'], my_test_server)
```

### Start the server

```python
server.start(my_test_server['uuid'])
```

### Stop the server

```python
server.stop(my_test_server['uuid'])
```

### Reading Meta Data

CloudSigma supports the notion of exposing meta data to guests. Using the Python library, this can be done very easily. **Please note** that you do not need `~/.cloudsigma.conf` in order to use this feature, as the data is read directly from `/dev/ttyS1`. More information on how to this works can be found [here](https://cloudsigma-docs.readthedocs.io/en/2.14.1/server_context.html#setting-up-the-virtual-serial-port).

By default, various system information is exposed, but it is also possible to push user-defined data, such as an SSH-key to the guest.

Here's snippet that demonstrates how to read the meta meta data from a given server using the python library:

```python
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
 u'name': u'MyTestServer',
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
```

If you get a permission error while running the above command, make sure you have access to read from `/dev/ttyS1`. For instance, on Ubuntu, the default owner is `root` and the group is set to `dialout`. Hence you need to either change the permission, or add your user to the group `sudo usermod -a -G dialout $(whoami)`. Please note that you will need to logout and log in again for the permission change to take effect.

For more examples on how to read and write meta data, please visit our [API documentation](https://autodetect.cloudsigma.com/docs/meta.html#examples).

## Sample: Install SSH key from meta data

In the example above, we pushed an SSH key as meta data to a server. That's great, but what if we want to put this to use? Don't worry, we got you covered.

The code snippet below assumes that you have installed your SSH key into the server's meta data with the key 'ssh_public_key'.

```python
import cloudsigma
import os
import stat

metadata = cloudsigma.metadata.GetServerMetadata().get()
ssh_key = metadata['meta']['ssh_public_key']

# Define paths
home = os.path.expanduser("~")
ssh_path = os.path.join(home, '.ssh')
authorized_keys = os.path.join(ssh_path, 'authorized_keys')


def get_permission(path):
    return oct(os.stat(ssh_path)[stat.ST_MODE])[-4:]

if not os.path.isdir(ssh_path):
    print('Creating folder %s' % ssh_path)
    os.makedirs(ssh_path)

if get_permission(ssh_path) != 0700:
    print('Setting permission for %s' % ssh_path)
    os.chmod(ssh_path, 0700)

# We'll have to assume that there might be other keys installed.
# We could do something fancy, like checking if the key is installed already,
# but in order to keep things simple, we'll simply append the key.
with open(authorized_keys, 'a') as auth_file:
    auth_file.write(ssh_key + '\n')

if get_permission(authorized_keys) != 0600:
    print('Setting permission for %s' % authorized_keys)
    os.chmod(authorized_keys, 0600)
```

[Download](https://raw.github.com/cloudsigma/pycloudsigma/master/samples/set_ssh_key.py)

## Sample: Monitor websocket activity

Here's a sample application that listens to activity on the websocket. You can run this application to see activity from the web interface.

```python
from cloudsigma.generic import GenericClient
from cloudsigma.resource import Websocket
from cloudsigma.errors import ClientError, PermissionError

ws = Websocket(timeout=None)
client = GenericClient()

print("Display Websocket activity.\nExit with ^C.")

while True:
    try:
        get_action = ws.ws.recv()
        action_uri = get_action['resource_uri']
        print('Received Action: %s' % get_action)
        print('Result:\n%s' % client.get(action_uri))
    except ClientError as e:
        if e.args[0] == 404:
            print("Resource %s was deleted" % action_uri)
        else:
            print('Error retrieving: %s' % e)
    except PermissionError as e:
        print("No permissions for resource %s" % action_uri)
```

[Download](https://raw.github.com/cloudsigma/pycloudsigma/master/samples/monitor_websocket_activity.py)

## Sample: A CLI for taking snapshots

One handy functionality in our API is the ability to take snapshots of a drive. Since the drive can be running while you take the snapshot, combined with the fact that you only pay for the delta between the original disk and the snapshot, this becomes a very powerful backup tool.

Using the snippet below, you can easily create automated backups. All you need to do is to run the snapshot blow in an automated fashion, such as using the crontab.


```python
import cloudsigma
import sys
from time import sleep

snapshot = cloudsigma.resource.Snapshot()
snapshot_done = False

if len(sys.argv) < 3:
    print('\nUsage: ./snapshot.py drive-uuid snapshot-name\n')
    sys.exit(1)

snapshot_data = {
    'drive': sys.argv[1],
    'name': sys.argv[2],
}

create_snapshot = snapshot.create(snapshot_data)

while not snapshot_done:
    snapshot_status = snapshot.get(create_snapshot['uuid'])

    if snapshot_status['status'] == 'available':
        snapshot_done = True
        print('\nSnapshot successfully created\n')
    else:
        sleep(1)
```

[Download](https://raw.github.com/cloudsigma/pycloudsigma/master/samples/snapshot.py)

There's also another script named [snapshot_purge.py](https://raw.githubusercontent.com/cloudsigma/pycloudsigma/master/samples/snapshot_purge.py) that can used for automatically purging old snapshots.

## Running the tests

There must be a VM available by the name that matches `persistent_drive_name`. This VM should be a server with SSH installed, where one can be log in as `root` with the password set in `persistent_drive_ssh_password`.

