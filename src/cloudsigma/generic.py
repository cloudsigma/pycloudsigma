from __future__ import division
from future import standard_library
standard_library.install_aliases()
from builtins import object
from past.utils import old_div
import urllib.parse
import logging
import copy

import requests
import simplejson
from websocket import create_connection

from .conf import config
from . import errors


LOG = logging.getLogger(__name__)

def wrap_with_log_hook(log_level, next_hook=None):
    if not next_hook:  #noop next hook
        next_hook = lambda r, *args, **kwargs: None

    if not log_level:  # no log level so no logging, just return next hook
        return next_hook

    level = getattr(logging, log_level, None)
    if not level:
        LOG.error('Wrong log_lgevel {}'.format(log_level))
        return next_hook

    def log_hook(response, *args, **kwargs):
        request = response.request
        req_msg = '-----RECONSTRUCTED-REQUEST:\n' \
                  '{req.method} {req.path_url} HTTP/1.1\r\n{headers}\r\n\r\n{body}' \
                  '\n-----RECONSTRUCTED-REQUEST-END'.format(req=request,
                                                            headers='\r\n'.join('{}: {}'.format(k, v)
                                                                                for k, v
                                                                                in list(request.headers.items())),
                                                            body=request.body if request.body else '')
        resp_msg = '-----RECONSTRUCTED-RESPONSE:\n' \
                   'HTTP/1.1 {resp.status_code} {resp.reason}\r\n{headers}\r\n\r\n{body}' \
                   '\n-----RECONSTRUCTED-RESPONSE-END'.format(resp=response,
                                                              headers='\r\n'.join('{}: {}'.format(k, v)
                                                                                  for k, v
                                                                                  in list(response.headers.items())),
                                                              body=response.content if response.content else '')
        LOG.log(level, '{}\n\n{}'.format(req_msg, resp_msg))

        next_hook(response, *args, **kwargs)
    return log_hook

class GenericClient(object):

    """Handles all low level HTTP, authentication, parsing and error handling.
    """
    LOGIN_METHOD_BASIC = 'basic'
    LOGIN_METHOD_SESSION = 'session'
    LOGIN_METHOD_NONE = 'none'
    LOGIN_METHODS = (
        LOGIN_METHOD_BASIC,
        LOGIN_METHOD_SESSION,
        LOGIN_METHOD_NONE,
    )

    def __init__(self, api_endpoint=None, username=None, password=None, login_method=LOGIN_METHOD_BASIC,
                 request_log_level=None):
        self.api_endpoint = api_endpoint if api_endpoint else config['api_endpoint']
        self.username = username if username else config['username']
        self.password = password if password else config['password']
        self.login_method = config.get('login_method', login_method)
        assert self.login_method in self.LOGIN_METHODS, 'Invalid value %r for login_method' % (login_method,)

        self._session = None
        self.resp = None
        self.response_hook = None
        self.request_log_level = request_log_level if request_log_level else config.get('request_log_level', None)
        if self.request_log_level:
            self.request_log_level = self.request_log_level.upper()

        if login_method == self.LOGIN_METHOD_SESSION:
            self._login_session()

    def _login_session(self):
        self.login_method = self.LOGIN_METHOD_SESSION
        self._session = requests.Session()
        full_url = self._get_full_url('/accounts/action/')
        kwargs = self._get_req_args(query_params={'do': 'login'})
        data = simplejson.dumps({"username": self.username, "password": self.password})
        res = self.http.post(full_url, data=data, **kwargs)
        self._process_response(res)
        csrf_token = res.cookies['csrftoken']
        self._session.headers.update({'X-CSRFToken': csrf_token, 'Referer': self._get_full_url('/')})

    def _get_full_url(self, url):
        api_endpoint = urllib.parse.urlparse(self.api_endpoint)
        if url.startswith(api_endpoint.path):
            full_url = list(api_endpoint)
            full_url[2] = url
            full_url = [str(x) for x in full_url]
            full_url = urllib.parse.urlunparse(full_url)
        else:
            if url[0] == '/':
                url = url[1:]
            full_url = urllib.parse.urljoin(str(self.api_endpoint), str(url))

        if not full_url.endswith("/"):
            full_url += "/"

        return full_url

    def _process_response(self, resp, return_list=False):
        resp_data = None
        request_id = resp.headers.get('X-REQUEST-ID', None)
        if resp.status_code in (200, 201, 202):
            resp_data = copy.deepcopy(resp.json())
            if 'objects' in resp_data:
                resp_data = resp_data['objects']
                if len(resp_data) == 1 and not return_list:
                    resp_data = resp_data[0]
        elif resp.status_code == 401:
            raise errors.AuthError(request_id, status_code=resp.status_code)
        elif resp.status_code == 403:
            raise errors.PermissionError(resp.text, status_code=resp.status_code, request_id=request_id)
        elif old_div(resp.status_code, 100) == 4:
            raise errors.ClientError(resp.text, status_code=resp.status_code, request_id=request_id)
        elif old_div(resp.status_code, 100) == 5:
            raise errors.ServerError(resp.text, status_code=resp.status_code, request_id=request_id)

        return resp_data

    def _get_req_args(self, body=None, query_params=None):
        kwargs = {}
        if self.login_method == self.LOGIN_METHOD_BASIC:
            kwargs['auth'] = (self.username, self.password)

        kwargs['headers'] = {
            'content-type': 'application/json',
            'user-agent': 'CloudSigma turlo client',
        }

        if query_params:
            if 'params' not in kwargs:
                kwargs['params'] = {}
            kwargs['params'].update(query_params)

        kwargs['hooks'] = {
            'response': wrap_with_log_hook(self.request_log_level, self.response_hook)
        }

        return kwargs

    @property
    def http(self):
        if self._session:
            return self._session
        return requests

    def get(self, url, query_params=None, return_list=False):
        kwargs = self._get_req_args(query_params=query_params)
        self.resp = self.http.get(self._get_full_url(url), **kwargs)
        return self._process_response(self.resp, return_list)

    def put(self, url, data, query_params=None, return_list=False):
        kwargs = self._get_req_args(body=data, query_params=query_params)
        self.resp = self.http.put(self._get_full_url(url), data=simplejson.dumps(data), **kwargs)
        return self._process_response(self.resp, return_list)

    def post(self, url, data, query_params=None, return_list=False):
        kwargs = self._get_req_args(body=data, query_params=query_params)
        self.resp = self.http.post(self._get_full_url(url), data=simplejson.dumps(data), **kwargs)
        return self._process_response(self.resp, return_list)

    def delete(self, url, query_params=None):
        self.resp = self.http.delete(self._get_full_url(url), **self._get_req_args(query_params=query_params))
        return self._process_response(self.resp)


class WebsocketClient(object):

    def __init__(self, cookie, timeout=10):
        self.conn = create_connection(config['ws_endpoint'], timeout=timeout,
                                      header=['Cookie: async_auth=%s' % (cookie,)])

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
