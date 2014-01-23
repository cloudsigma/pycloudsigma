import bisect
from collections import defaultdict
from datetime import timedelta, datetime
import dateutil.parser
from decimal import Decimal
import re

import cloudsigma.resource as cr

start_time = datetime(2014, 01, 1)
end_time = datetime(2014, 02, 1)




def get_usages(usage_client, ledger_time, start_date, usage_list, bisect_list):
    if not usage_list:
        return usage_client.list(dict(poll_time__lt=ledger_time, poll_time__gt=start_date.isoformat()))
    else:
        i = bisect.bisect_left(bisect_list, start_date)
        res = []
        while i != len(bisect_list):
            if usage_list[i]['poll_time'] >= ledger_time:
                break
            res.append(usage_list[i])
            i += 1
        return res



def get_per_server_usage(start_time, end_time):
    server_client = cr.Server()
    server_list = server_client.list_detail()
    server_resources = {}
    for server in server_list:
        server_resources[server['uuid']] = server['uuid']
        for drive in server['drives']:
            server_resources[drive['drive']['uuid']] = server['uuid']
    usage_client = cr.Usage()
    ledger_client = cr.Ledger()
    server_billing = defaultdict(int)
    interval = (end_time - start_time).days

    ledger_list = ledger_client.list(dict(time__gt=end_time - timedelta(days=interval), time__lt=end_time))
    usage_list = []
    i = 0
    for i in range(7, interval, 7):
        usage_list.extend(usage_client.list(dict(poll_time__gt=end_time - timedelta(days=i),
                                                 poll_time__lt=end_time - timedelta(days=i - 7))))
    if interval % 7 != 0:
        usage_list.extend(usage_client.list(dict(poll_time__gt=end_time - timedelta(days=interval),
                                                 poll_time__lt=end_time - timedelta(days=i))))
    usage_list = list(sorted(usage_list, key=lambda x:x['poll_time']))
    bisect_list = [dateutil.parser.parse(u['poll_time']) for u in usage_list]
    for ledger in ledger_list:
        if not ledger['billing_cycle']:
            continue

        match = re.search('Burst: .* of ([^ ]*) .*', ledger['reason'])
        if not match:
            continue
        ledger['resource'] = match.group(1)
        poll_time = dateutil.parser.parse(ledger['time'])
        start_date = poll_time - timedelta(seconds=ledger['interval'] - 1)
        usages = get_usages(usage_client, ledger['time'], start_date, usage_list, bisect_list)
        for usage in usages:
            if usage['resource'] != ledger['resource']:
                continue
            server = server_resources.get(usage['uuid'])
            if server:
                server_billing[server] += Decimal(usage['amount']) / Decimal(ledger['resource_amount']) * Decimal(ledger['amount'])

    return server_billing

if __name__ == '__main__':
    for server, amount in get_per_server_usage(start_time, end_time).iteritems():
        print "%s - %.2f" % (server, amount)
