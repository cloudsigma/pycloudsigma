from builtins import str, object
import socket
import os
import time
import requests

from past.builtins import basestring

from cloudsigma.generic import get_client, WebsocketClient, GenericClient


class ResourceBase(object):
    resource_name = None

    def __init__(self, *args, **kwargs):
        self.c = get_client()(*args, **kwargs)

    def attach_response_hook(self, func):
        self.c.response_hook = func

    def detach_response_hook(self):
        self.c.response_hook = None

    def _get_url(self):
        assert self.resource_name, \
            'Descendant class must set the resource_name field'
        return '/%s/' % (self.resource_name,)

    def get(self, uuid=None):
        url = self._get_url()
        if uuid is not None:
            if isinstance(uuid, bytes):
                uuid_str = uuid.decode('utf-8')
            else:
                uuid_str = uuid
            url += uuid_str
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
        elif isinstance(data, dict):
            if 'objects' not in data:
                res_data = {'objects': [data]}
        else:
            raise TypeError(
                '%r is not should be of type list, tuple or dict' % data
            )
        return res_data

    def create(self, data, query_params=None):
        query_params = query_params or {}
        url = self._get_url()
        return self.c.post(
            url,
            self._pepare_data(data),
            return_list=False,
            query_params=query_params
        )

    def update(self, uuid, data):
        url = self._get_url() + uuid + '/'
        return self.c.put(url, data, return_list=False)

    def delete(self, uuid, query_params=None):
        url = self._get_url() + uuid
        return self.c.delete(url, query_params=query_params)

    def _action(self, uuid, action, data=None, query_params=None):
        query_params = query_params or {}
        q_params = {'do': action}
        q_params.update(query_params)

        if uuid is None:
            url = self._get_url() + 'action/'
        else:
            url = self._get_url() + uuid + '/action/'
        return self.c.post(
            url,
            data,
            query_params=q_params,
            return_list=False
        )


class Profile(ResourceBase):
    resource_name = 'profile'

    def get(self):
        return self.c.get(self._get_url(), return_list=False)

    def update(self, data):
        return self.c.put(self._get_url(), data, return_list=False)


class GlobalContext(ResourceBase):
    resource_name = 'global_context'

    def get(self):
        return self.c.get(self._get_url(), return_list=False)

    def update(self, data):
        return self.c.post(self._get_url(), data, return_list=False)


class NotificationContact(ResourceBase):
    resource_name = 'notification_contacts'


class NotificationPreference(ResourceBase):
    resource_name = 'notification_preferences'

    def update(self, data):
        return self.c.put(self._get_url(), data, return_list=True)


class LibDrive(ResourceBase):
    resource_name = 'libdrives'


class Drive(ResourceBase):
    resource_name = 'drives'

    def clone(self, uuid, data=None, avoid=None):
        """
        Clone a drive.

        :param uuid:
            Source drive for the clone.
        :param data:
            Clone drive options. Refer to API docs for possible options.
        :param avoid:
            A list of drive or server uuids to avoid for the clone.
            Avoid attempts to put the clone on a different physical storage
            host from the drives in *avoid*.
            If a server uuid is in *avoid* it is internally expanded
            to the drives attached to the server.
        :return:
            Cloned drive definition.
        """
        data = data or {}
        query_params = {}
        if avoid:
            if isinstance(avoid, basestring):
                avoid = [avoid]
            query_params['avoid'] = ','.join(avoid)

        return self._action(uuid, 'clone', data, query_params=query_params)

    def resize(self, uuid, data=None):
        """
        Resize a drive. Raises an error if drive is mounted on a running
        server or unavailable.
        :param uuid:
            UUID of the drive.
        :param data:
            Drive definition containing the new size.
        :return:
        """
        data = data or {}
        return self._action(uuid, 'resize', data)

    def create(self, data, avoid=None):
        """
        Create a drive.

        :param data:
            Drive definition.
        :param avoid:
            A list of drive or server uuids to avoid for the new drive.
            Avoid attempts to put the drive on a different physical storage
            host from the drives in *avoid*. If a server uuid is in *avoid*
            it is internally expanded to the drives attached to the server.
        :return:
            New drive definition.
        """
        query_params = {}
        if avoid:
            if isinstance(avoid, basestring):
                avoid = [avoid]
            query_params['avoid'] = ','.join(avoid)
        return super(Drive, self).create(data, query_params=query_params)

    def get_upload_chunk_link(self, uuid, chunk_number, chunk_size=5 * 1024 ** 2):
        """
        Get an upload URL for a give chunk
        :param uuid:
            UUID of the drive. Needs to be in *uploading* state
        :type uuid: basestring
        :param chunk_number:
            The number of the chunk to upload. Counting starts from 0 and last chunk is bigger in size, for example
            if drive is 5MiB and chunks are 2MiB each, the last chunk (chunk 1) is 3MiB.
        :type chunk_number: int
        :param chunk_size:
            Size of the upload chunk in bytes. For example use 2 * 1024 ** 2 for 2MiB chunks.
        :type chunk_size: int
        :return:
            A link to upload the chunk to. The link does not require authentication and is valid for 5 minutes
        :rtype: str
        """
        res_data = self._action(uuid, 'upload_chunk', {'chunk_number': chunk_number, 'chunk_size': chunk_size})
        return res_data['link']

    def upload_chunk(self, link, image_path, chunk_number, chunk_size):
        chunk_offset = chunk_number * chunk_size
        file_size = os.path.getsize(image_path)
        n_chunks = file_size // chunk_size
        if n_chunks == 0:
            real_chunk_size = file_size
        elif chunk_number < n_chunks - 1:
            real_chunk_size = chunk_size
        else:
            real_chunk_size = file_size - chunk_offset
        with open(image_path, 'r') as f:
            f.seek(chunk_offset)
            data = f.read(real_chunk_size)

        headers = {
            'User-Agent': 'CloudSigma turlo client',
            'Content-Type': 'application/octet-stream',
            'Accept': 'application/json'
        }
        return requests.post(self.c._get_full_url(link), data=data, headers=headers)


class InitUpload(ResourceBase):
    resource_name = 'initupload'

    def create(self, data, avoid=None, image_path=None):
        """
        Create a drive for upload.

        :param data:
            Drive definition. Note that the size of the drive should be equal to the exact file size to be uploaded up
            to a KiB. The image format should be raw disk image.
        :param avoid:
            A list of drive or server uuids to avoid for the new drive. Avoid attempts to put the drive on a different
            physical storage host from the drives in *avoid*. If a server uuid is in *avoid* it is internally expanded
            to the drives attached to the server.
        :param image_path:
            A path to the drive image to be uploaded. If given, and no name is specified in data, filename will be used
            as a drive name, also if the size parameter is not preset the file size will be used.
        :return:
            New drive definition.
        """
        query_params = {}
        if not data.get('name'):
            data['name'] = os.path.split(image_path)[1]
        if not data.get('size'):
            data['size'] = os.path.getsize(image_path)
        if avoid:
            if isinstance(avoid, basestring):
                avoid = [avoid]
            query_params['avoid'] = ','.join(avoid)
        return super(InitUpload, self).create(data, query_params=query_params)


class Server(ResourceBase):
    resource_name = 'servers'

    def start(self, uuid, allocation_method=None):
        data = {}
        if allocation_method:
            data = {'allocation_method': str(allocation_method)}
        return self._action(uuid, 'start', data)

    def stop(self, uuid):
        return self._action(
            uuid,
            'stop',
            data={}  # Workaround API issue - see TUR-1346
        )

    def restart(self, uuid):
        return self._action(
            uuid,
            'restart',
            data={}  # Workaround API issue - see TUR-1346
        )

    def shutdown(self, uuid):
        return self._action(
            uuid,
            'shutdown',
            data={}  # Workaround API issue - see TUR-1346
        )

    def runtime(self, uuid):
        url = self._get_url() + uuid + '/runtime/'
        return self.c.get(url, return_list=False)

    def open_vnc(self, uuid):
        return self._action(uuid, 'open_vnc', data={})

    def close_vnc(self, uuid):
        return self._action(uuid, 'close_vnc', data={})

    def open_console(self, uuid):
        return self._action(uuid, 'open_console', data={})

    def close_console(self, uuid):
        return self._action(uuid, 'close_console', data={})

    def clone(self, uuid, data=None, avoid=None):
        """
        Clone a server. Attached disk drives get cloned and attached to the new
        server, and attached cdroms get attached to the
        new server (without cloning).

        :param uuid:
            Source server for the clone.
        :param data:
            Clone server options. Refer to API docs for possible options.
        :param avoid:
            A list of drive or server uuids to avoid for the clone. Avoid
            attempts to put the cloned drives on a different physical storage
            host from the drives in *avoid*. If a server uuid is in *avoid* it
            is internally expanded to the drives attached to the server.
        :return:
            Cloned server definition.
        """
        data = data or {}
        query_params = {}
        if avoid:
            if isinstance(avoid, basestring):
                avoid = [avoid]
            query_params['avoid'] = ','.join(avoid)

        return self._action(uuid, 'clone', data=data,
                            query_params=query_params)

    def delete(self, uuid, recurse=None):
        """
        Deletes a server.

        :param uuid:
            uuid of the server to delete
        :param recurse:
            option to recursively delete attached drives. Possible values are
            'all_drives', 'disks'. It is possible to use one of the supplied
            convenience functions: delete_with_all_drives, delete_with_disks,
            delete_with_cdroms

        :return:
        """
        query_params = {}
        if recurse is not None:
            query_params.update(recurse=recurse)
        if not query_params:
            query_params = None

        return super(Server, self).delete(uuid, query_params=query_params)

    def delete_with_all_drives(self, uuid):
        """
        Deletes a server with all attached drives.
        :param uuid: uuid of the server to delete
        :return:
        """
        return self.delete(uuid, recurse='all_drives')

    def delete_with_disks(self, uuid):
        """
        Deletes a server with all attached drives with media='disk'.
        :param uuid: uuid of the server to delete
        :return:
        """
        return self.delete(uuid, recurse='disks')

    def delete_with_cdroms(self, uuid):
        """
        Deletes a server with all attached drives with media='cdrom'.
        :param uuid: uuid of the server to delete
        :return:
        """
        return self.delete(uuid, recurse='cdroms')


class BServer(Server):
    resource_name = 'bservers'


class ServersAvailabilityGroups(ResourceBase):
    resource_name = 'servers/availability_groups'


class VLAN(ResourceBase):
    resource_name = 'vlans'


class IP(ResourceBase):
    resource_name = 'ips'


class FirewallPolicy(ResourceBase):
    resource_name = 'fwpolicies'


class Subscriptions(ResourceBase):
    resource_name = 'subscriptions'

    def extend(self, uuid, data=None):
        return self._action(uuid, 'extend', data or {})


class SubscriptionCalculator(Subscriptions):
    resource_name = 'subscriptioncalculator'

    def get_price(self, amount, period, resource_type):
        data = dict(
            amount=amount,
            period=period,
            resource=resource_type
        )
        resp = self.create(data)
        return resp['price']


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
        # data empty see TUR-1346
        return self._action(None, 'authenticate_asynchronous', data={})

    def create(self, email, promo_code=None):
        self.c._session = None
        self.c.login_method = GenericClient.LOGIN_METHOD_NONE
        return self._action(
            None, 'create', data={'email': email, 'promo': promo_code})


class CurrentUsage(ResourceBase):
    resource_name = 'currentusage'


class Snapshot(ResourceBase):
    resource_name = 'snapshots'

    def clone(self, uuid, data=None, avoid=None):
        """
        Clone a snapshot (creates a drive).

        :param uuid:
            Source snapshot for the clone.
        :param data:
            Clone snapshot options. Refer to API docs for possible options.
        :param avoid:
            A list of snapshot or server uuids to avoid for the clone. Avoid
            attempts to put the clone on a different physical storage host from
            the snapshot in *avoid*. If a server uuid is in *avoid* it is
            internally expanded to the snapshots attached to the server.
        :return:
            Cloned snapshot definition.
        """
        data = data or {}
        query_params = {}
        if avoid:
            if isinstance(avoid, basestring):
                avoid = [avoid]
            query_params['avoid'] = ','.join(avoid)

        return self._action(uuid, 'clone', data, query_params=query_params)


class Tags(ResourceBase):
    resource_name = 'tags'

    def list_resource(self, uuid, resource_name):
        url = '{base}{tag_uuid}/{res_name}/'.format(
            base=self._get_url(),
            tag_uuid=uuid,
            res_name=resource_name
        )
        return self.c.get(url, return_list=True)

    def drives(self, uuid):
        return self.list_resource(uuid, 'drives')

    def servers(self, uuid):
        return self.list_resource(uuid, 'servers')

    def ips(self, uuid):
        return self.list_resource(uuid, 'ips')

    def vlans(self, uuid):
        return self.list_resource(uuid, 'vlans')


class Acls(ResourceBase):
    resource_name = 'acls'


class Jobs(ResourceBase):
    resource_name = 'jobs'


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
                raise WebsocketTimeoutError(
                    'Timeout reached when waiting for events'
                )
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

    def wait_obj_uri(self, resource_uri, cls, timeout=None):
        ret = self.wait({"resource_uri": resource_uri})
        return cls().get_from_url(resource_uri)

    def wait_obj_wrapper(
            self,
            waiter,
            args,
            kwargs=None,
            timeout=None,
            extra_filter=lambda x: True
    ):
        if timeout is None:
            timeout = self.timeout
        if kwargs is None:
            kwargs = {}
        while timeout > 0:
            start_t = time.time()
            kwargs['timeout'] = timeout
            frame = waiter(*args, **kwargs)
            if extra_filter(frame):
                return frame
            timeout = timeout - (time.time() - start_t)
        raise WebsocketTimeoutError('Timeout reached when waiting for events')

    def wait_for_status(self, uri, resource, status, timeout=30):
        return self.wait_obj_wrapper(
            self.wait_obj_uri,
            (uri, resource),
            timeout=timeout,
            extra_filter=lambda x: x['status'] == status
        )


class BurstUsage(ResourceBase):
    resource_name = 'burstusage'


class Locations(ResourceBase):
    resource_name = 'locations'


class RemoteSnapshot(ResourceBase):
    resource_name = 'remotesnapshots'

    def clone(self, uuid, data=None, avoid=None):
        """
        Clone a drive from a remote snapshot.

        :param uuid:
            Source drive for the clone.
        :param data:
            Clone drive options. Refer to API docs for possible options.
        :param avoid:
            A list of drive or server uuids to avoid for the clone.
            Avoid attempts to put the clone on a different
            physical storage host from the drives in *avoid*.
            If a server uuid is in *avoid* it is internally expanded
            to the drives attached to the server.
        :return:
            Cloned drive definition.
        """
        data = data or {}
        query_params = {}
        if avoid:
            if isinstance(avoid, basestring):
                avoid = [avoid]
            query_params['avoid'] = ','.join(avoid)

        return self._action(uuid, 'clone', data, query_params=query_params)


class Vpc(ResourceBase):
    resource_name = 'vpc'


class Nodes(ResourceBase):
    resource_name = 'nodes'


class HostAvailabilityZones(ResourceBase):
    resource_name = 'hostavailabilityzones'


class HostAllocationPools(ResourceBase):
    resource_name = 'hostallocationpools'


class DriveUsers(ResourceBase):
    resource_name = 'driveusers'


class VirtualRouters(ResourceBase):
    resource_name = 'virtualrouters'

    def enable_nat(self, virtual_router_uuid, data):
        data = data or {}
        return self._action(virtual_router_uuid, 'enable_nat', data)

    def disable_nat(self, virtual_router_uuid, data):
        data = data or {}
        return self._action(virtual_router_uuid, 'disable_nat', data)

    def enable_firewall(self, virtual_router_uuid, data):
        data = data or {}
        return self._action(virtual_router_uuid, 'enable_firewall', data)

    def disable_firewall(self, virtual_router_uuid, data):
        data = data or {}
        return self._action(virtual_router_uuid, 'disable_firewall', data)

    def enable_firewall_logging(self, virtual_router_uuid, data):
        data = data or {}
        action = 'enable_firewall_logging'
        return self._action(virtual_router_uuid, action, data)

    def disable_firewall_logging(self, virtual_router_uuid, data):
        data = data or {}
        action = 'disable_firewall_logging'
        return self._action(virtual_router_uuid, action, data)

    def get_log(self, virtual_router_uuid, data, query_params):
        data = data or {}
        return self._action(
            virtual_router_uuid, 'get_log', data, query_params=query_params)


class Lans(ResourceBase):
    resource_name = 'lans'

    def configure_dhcp(self, virtual_router_uuid, data):
        data = data or {}
        return self._action(virtual_router_uuid, 'configure_dhcp', data)


class IpAliases(ResourceBase):
    resource_name = 'ipaliases'


class Upstream(ResourceBase):
    resource_name = 'upstream'

    def configure_vpn(self, virtual_router_uuid, data):
        data = data or {}
        return self._action(virtual_router_uuid, 'configure_vpn', data)


class PortForwards(ResourceBase):
    resource_name = 'portforwards'


class AddressForwards(ResourceBase):
    resource_name = 'addressforwards'


class VrFwPolicies(ResourceBase):
    resource_name = 'vrfwpolicies'

    def enable(self, fw_policy_uuid, data):
        data = data or {}
        return self._action(fw_policy_uuid, 'enable', data)

    def disable(self, fw_policy_uuid, data):
        data = data or {}
        return self._action(fw_policy_uuid, 'disable', data)


class VrFwFilters(ResourceBase):
    resource_name = 'vrfwfilters'

    def enable_logging(self, fw_filter_uuid, data):
        data = data or {}
        return self._action(fw_filter_uuid, 'enable_logging', data)

    def disable_logging(self, fw_filter_uuid, data):
        data = data or {}
        return self._action(fw_filter_uuid, 'disable_logging', data)


class Routes(ResourceBase):
    resource_name = 'routes'
