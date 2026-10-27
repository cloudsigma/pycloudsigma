from __future__ import division
from . import errors
from .conf import config
from websocket import create_connection
from past.utils import old_div
import simplejson
import requests
import copy
import logging
import sys
import math
import base64
import hashlib
import hmac
import struct
import time
from urllib.parse import urlsplit
from builtins import object
from builtins import str
from future import standard_library
standard_library.install_aliases()


LOG = logging.getLogger(__name__)


def wrap_with_log_hook(log_level, next_hook=None):
    # noop next hook
    if not next_hook:
        next_hook = lambda r, *args, **kwargs: None

    # No log level so no logging, just return next hook
    if not log_level:
        return next_hook

    level = getattr(logging, log_level, None)
    if not level:
        LOG.error('Wrong log_lgevel {}'.format(log_level))
        return next_hook

    def log_hook(response, *args, **kwargs):
        # Never log URLs, headers, payloads or response text: all may contain secrets.
        LOG.log(level, 'HTTP response status=%s', response.status_code)

        next_hook(response, *args, **kwargs)
    return log_hook


class GenericClient(object):
    """
    Handles all low level HTTP, authentication, parsing and error handling.
    """
    LOGIN_METHOD_BASIC = 'basic'
    LOGIN_METHOD_DIGEST = 'digest'
    LOGIN_METHOD_SESSION = 'session'
    LOGIN_METHOD_NONE = 'none'
    LOGIN_METHODS = (
        LOGIN_METHOD_BASIC,
        LOGIN_METHOD_DIGEST,
        LOGIN_METHOD_SESSION,
        LOGIN_METHOD_NONE,
    )

    def __init__(
            self,
            api_endpoint=None,
            username=None,
            password=None,
            login_method=None,
            request_log_level=None,
            timeout=15, trust_env=False, proxies=None, session=None, secret=None
    ):
        self.api_endpoint = api_endpoint if api_endpoint \
            else config['api_endpoint']
        self.username = username if username else config['username']
        self.password = password if password else config['password']
        self.secret = secret if secret is not None else config.get('secret')
        self.login_method = login_method if login_method is not None else config.get('login_method', self.LOGIN_METHOD_BASIC)
        assert self.login_method in self.LOGIN_METHODS, \
            'Invalid value %r for login_method' % (login_method,)

        def positive(value):
            return type(value) in (int, float) and math.isfinite(value) and value > 0
        if not (positive(timeout) or (type(timeout) is tuple and len(timeout) == 2 and all(positive(x) for x in timeout))):
            raise ValueError('timeout must be finite and positive')
        if type(trust_env) is not bool or (proxies is not None and type(proxies) is not dict):
            raise ValueError('invalid transport options')
        self.timeout = timeout
        self.proxies = dict(proxies) if proxies is not None else None
        self._session = session if session is not None else requests.Session()
        # Borrowed sessions must support requests.Session semantics; policy is explicit.
        self._session.trust_env = trust_env
        self.resp = None
        self.response_hook = None
        self.request_log_level = request_log_level if request_log_level else \
            config.get('request_log_level', None)
        if self.request_log_level:
            self.request_log_level = self.request_log_level.upper()

        if self.login_method == self.LOGIN_METHOD_SESSION:
            self._login_session()

    def _login_session(self):
        self.login_method = self.LOGIN_METHOD_SESSION
        full_url = self._get_full_url('/accounts/action/')
        kwargs = self._get_req_args(query_params={'do': 'login'},
                                    otp=self._session_otp() if self.secret else None)
        data = simplejson.dumps(
            {
                "username": self.username,
                "password": self.password
            }
        )
        res = self.http.post(full_url, data=data, **kwargs)
        # The public login contract specifies HTTP 200 with an empty body.
        # Keep ordinary JSON decoding and all other status handling unchanged.
        if not (res.status_code == 200 and res.content == b''):
            self._process_response(res)
        csrf_token = res.cookies['csrftoken']
        self._session.headers.update(
            {
                'X-CSRFToken': csrf_token,
                'Referer': self._get_full_url('/')
            }
        )

    def _session_otp(self):
        """Generate once for explicit session login; never for ordinary requests.

        Base32 only. Enrollment URIs are deliberately not consumed. Defaults
        reflect owner-relayed DevOps guidance, not published API documentation.
        """
        key = None
        try:
            if type(self.secret) is str and self.secret and not self.secret.startswith('otpauth:'):
                key = base64.b32decode(self.secret.upper() + '=' * (-len(self.secret) % 8))
        except (ValueError, TypeError):
            key = None
        if not key:
            raise errors.ApiClientError('invalid MFA secret')
        counter = int(time.time() // 30)
        digest = hmac.new(key, struct.pack('>Q', counter), hashlib.sha1).digest()
        offset = digest[-1] & 15
        value = struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7fffffff
        return '%06d' % (value % 1000000)

    def _get_full_url(self, url):
        def canonical(value):
            try:
                parsed = urlsplit(value)
                if (parsed.scheme.lower() not in ('http', 'https') or not parsed.hostname
                        or parsed.username is not None or parsed.password is not None
                        or '%' in parsed.netloc or parsed.netloc.endswith(':')):
                    raise ValueError()
                host = parsed.hostname.encode('idna').decode('ascii').lower()
                port = parsed.port or (443 if parsed.scheme.lower() == 'https' else 80)
                return parsed.scheme.lower(), host, port
            except (ValueError, UnicodeError):
                raise errors.ApiClientError('invalid request origin') from None
        def unambiguous(value):
            if (not isinstance(value, str) or not value or '\\' in value
                    or any(ord(c) <= 32 or ord(c) == 127 for c in value)
                    or any(x in value.lower() for x in ('%2f', '%5c'))):
                raise errors.ApiClientError('ambiguous request URL')
        unambiguous(self.api_endpoint)
        unambiguous(url)
        expected = canonical(self.api_endpoint)
        if url.startswith('//'):
            raise errors.ApiClientError('ambiguous request URL')
        try:
            requested = urlsplit(url)
            if requested.scheme or requested.netloc:
                if canonical(url) != expected:
                    raise errors.ApiClientError('cross-origin request refused')
        except ValueError:
            raise errors.ApiClientError('invalid request URL') from None
        urlparse = get_urlparse()
        urlunparse = get_urlunparse()
        urljoin = get_urljoin()
        api_endpoint = urlparse(self.api_endpoint)
        if url.startswith(api_endpoint.path):
            full_url = list(api_endpoint)
            full_url[2] = requested.path
            full_url[3] = ''
            full_url[4] = requested.query
            full_url[5] = requested.fragment
            full_url = [str(x) for x in full_url]
            full_url = urlunparse(full_url)
        else:
            if url[0] == '/':
                url = url[1:]
            full_url = urljoin(str(self.api_endpoint), str(url))

        # Normalize the resource path only; query values are not path segments.
        resolved = list(urlparse(full_url))
        if not resolved[2].endswith('/'):
            resolved[2] += '/'
        full_url = urlunparse(resolved)

        # Validate both resolver output and requests normalization before auth dispatch.
        if canonical(full_url) != expected:
            raise errors.ApiClientError('cross-origin request refused')
        try:
            prepared = requests.Request('GET', full_url).prepare().url
        except (ValueError, requests.RequestException):
            raise errors.ApiClientError('invalid resolved URL') from None
        if canonical(prepared) != expected:
            raise errors.ApiClientError('cross-origin request refused')
        return full_url

    def _process_response(self, resp, return_list=False):
        return self._decode_response(resp, return_list)

    def _decode_response(self, resp, return_list=False, preserve_envelope=False):
        resp_data = None
        request_id = resp.headers.get('X-REQUEST-ID', None)
        if resp.status_code in (200, 201, 202):
            resp_data = copy.deepcopy(resp.json())
            if not preserve_envelope and 'objects' in resp_data:
                resp_data = resp_data['objects']
                if len(resp_data) == 1 and not return_list:
                    resp_data = resp_data[0]
        elif 300 <= resp.status_code < 400:
            raise errors.ApiClientError('redirect refused', status_code=resp.status_code, request_id=request_id)
        elif resp.status_code == 401:
            error = errors.AuthError(request_id, status_code=resp.status_code)
            # Preserve legacy exception fields; expose response details additively.
            error.response_body = resp.text
            error.response_request_id = request_id
            raise error
        elif resp.status_code == 403:
            raise errors.PermissionError(
                resp.text,
                status_code=resp.status_code,
                request_id=request_id
            )
        elif old_div(resp.status_code, 100) == 4:
            raise errors.ClientError(
                resp.text,
                status_code=resp.status_code,
                request_id=request_id
            )
        elif old_div(resp.status_code, 100) == 5:
            raise errors.ServerError(
                resp.text,
                status_code=resp.status_code,
                request_id=request_id
            )

        return resp_data

    def _get_req_args(self, body=None, query_params=None, otp=None):
        # Requests Digest response hooks resend the prepared OTP and body.
        # Refuse this combination rather than remove auth or hide a retry.
        if otp is not None and self.login_method == self.LOGIN_METHOD_DIGEST:
            raise errors.ApiClientError('explicit OTP with Digest authentication is unsupported')
        kwargs = {'timeout': self.timeout, 'allow_redirects': False}
        if self.proxies is not None:
            kwargs['proxies'] = self.proxies.copy()
        if self.login_method == self.LOGIN_METHOD_BASIC:
            kwargs['auth'] = (self.username, self.password)
        elif self.login_method == self.LOGIN_METHOD_DIGEST:
            # Fresh challenge state per operation: never preemptively send a
            # cached digest to another path, realm or changed endpoint.
            kwargs['auth'] = requests.auth.HTTPDigestAuth(self.username, self.password)

        kwargs['headers'] = {
            'content-type': 'application/json',
            'user-agent': 'CloudSigma turlo client',
        }

        if otp is not None:
            if type(otp) is not str or len(otp) != 6 or any(c not in '0123456789' for c in otp):
                raise errors.ApiClientError('invalid OTP format')
            kwargs['headers']['OTP'] = otp

        if query_params:
            if 'params' not in kwargs:
                kwargs['params'] = {}
            kwargs['params'].update(query_params)

        kwargs['hooks'] = {
            'response': wrap_with_log_hook(
                self.request_log_level,
                self.response_hook
            )
        }

        return kwargs

    @property
    def http(self):
        if self._session:
            return self._session
        return requests

    def get(self, url, query_params=None, return_list=False, otp=None):
        kwargs = self._get_req_args(query_params=query_params, otp=otp)
        self.resp = self.http.get(self._get_full_url(url), **kwargs)
        return self._process_response(self.resp, return_list)

    def get_raw(self, url, query_params=None, otp=None):
        """Return one decoded GET response without unwrapping objects.

        Uses the existing JSON numeric policy, authentication and errors.
        No traversal, schema validation or original JSON lexeme guarantee.
        """
        kwargs = self._get_req_args(query_params=query_params, otp=otp)
        self.resp = self.http.get(self._get_full_url(url), **kwargs)
        return self._decode_response(self.resp, preserve_envelope=True)

    def put(self, url, data, query_params=None, return_list=False, otp=None):
        kwargs = self._get_req_args(body=data, query_params=query_params, otp=otp)
        self.resp = self.http.put(
            self._get_full_url(url),
            data=simplejson.dumps(data),
            **kwargs
        )
        return self._process_response(self.resp, return_list)

    def post(self, url, data, query_params=None, return_list=False, otp=None):
        kwargs = self._get_req_args(body=data, query_params=query_params, otp=otp)
        self.resp = self.http.post(
            self._get_full_url(url),
            data=simplejson.dumps(data),
            **kwargs
        )
        return self._process_response(self.resp, return_list)

    def post_empty_ack(self, url, data, query_params=None):
        """POST an action documenting HTTP 200 with an exactly empty body.

        Other responses retain the ordinary response decoder and error policy.
        This does not establish authentication or asynchronous completion.
        """
        kwargs = self._get_req_args(body=data, query_params=query_params)
        self.resp = self.http.post(
            self._get_full_url(url), data=simplejson.dumps(data), **kwargs)
        if self.resp.status_code == 200 and self.resp.content == b'':
            return None
        return self._process_response(self.resp)

    def delete(self, url, query_params=None, data=None, otp=None):
        kwargs = self._get_req_args(query_params=query_params, otp=otp)
        if data is not None:
            kwargs['data'] = simplejson.dumps(data)
        self.resp = self.http.delete(
            self._get_full_url(url),
            **kwargs
        )
        return self._process_response(self.resp)


class WebsocketClient(object):

    def __init__(self, cookie, timeout=10):
        self.conn = create_connection(
            config['ws_endpoint'],
            timeout=timeout,
            header=['Cookie: async_auth=%s' % (cookie,)]
        )

    def recv(self, timeout=None, return_raw=False):
        if timeout is None:
            ret = self.conn.recv()
        else:
            old_timeout = self.conn.gettimeout()
            self.conn.settimeout(timeout)
            try:
                ret = self.conn.recv()
            finally:
                self.conn.settimeout(old_timeout)
        if not return_raw:
            ret = simplejson.loads(ret)
        return ret


def get_client():
    client_str = config.get('client', None)

    if not client_str:
        return GenericClient

    module_str, klass_str = client_str.split(":")

    import importlib

    module = importlib.import_module(module_str)

    return getattr(module, klass_str)


def get_urlparse():
    if sys.version_info >= (3, 3):
        from urllib.parse import urlparse
    else:
        from urlparse import urlparse
    return urlparse


def get_urljoin():
    if sys.version_info >= (3, 3):
        from urllib.parse import urljoin
    else:
        from urlparse import urljoin
    return urljoin


def get_urlunparse():
    if sys.version_info >= (3, 3):
        from urllib.parse import urlunparse
    else:
        from urlparse import urlunparse
    return urlunparse


def get_unquote():
    if sys.version_info >= (3, 3):
        from urllib.parse import unquote
    else:
        from urlparse import unquote
    return unquote


def get_parse_qsl():
    if sys.version_info >= (3, 3):
        from urllib.parse import parse_qsl
    else:
        from urlparse import parse_qsl
    return parse_qsl






