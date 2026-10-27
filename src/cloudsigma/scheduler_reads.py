"""Explicit scheduler GETs and collection deletion; no traversal contract."""
from cloudsigma.router_reads import VirtualRouterReads


class BackupSchedulerReads(VirtualRouterReads):
    """Preserve HTTP200 envelopes/Decimal values using the scoped read client.

    Only delete_many is a qualified mutation here. Other inherited mutations
    are not a readonly fence or supported contract.
    Existing generic resources are unchanged. Fields projection is list-only.
    """
    resource_name = 'backupschedulers'


    def delete_many(self, uuids):
        """Request scheduler collection deletion, not completion or atomicity.

        Accept a nonempty list/tuple of nonempty ASCII letters, digits, hyphens
        and underscores. This conservative SDK policy is not public UUID
        grammar. Validate the whole batch before one request; preserve order
        and duplicates without modifying the caller's sequence. HTTP 204
        returns None and means deletion started. No retries, polling, drive
        deletion or scheduler creation contract is provided.
        https://docs.cloudsigma.com/en/latest/backup_schedulers.html#deleting
        """
        if not isinstance(uuids, (list, tuple)) or not uuids:
            raise ValueError('scheduler identifiers must be a nonempty list or tuple')
        objects = []
        for uuid in uuids:
            if not isinstance(uuid, str) or not uuid or any(
                    char not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_'
                    for char in uuid):
                raise ValueError('invalid scheduler identifier')
            objects.append({'uuid': uuid})
        return self.c.delete(self._get_url(), data={'objects': objects})

    def _page(self, detail=False, query_params=None, *, otp=None):
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
                           query_params=query, return_list=True, otp=otp)
        if type(value) is not dict:
            raise ValueError('scheduler page must be an object')
        objects = value.get('objects')
        if objects is not None and (type(objects) is not list or
                                    any(type(x) is not dict for x in objects)):
            raise ValueError('scheduler objects must be object arrays')
        return value
