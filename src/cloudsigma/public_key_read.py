"""Documented public SSH-key singleton reader; no key mutation helpers."""
from cloudsigma.generic import get_client


class PublicKeyRead:
    """Read GET /pubkeys/{id}/ with the existing generic response decoder.

    Import from cloudsigma.public_key_read. Only get is exposed as a resource
    operation; the underlying client is not a security/authorization boundary.
    Unexpected sensitive response fields are not redacted. Generic numeric,
    status and decoding semantics apply; no schema or key-material validation.
    """
    def __init__(self, *args, **kwargs):
        self.c = get_client()(*args, **kwargs)

    def get(self, identifier):
        """Read one key. Require a nonempty exact str ASCII alnum/-/_ segment.

        Reject bytes, bool and other types before dispatch. This is routing
        validation, not UUID semantics or ownership authorization.
        """
        if type(identifier) is not str or not identifier or any(
                ch not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_'
                for ch in identifier):
            raise ValueError('invalid public-key identifier')
        return self.c.get('/pubkeys/' + identifier + '/', return_list=False)
