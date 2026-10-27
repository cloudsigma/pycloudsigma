"""Explicit full binary download; no shared GenericClient transport changes."""
import math
import re
import time
from urllib.parse import urlsplit, urljoin

import requests


class DownloadError(Exception):
    """Sanitized download refusal; partial caller output may remain."""


class DownloadStatusError(DownloadError):
    """SDK-policy refusal, not universal provider error semantics."""
    def __init__(self, status):
        self.status = status
        super().__init__('download status %d' % status)


def _url(value):
    if not isinstance(value, str) or any(ord(c) <= 32 or ord(c) == 127 for c in value) or '\\' in value:
        raise DownloadError('invalid URL')
    p = urlsplit(value)
    try:
        port = p.port
    except ValueError:
        raise DownloadError('invalid authority') from None
    if (p.scheme != 'https' or not p.hostname or p.username is not None
            or p.password is not None or p.fragment or '%' in p.netloc
            or p.netloc.endswith(':') or not re.fullmatch(r'[a-z0-9.-]+(?::[0-9]+)?', p.netloc)
            or (port is not None and not 1 <= port <= 65535)):
        raise DownloadError('invalid authority')
    return p


class _DownloadSession(requests.Session):
    # Requests.send(False) otherwise calls resolve_redirects(yield_requests=True)
    # to populate Response.next, consuming resp.content BEFORE caller policy.
    # This private session never prepares/follows redirects; the API owns each hop.
    def resolve_redirects(self, resp, req, **kwargs):
        return iter(())


def _location(value):
    # Validate original header BEFORE urllib normalization can strip controls.
    if not isinstance(value, str) or not value or any(ord(c) <= 32 or ord(c) == 127 for c in value) or '\\' in value:
        raise DownloadError('invalid Location')
    try:
        p = urlsplit(value)
    except ValueError:
        raise DownloadError('invalid Location') from None
    if p.fragment or (p.scheme and p.scheme != 'https'):
        raise DownloadError('invalid Location')
    if p.netloc:
        _url(('https:' if not p.scheme else '') + value)
    elif p.scheme or value.startswith('//'):
        raise DownloadError('invalid Location')


class DriveDownload:
    """Separate Basic-only opt-in API. No login, config loading or network at init.

    Default redirects denied; caller policy is trusted, not provider approval or
    DNS/private-address/rebinding protection. No borrowed Session is mutated.
    Internal Session setup precedes the cooperative total timeout. Requests timeouts
    are per-operation, not a hard wall deadline. Hostile writers/callbacks/close
    cannot be bounded; cancellation during a final write may complete successfully.
    """
    def __init__(self, *, location, username, password):
        if not isinstance(location, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', location):
            raise ValueError('invalid location')
        for v in (username, password):
            if not isinstance(v, str) or not v or any(ord(c) < 32 or ord(c) == 127 for c in v):
                raise ValueError('invalid credentials')
            try:
                v.encode('latin1')
            except UnicodeEncodeError:
                raise ValueError('unsupported Basic encoding') from None
        if ':' in username:
            raise ValueError('invalid credentials')
        self._origin = 'https://direct.' + location + '.cloudsigma.com'
        self._auth = (username, password)

    def download(self, uuid, writer, *, max_bytes, timeout, max_redirects=0,
                 allow_redirect=None, cancelled=None):
        """Stream 200 octet-stream/identity bytes, no206/ranges/resume/files.

        Writer stays caller-owned; write must return the exact byte count.
        Errors retain partial output. Cancellation is an optional trusted boolean
        callback, checked before dispatch and between raw reads. Redirect callback
        receives immutable URL strings. Credentials reapply only on exact origin,
        including return hops; all other origins get fresh unauthenticated headers.
        """
        if (not isinstance(uuid, str) or not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', uuid)
                or not callable(getattr(writer, 'write', None)) or type(max_bytes) is not int or max_bytes <= 0
                or type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 3600
                or type(max_redirects) is not int or not 0 <= max_redirects <= 10
                or (allow_redirect is not None and not callable(allow_redirect))
                or (max_redirects and allow_redirect is None)
                or (cancelled is not None and not callable(cancelled))):
            raise ValueError('invalid download options')
        if cancelled is not None and cancelled():
            raise DownloadError('cancelled')
        session = _DownloadSession()
        try:
            session.trust_env = False
            session.auth = None
            session.proxies.clear()
            session.headers.clear()
            deadline = time.monotonic() + timeout
            url = self._origin + '/api/2.0/drives/' + uuid + '/download/'
            seen = set()
            count = 0
            def check():
                if time.monotonic() >= deadline:
                    raise DownloadError('timeout')
                if cancelled is not None and cancelled():
                    raise DownloadError('cancelled')
            for hop in range(max_redirects + 1):
                check()
                p = _url(url)
                if url in seen:
                    raise DownloadError('redirect loop')
                seen.add(url)
                session.cookies.clear()
                headers = {'Accept': 'application/octet-stream', 'Accept-Encoding': 'identity'}
                auth = self._auth if p.scheme + '://' + p.netloc == self._origin else None
                # Prepare a fresh request without Session defaults, cookies or netrc.
                req = requests.Request('GET', url, headers=headers, auth=auth).prepare()
                if req.url != url or 'Host' in req.headers:
                    raise DownloadError('prepared URL normalization refused')
                try:
                    response = session.send(req, stream=True, allow_redirects=False,
                                            timeout=max(0.001, deadline-time.monotonic()), verify=True, proxies={})
                except requests.RequestException:
                    raise DownloadError('transport failed') from None
                try:
                    check()
                    if response.url != url:
                        raise DownloadError('final URL refused')
                    if response.status_code in (301, 302, 303, 307, 308):
                        loc = response.headers.get('Location')
                        if not loc or hop >= max_redirects or allow_redirect is None:
                            raise DownloadError('redirect refused')
                        _location(loc)
                        target = urljoin(url, loc)
                        _url(target)
                        if allow_redirect(url, target) is not True:
                            raise DownloadError('redirect policy refused')
                        url = target
                        continue
                    if response.status_code != 200:
                        raise DownloadStatusError(response.status_code)
                    if (response.headers.get('Content-Type', '').split(';', 1)[0].strip().lower() != 'application/octet-stream'
                            or response.headers.get('Content-Encoding', 'identity').lower() != 'identity'):
                        raise DownloadError('representation refused')
                    length = response.headers.get('Content-Length')
                    if length is not None and not re.fullmatch(r'[0-9]+', length):
                        raise DownloadError('invalid length')
                    length = int(length) if length is not None else None
                    if length is not None and length > max_bytes:
                        raise DownloadError('size limit')
                    response.raw.decode_content = False
                    while True:
                        check()
                        data = response.raw.read(min(32768, max_bytes-count+1), decode_content=False)
                        check()
                        if not data:
                            if length is not None and count != length:
                                raise DownloadError('truncated')
                            return count
                        if len(data) > max_bytes-count:
                            raise DownloadError('size limit')
                        written = writer.write(data)
                        if type(written) is not int or written != len(data):
                            raise DownloadError('short write')
                        count += written
                finally:
                    response.close()
            raise DownloadError('redirect refused')
        finally:
            session.close()
