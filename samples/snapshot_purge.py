import cloudsigma
import sys
import iso8601
import pytz
from datetime import datetime, timedelta

snapshot = cloudsigma.resource.Snapshot()

if len(sys.argv) < 3:
    print "\nA tool for purging snapshots of a drive older than n days."
    print 'Usage: ./snapshot_purge.py drive-uuid days-to-keep\n'
    sys.exit(1)

drive_uuid = sys.argv[1]
days_to_keep = int(sys.argv[2])
snapshot_list = snapshot.list()

for s in snapshot_list:
    snapshot_timestamp = iso8601.parse_date(s['timestamp'])
    cut_off_date = datetime.now(pytz.utc) - timedelta(days=days_to_keep)

    if (s['drive']['uuid'] == drive_uuid and snapshot_timestamp < cut_off_date):
        print 'Deleting snapshot "%s" from %s' % (s['name'], snapshot_timestamp)
        snapshot.delete(s['uuid'])
