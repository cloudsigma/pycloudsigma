"""Explicit VMware collection read; no lifecycle or traversal helpers."""
from cloudsigma.router_reads import _RawReadClient


class VMwareRead:
    """One complete HTTP200 envelope; Decimal numeric values, not lexemes.

    Nested schemas are unvalidated and unexpected sensitive fields not redacted.
    The accessible client is not an authorization boundary. Serial session login
    is inherited; no runtime feature availability or ownership is inferred.
    """
    def __init__(self, *args, **kwargs):
        self.c = _RawReadClient(*args, **kwargs)

    def list(self):
        return self.c.get('/vmware_servers/')
