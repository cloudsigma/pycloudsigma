import requests
import urlparse
import simplejson
import logging

from websocket import create_connection
from .conf import config
from . import errors

LOG = logging.getLogger(__name__)


class GenericClient(object):
    """Handles all low level HTTP, authentication, parsing and error handling. 
    """
    LOGIN_METHOD_BASIC = 'basic'
    LOGIN_METHOD_SESSION = 'session'
    LOGIN_METHODS = (
        LOGIN_METHOD_BASIC,
        LOGIN_METHOD_SESSION,
    )
    
    def __init__(self, api_endpoint=None, username=None, password=None, login_method=LOGIN_METHOD_BASIC):
        self.api_endpoint = api_endpoint if api_endpoint else config['api_endpoint']
        self.username = username if username else config['username']
        self.password = password if password else config['password']
        self.login_method = config.get('login_method', login_method)
        assert self.login_method in self.LOGIN_METHODS, 'Invalid value %r for login_method' % (login_method,)

        self._session = None
        self.resp = None
        self.response_hook = None
        
    def _login_session(self):
        raise NotImplementedError()

    def _get_full_url(self, url):
        api_endpoint = urlparse.urlparse(self.api_endpoint)
        if url.startswith(api_endpoint.path):
            full_url = list(api_endpoint)
            full_url[2] = url
            full_url = urlparse.urlunparse(full_url)
        else:
            if url[0] == '/':
                url = url[1:]
            full_url = urlparse.urljoin(self.api_endpoint, url)

        if not full_url.endswith("/"):
            full_url += "/"

        return full_url

    def _process_response(self, resp, return_list=False):
        resp_data = None
        if resp.status_code in (200, 201, 202):
            resp_data = resp.json().copy()
            if 'objects' in resp_data:
                resp_data = resp_data['objects']
                if len(resp_data) == 1 and not return_list:
                    resp_data = resp_data[0]
        elif resp.status_code == 401:
            raise errors.AuthError()
        elif resp.status_code == 403:
            raise errors.PermissionError(resp.text)
        elif resp.status_code / 100 == 4:
            raise errors.ClientError(resp.status_code, resp.text)
        elif resp.status_code / 100 == 5:
            raise errors.ServerError(resp.status_code, resp.text)
        
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

        if self.response_hook is not None:
            kwargs['hooks'] = {
                'response': self.response_hook
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
        self.conn = create_connection(config['ws_endpoint'], timeout=timeout, header=['Cookie: async_auth=%s' % (cookie,)])

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
