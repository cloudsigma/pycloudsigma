"""Opt-in complete account read envelopes; legacy resources remain unchanged."""
from cloudsigma.resource import ResourceBase
from cloudsigma.router_reads import _RawReadClient


class PricingRead(ResourceBase):
    """One GET /pricing/ envelope; Decimal numeric values, not original lexemes.

    Only get is qualified. Inherited mutations are not a readonly fence.
    """
    resource_name = 'pricing'

    _client_class = _RawReadClient

    def get(self, uuid=None, query_params=None, *, otp=None, limit=None,
            offset=None):
        """Read one pricing page with explicit limit and zero-based offset.

        Omitted values preserve service defaults; limit=0 requests all objects.
        Existing positional limit calls remain unchanged. No traversal occurs.
        """
        # Keep the historical ``get(limit, offset)`` form while accepting the
        # ResourceBase-compatible names used by generic callers.
        if limit is None and offset is None and uuid is not None:
            limit = uuid
            if query_params is not None and not isinstance(query_params, dict):
                offset = query_params
                query_params = None
        if isinstance(query_params, dict):
            if limit is None:
                limit = query_params.get('limit')
            if offset is None:
                offset = query_params.get('offset')
        if limit is not None and (type(limit) is not int or limit < 0):
            raise ValueError('limit must be a nonnegative integer')
        if offset is not None and (type(offset) is not int or offset < 0):
            raise ValueError('offset must be a nonnegative integer')
        query = {}
        if limit is not None:
            query['limit'] = limit
        if offset is not None:
            query['offset'] = offset
        return self.c.get(self._get_url(), query_params=query or None, otp=otp)


class LedgerRead(ResourceBase):
    """One GET /ledger/ envelope, not complete history or automatic traversal."""
    resource_name = 'ledger'

    _client_class = _RawReadClient

    def get(self, uuid=None, query_params=None, *, otp=None, limit=None, offset=None):
        """Read one page, optionally selecting documented limit/offset values.

        Omitted parameters preserve the service's default page. No automatic
        traversal or new filter support is implied.
        """
        if query_params is None and isinstance(uuid, dict):
            query_params = uuid
        return self.c.get(self._get_url(), query_params=query_params, otp=otp)
