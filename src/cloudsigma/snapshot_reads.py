"""Opt-in snapshot envelopes; raw responses are not redacted."""
from cloudsigma.resource import Snapshot, _AvailabilityGroups
from cloudsigma.router_reads import _RawReadClient


class SnapshotReads(Snapshot):
    """One response, no traversal. Inherited mutations are not a fence.

    Fractional numbers use Decimal, not original numeric lexemes. Nested schema
    is not validated. Unexpected sensitive fields remain caller responsibility.
    Existing generic Snapshot and shared decoder/transport remain unchanged.
    """
    _client_class = _RawReadClient

    def list(self, query_params=None, *, otp=None):
        """Read one summary page with optional explicit limit/offset values.

        Omitted parameters preserve the service default. Forwarding a query
        does not establish support for the disputed drive-filter variant.
        """
        return self.c.get(self._get_url(), query_params=query_params, otp=otp)

    def list_detail(self, query_params=None, *, otp=None):
        """Read one detail page with optional explicit limit/offset values.

        Omitted parameters preserve the service default. Forwarding a query
        does not establish support for the disputed drive-filter variant.
        """
        return self.c.get(self._get_url() + 'detail/', query_params=query_params,
                          otp=otp)

    def get(self, uuid=None, query_params=None, *, otp=None, limit=None, offset=None):
        identifier = _AvailabilityGroups._identifier(uuid)
        return self.c.get(self._get_url() + identifier + '/',
                          query_params=query_params, otp=otp)
