"""Opt-in snapshot envelopes; raw responses are not redacted."""
from cloudsigma.resource import Snapshot, _AvailabilityGroups
from cloudsigma.router_reads import _RawReadClient


class SnapshotReads(Snapshot):
    """One response, no query or traversal. Inherited mutations are not a fence.

    Fractional numbers use Decimal, not original numeric lexemes. Nested schema
    is not validated. Unexpected sensitive fields remain caller responsibility.
    Existing generic Snapshot and shared decoder/transport remain unchanged.
    """
    def __init__(self, *args, **kwargs):
        self.c = _RawReadClient(*args, **kwargs)

    def list(self):
        return self.c.get(self._get_url())

    def list_detail(self):
        return self.c.get(self._get_url() + 'detail/')

    def get(self, uuid=None):
        identifier = _AvailabilityGroups._identifier(uuid)
        return self.c.get(self._get_url() + identifier + '/')
