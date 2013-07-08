# CloudSigma Python Library

Work in Progress. Not ready for public use.

## Config file

In order for the CloudSigma library to be able to authenticate with the server, you need to provide your credentials. These are set in the file `~/.cloudsigma.conf`. Here's a sample version of the file that talks to the Las Vegas datacenter. If you instead want to use the Zürich datacenter, simply replace 'lvs' with 'zrh' in the api_endpoint and ws_endpoint.

    api_endpoint = https://lvs.cloudsigma.com/api/2.0/
    ws_endpoint = wss://direct.lvs.cloudsigma.com/websocket
    username = user@domain.com
    password = secret

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

## Running the tests

There must be a VM available by the name that matches `persistent_drive_name`. This VM should be a server with SSH installed, where one can be log in as `root` with the password set in `persistent_drive_ssh_password`.
