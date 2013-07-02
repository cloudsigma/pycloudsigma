import socket
import time
from cloudsigma.generic import GenericClient, WebsocketClient


class ResourceBase(object):
    resource_name = None

    def __init__(self, *args, **kwargs):
        self.c = GenericClient(*args, **kwargs)

    def attach_response_hook(self, func):
        self.c.response_hook = func

    def detach_response_hook(self):
        self.c.response_hook = None

    def _get_url(self):
        assert self.resource_name, 'Descendant class must set the resource_name field'
        return '/%s/' % (self.resource_name,)

    def get(self, uuid=None):
        url = self._get_url()
        if uuid is not None:
            url += uuid
        return self.c.get(url, return_list=False)

    def get_schema(self):
        url = self._get_url() + 'schema'
        return self.c.get(url)

    def get_from_url(self, url):
        return self.c.get(url, return_list=False)

    def list(self, query_params=None):
        url = self._get_url()
        _query_params = {
            'limit': 0,  # get all results, do not use pagination
        }
        if query_params:
            _query_params.update(query_params)
        return self.c.get(url, query_params=_query_params, return_list=True)

    def list_detail(self, query_params=None):
        url = self._get_url() + 'detail/'
        _query_params = {
            'limit': 0,  # get all results, do not use pagination
        }
        if query_params:
            _query_params.update(query_params)
        return self.c.get(url, query_params=_query_params, return_list=True)

    def _pepare_data(self, data):
        res_data = data
        if isinstance(data, (list, tuple)):
            res_data = {'objects': data}
        elif isinstance(data, (dict,)):
            if not data.has_key('objects'):
                res_data = {'objects': [data]}
        else:
            raise TypeError('%r is not should be of type list, tuple or dict' % data)
        return res_data

    def create(self, data):
        url = self._get_url()
        return self.c.post(url, self._pepare_data(data), return_list=False)

    def update(self, uuid, data):
        url = self._get_url() + uuid + '/'
        return self.c.put(url, data, return_list=False)

    def delete(self, uuid):
        url = self._get_url() + uuid
        return self.c.delete(url)

    def _action(self, uuid, action, data=None):
        if uuid is None:
            url = self._get_url() + 'action/'
        else:
            url = self._get_url() + uuid + '/action/'
        return self.c.post(url, data, query_params={'do': action}, return_list=False)


class Profile(ResourceBase):
    resource_name = 'profile'

    def get(self):
        return self.c.get(self._get_url(), return_list=False)

    def update(self, data):
        return self.c.put(self._get_url(), data, return_list=False)


class LibDrive(ResourceBase):
    resource_name = 'libdrives'


class Drive(ResourceBase):
    resource_name = 'drives'

    def clone(self, uuid, data):
        return self._action(uuid, 'clone', data)


class Server(ResourceBase):
    resource_name = 'servers'

    def start(self, uuid, allocation_method=None):
        data = {}
        if allocation_method:
            data = {'allocation_method': str(allocation_method)}
        return self._action(uuid, 'start', data)

    def stop(self, uuid):
        return self._action(uuid,
                            'stop',
                            data={}     # Workaround API issue - see TUR-1346
                            )

    def restart(self, uuid):
        return self._action(uuid,
                            'restart',
                            data={}     # Workaround API issue - see TUR-1346
                            )

    def shutdown(self, uuid):
        return self._action(uuid,
                            'shutdown',
                            data={}     # Workaround API issue - see TUR-1346
                            )

    def runtime(self, uuid):
        url = self._get_url() + uuid + '/runtime/'
        return self.c.get(url, return_list=False)

    def open_vnc(self, uuid):
        return self._action(uuid, 'open_vnc', data={})

    def close_vnc(self, uuid):
        return self._action(uuid, 'close_vnc', data={})

    def clone(self, uuid, data=None):
        data = data or {}
        return self._action(uuid, 'clone', data=data)


class VLAN(ResourceBase):
    resource_name = 'vlans'


class IP(ResourceBase):
    resource_name = 'ips'


class FirewallPolicy(ResourceBase):
    resource_name = 'fwpolicies'


class Subscriptions(ResourceBase):
    resource_name = 'subscriptions'


class Ledger(ResourceBase):
    resource_name = 'ledger'


class Balance(ResourceBase):
    resource_name = 'balance'


class Discount(ResourceBase):
    resource_name = 'discount'


class Pricing(ResourceBase):
    resource_name = 'pricing'


class AuditLog(ResourceBase):
    resource_name = 'logs'


class Licenses(ResourceBase):
    resource_name = 'licenses'


class Capabilites(ResourceBase):
    resource_name = 'capabilities'


class Accounts(ResourceBase):
    resource_name = 'accounts'

    def authenticate_asynchronous(self):
        return self._action(None, 'authenticate_asynchronous', data={})  # data empty see TUR-1346


class CurrentUsage(ResourceBase):
    resource_name = 'currentusage'


class Tags(ResourceBase):

    resource_name = 'tags'

    def list_resource(self, uuid, resource_name):
        url = '{base}{tag_uuid}/{res_name}/'.format(base=self._get_url(), tag_uuid=uuid, res_name=resource_name)
        return self.c.get(url, return_list=True)

    def drives(self, uuid):
        return self.list_resource(uuid, 'drives')

    def servers(self, uuid):
        return self.list_resource(uuid, 'servers')

    def ips(self, uuid):
        return self.list_resource(uuid, 'ips')

    def vlans(self, uuid):
        return self.list_resource(uuid, 'vlans')


class WebsocketTimeoutError(Exception):
    pass


class Websocket(object):
    def __init__(self, timeout=10):
        self.timeout = timeout
        accounts = Accounts()
        accounts.authenticate_asynchronous()
        cookie = accounts.c.resp.cookies['async_auth']
        self.ws = WebsocketClient(cookie, self.timeout)

    def wait(self, message_filter=None, timeout=None):
        # message_filter = {'resource_type': ['drives']}
        # message_filter = {'resource_uri': ['/api/2.0/balance/']}

        events = []
        if message_filter is not None:
            for key in message_filter:
                if isinstance(message_filter[key], basestring):
                    message_filter[key] = [message_filter[key]]
        if timeout is None:
            timeout = self.timeout
        while timeout > 0:
            start_t = time.time()
            try:
                frame = self.ws.recv(timeout)
            except socket.timeout as e:
                raise WebsocketTimeoutError('Timeout reached when waiting for events')
            events.append(frame)
            if self.filter_frame(message_filter, frame):
                return events
            timeout = timeout - (time.time() - start_t)
        raise WebsocketTimeoutError('Timeout reached when waiting for events')

    def filter_frame(self, message_filter, frame):
        if not message_filter:
            return True
        for key in message_filter:
            if key in frame:
                for value in message_filter[key]:
                    if frame[key] == value:
                        return True
        return False

    def wait_obj_type(self, resource_type, cls, timeout=None):
        ret = self.wait({"resource_type": resource_type})[-1]
        return cls().get_from_url(ret['resource_uri'])

    def wait_obj_type(self, resource_type, cls, timeout=None):
        ret = self.wait({"resource_type": resource_type})[-1]
        return cls().get_from_url(ret['resource_uri'])
