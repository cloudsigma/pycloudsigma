from cloudsigma.generic import GenericClient
from cloudsigma.resource import Websocket
from cloudsigma.errors import ClientError, PermissionError

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
        if e.args[0] == 404:
            print "Resource %s was deleted" % action_uri
        else:
            print 'Error retrieving: %s' % e
    except PermissionError as e:
        print "No permissions for resource %s" % action_uri
