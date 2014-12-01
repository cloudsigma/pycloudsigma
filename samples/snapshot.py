import cloudsigma
import sys
from time import sleep

snapshot = cloudsigma.resource.Snapshot()
snapshot_done = False

if len(sys.argv) < 3:
    print '\nUsage: ./snapshot.py drive-uuid snapshot-name\n'
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
        print '\nSnapshot successfully created\n'
    else:
        sleep(1)
