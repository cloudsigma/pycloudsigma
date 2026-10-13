"""Explicit scheduler GETs; no scheduling mutations or traversal contract."""
from cloudsigma.router_reads import VirtualRouterReads


class BackupSchedulerReads(VirtualRouterReads):
    """Preserve HTTP200 envelopes/Decimal values using the scoped read client.

    Inherited mutation methods are not a readonly fence or supported contract.
    Existing generic resources are unchanged. Fields projection is list-only.
    """
    resource_name = 'backupschedulers'

    def _page(self, detail=False, query_params=None):
        query = {} if query_params is None else dict(query_params)
        allowed = ('type', 'limit', 'offset') if detail else ('type', 'fields', 'limit', 'offset')
        if any(k not in allowed for k in query):
            raise ValueError('unsupported scheduler query')
        for key in ('limit', 'offset'):
            if key in query and (type(query[key]) is not int or query[key] < 0):
                raise ValueError('page values must be nonnegative integers')
        if 'type' in query and query['type'] not in ('backup', 'snapshot'):
            raise ValueError('unsupported scheduler type')
        if 'fields' in query and (type(query['fields']) is not str or not query['fields']):
            raise ValueError('fields must be a nonempty string')
        value = self.c.get(self._get_url() + ('detail/' if detail else ''),
                           query_params=query, return_list=True)
        if type(value) is not dict:
            raise ValueError('scheduler page must be an object')
        objects = value.get('objects')
        if objects is not None and (type(objects) is not list or
                                    any(type(x) is not dict for x in objects)):
            raise ValueError('scheduler objects must be object arrays')
        return value
