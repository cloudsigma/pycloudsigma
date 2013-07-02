# CloudSigma Python Library

Work in Progress. Not ready for public use.

## Config file

In order for the CloudSigma library to be able to authenticate with the server, you need to provide your credentials. These are set in the file `~/.cloudsigma.conf`. Here's a sample version of the file that talks to the Las Vegas datacenter. If you instead want to use the Zurich datacenter, simply replace 'lvs' with 'zrh' in the api_endpoint and ws_endpoint.

    api_endpoint = https://lvs.cloudsigma.com/api/2.0/
    ws_endpoint = wss://direct.lvs.cloudsigma.com/websocket
    username = user@domain.com
    password = secret

    persistent_drive_name=foobar
    persistent_drive_ssh_password=sshsecret

Since this file includes credentials, it is highly recommended that you set the permission of the file to 600 (`chmod 600 ~/.cloudsigma.conf`)

## Running the tests

There must be a VM available by the name that matches `persistent_drive_name`. This VM should be a server with SSH installed, where one can be log in as `root` with the password set in `persistent_drive_ssh_password`.
