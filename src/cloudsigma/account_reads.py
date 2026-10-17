"""Opt-in complete account read envelopes; legacy resources remain unchanged."""
from cloudsigma.resource import ResourceBase
from cloudsigma.router_reads import _RawReadClient


class PricingRead(ResourceBase):
    """One GET /pricing/ envelope; Decimal numeric values, not original lexemes.

    Only get is qualified. Inherited mutations are not a readonly fence.
    """
    resource_name = 'pricing'

    def __init__(self, *args, **kwargs):
        self.c = _RawReadClient(*args, **kwargs)

    def get(self, limit=None):
        if limit is not None and (type(limit) is not int or limit < 0):
            raise ValueError('limit must be a nonnegative integer')
        query = None if limit is None else {'limit': limit}
        return self.c.get(self._get_url(), query_params=query)


class LedgerRead(ResourceBase):
    """One GET /ledger/ envelope, not complete history or automatic traversal."""
    resource_name = 'ledger'

    def __init__(self, *args, **kwargs):
        self.c = _RawReadClient(*args, **kwargs)

    def get(self, query_params=None):
        """Read one page, optionally selecting documented limit/offset values.

        Omitted parameters preserve the service's default page. No automatic
        traversal or new filter support is implied.
        """
        return self.c.get(self._get_url(), query_params=query_params)
