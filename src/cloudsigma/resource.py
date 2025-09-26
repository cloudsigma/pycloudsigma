from builtins import str, object
import socket
import os
import time
import requests
import sys

from past.builtins import basestring

# Add try-except for basestring for broader compatibility
try:
    basestring
except NameError:
    basestring = str

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
        """
        Edits a user profile.
        """
        url = self._get_url()
        return self.c.put(url, data, return_list=False)


class GlobalContext(ResourceBase):
    resource_name = 'global_context'

    def get(self):
        return self.c.get(self._get_url(), return_list=False)

    def update(self, data):
        return self.c.post(self._get_url(), data, return_list=False)


class NotificationContact(ResourceBase):
    resource_name = 'notification_contacts'


class NotificationContacts(ResourceBase):
    resource_name = 'notification_contacts'


class NotificationPreference(ResourceBase):
    resource_name = 'notification_preferences'

    def update(self, data):
        """
        Updates the specified notification preferences. Only the ones in the request are modified.

        :param data:
            A dictionary or a list of dictionaries representing the preferences to update.
            Each dictionary should contain 'contact', 'medium', 'type', and 'value'.
        :return:
            Updated notification preferences.
        """
        url = self._get_url()
        return self.c.put(
            url,
            self._pepare_data(data),
            return_list=True
        )


class LibDrive(ResourceBase):
    resource_name = 'libdrives'

    def clone(self, uuid, data=None):
        """
        Clone a library drive.

        :param uuid:
            Source library drive for the clone.
        :param data:
            Clone drive options. Refer to API docs for possible options.
        :return:
            Cloned drive definition.
        """
        data = data or {}
        return self._action(uuid, 'clone', data)


class Drive(ResourceBase):
    resource_name = 'drives'

    def clone(self, uuid, data=None, avoid=None):
        """
        Clones a drive. Request body is optional and any or all of the key/value
        pairs from the drive definition can be omitted. Size of the cloned drive
        can only be bigger or the same.

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
            Updated drive definition.
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
        with open(image_path, 'rb') as f: # Changed from 'r' to 'rb' for binary file reading
            f.seek(chunk_offset)
            data = f.read(real_chunk_size)

        headers = {
            'User-Agent': 'CloudSigma turlo client',
            'Content-Type': 'application/octet-stream',
            'Accept': 'application/json'
        }
        return requests.post(self.c._get_full_url(link), data=data, headers=headers)

    def delete_multiple(self, uuids, query_params=None):
        """
        Deletes multiple mounted or unmounted drives specified by their UUIDs.

        :param uuids:
            A list of drive UUIDs to delete.
        :type uuids: list of basestring
        :param query_params:
            Additional query parameters.
        :return:
            Deletion confirmation.
        """
        if not isinstance(uuids, (list, tuple)):
            raise TypeError('uuids must be a list or tuple of drive UUIDs')
        
        data = {'objects': [{'uuid': u} for u in uuids]}
        
        url = self._get_url()
        return self.c.delete(url, data=data, query_params=query_params)

    def list_availability_groups(self, query_params=None):
        url = self._get_url() + 'availability_groups/'
        _query_params = {
            'limit': 0,  # get all results, do not use pagination
        }
        if query_params:
            _query_params.update(query_params)
        return self.c.get(url, query_params=_query_params, return_list=True)

    def get_availability_group(self, uuid):
        url = self._get_url() + 'availability_groups/'
        if uuid is not None:
            if isinstance(uuid, bytes):
                uuid_str = uuid.decode('utf-8')
            else:
                uuid_str = uuid
            url += uuid_str + '/'
        return self.c.get(url, return_list=False)


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

    def start(self, uuid, allocation_method=None, data=None, query_params=None, avoid=None):
        """
        Starts a server with specific UUID.

        :param uuid:
            UUID of the server to start.
        :param allocation_method:
            Optional parameter to specify how resources should be allocated.
            Refer to API docs for possible options.
        :param data:
            Dictionary of body parameters to append to the request.
        :param query_params:
            Dictionary of query parameters to append to the request.
        :param avoid:
            A list of drive or server uuids to avoid for the server start.
            Avoid attempts to put the server on a different physical host from
            the resources in *avoid*.
        :return:
            API response.
        """
        _data = data or {}
        if allocation_method:
            _data['allocation_method'] = str(allocation_method)
        
        _query_params = query_params or {}
        if avoid:
            _avoid_list = []
            if isinstance(avoid, (str, bytes)):
                if isinstance(avoid, bytes):
                    _avoid_list.append(avoid.decode('utf-8'))
                else:
                    _avoid_list.append(avoid)
            elif isinstance(avoid, (list, tuple)):
                for item in avoid:
                    if isinstance(item, bytes):
                        _avoid_list.append(item.decode('utf-8'))
                    elif isinstance(item, str):
                        _avoid_list.append(item)
                    else:
                        raise TypeError("Avoid list elements must be strings or bytes, not %r" % item)
            else:
                raise TypeError("Avoid must be a string, bytes, list, or tuple, not %r" % avoid)
            
            if _avoid_list:
                _query_params['avoid'] = ','.join(_avoid_list)

        return self._action(uuid, 'start', data=_data, query_params=_query_params)

    def stop(self, uuid, data=None, query_params=None):
        """
        Stops a server with specific UUID. This action is equivalent to pulling the
        power cord of a physical server. For more graceful shutdown see ACPI Shutdown.

        :param uuid:
            UUID of the server to stop.
        :param data:
            Dictionary of body parameters to append to the request. (Used for API workaround).
        :param query_params:
            Dictionary of query parameters to append to the request.
        :return:
            API response.
        """
        # Preserve the workaround if data is not explicitly provided by the caller
        _data = data if data is not None else {}
        return self._action(
            uuid,
            'stop',
            data=_data,
            query_params=query_params
        )

    def restart(self, uuid, data=None, query_params=None):
        """
        Restarts a server with specific UUID. This action is equivalent to pressing the
        reset button of a physical server.

        :param uuid:
            UUID of the server to restart.
        :param data:
            Dictionary of body parameters to append to the request. (Used for API workaround).
        :param query_params:
            Dictionary of query parameters to append to the request.
        :return:
            API response.
        """
        _data = data if data is not None else {}
        return self._action(
            uuid,
            'restart',
            data=_data,
            query_params=query_params
        )

    def shutdown(self, uuid, data=None, query_params=None):
        """
        Sends an ACPI shutdown signal to a server with a specific UUID for a minute.
        If the VM OS handles ACPI shutdown events (equivalent to pressing the power button),
        it will shutdown gracefully. As some operating systems don’t always handle single
        ACPI event the shutdown is sent every second for a minute. While the shutdown is
        initiated, the server is put into status 'stopping' to prevent interfering actions.
        If after a minute the server has not powered off during this minute the status
        is returned to 'running' to allow the user to Stop it. If the server shuts down
        successfully during the one minute period it will be switched to 'stopped' status.

        :param uuid:
            UUID of the server to shutdown.
        :param data:
            Dictionary of body parameters to append to the request. (Used for API workaround).
        :param query_params:
            Dictionary of query parameters to append to the request.
        :return:
            API response.
        """
        _data = data if data is not None else {}
        return self._action(
            uuid,
            'shutdown',
            data=_data,
            query_params=query_params
        )

    def runtime(self, uuid):
        url = self._get_url() + uuid + '/runtime/'
        return self.c.get(url, return_list=False)

    def open_vnc(self, uuid, data=None, query_params=None):
        """
        Open a VNC connection to a server with a specific UUID.

        :param uuid:
            UUID of the server to open VNC for.
        :param data:
            Dictionary of body parameters to append to the request. (Used for API workaround).
        :param query_params:
            Dictionary of query parameters to append to the request.
        :return:
            API response, including VNC connection details.
        """
        _data = data if data is not None else {}
        return self._action(uuid, 'open_vnc', data=_data, query_params=query_params)

    def close_vnc(self, uuid, data=None, query_params=None):
        """
        Close a VNC connection to a server with a specific UUID.

        :param uuid:
            UUID of the server to close VNC for.
        :param data:
            Dictionary of body parameters to append to the request. (Used for API workaround).
        :param query_params:
            Dictionary of query parameters to append to the request.
        :return:
            API response.
        """
        _data = data if data is not None else {}
        return self._action(uuid, 'close_vnc', data=_data, query_params=query_params)

    def open_console(self, uuid, data=None, query_params=None):
        """
        Open a serial console connection to a server with a specific UUID.
        Each server has a virtual serial device, which is tunneled to a TCP socket.
        The serial device is seen as /dev/ttyS0 or COM1 on most operating systems.
        If your OS supports it, you can configure a serial console on this virtual
        serial port, which might be more convenient to use than VNC, as it generally
        uses less bandwidth and allows you to copy-paste in the virtual terminal.

        The return object contains 'console_url' formatted as csconsole://<cs-domain>:<port>.

        :param uuid:
            UUID of the server to open console for.
        :param data:
            Dictionary of body parameters to append to the request. (Used for API workaround).
        :param query_params:
            Dictionary of query parameters to append to the request.
        :return:
            The console URL (str).
        """
        _data = data if data is not None else {}
        res_data = self._action(uuid, 'open_console', data=_data, query_params=query_params)
        return res_data['console_url']

    def close_console(self, uuid, data=None, query_params=None):
        """
        Closes a serial console connection to a server with a specific UUID.

        :param uuid:
            UUID of the server to close console for.
        :param data:
            Dictionary of body parameters to append to the request. (Used for API workaround).
        :param query_params:
            Dictionary of query parameters to append to the request.
        :return:
            API response.
        """
        _data = data if data is not None else {}
        return self._action(uuid, 'close_console', data=_data, query_params=query_params)

    def clone(self, uuid, data=None, avoid=None, name=None, random_vnc_password=None, query_params=None):
        """
        Clones a server. Attached disk drives get cloned and attached to the new
        server, and attached cdroms get attached to the
        new server (without cloning).

        The optional body can contain a 'name' attribute, which will be the name of
        the newly-cloned server and/or 'random_vnc_password' boolean attribute which
        if set will generate a new vnc password for the new server.

        :param uuid:
            Source server for the clone.
        :param data:
            Clone server options. Refer to API docs for possible options.
        :param avoid:
            A list of drive or server uuids to avoid for the clone. Avoid
            attempts to put the cloned drives on a different physical storage
            host from the drives in *avoid*. If a server uuid is in *avoid* it
            is internally expanded to the drives attached to the server.
        :param name:
            Optional name for the cloned server.
        :param random_vnc_password:
            If True, a new random VNC password will be generated for the cloned server.
        :param query_params:
            Dictionary of additional query parameters to append to the request.
        :return:
            Cloned server definition.
        """
        _data = data or {}
        if name is not None:
            _data['name'] = name
        if random_vnc_password is not None:
            _data['random_vnc_password'] = random_vnc_password

        _query_params = query_params or {}
        if avoid:
            _avoid_list = []
            if isinstance(avoid, (str, bytes)):
                if isinstance(avoid, bytes):
                    _avoid_list.append(avoid.decode('utf-8'))
                else:
                    _avoid_list.append(avoid)
            elif isinstance(avoid, (list, tuple)):
                for item in avoid:
                    if isinstance(item, bytes):
                        _avoid_list.append(item.decode('utf-8'))
                    elif isinstance(item, str):
                        _avoid_list.append(item)
                    else:
                        raise TypeError("Avoid list elements must be strings or bytes, not %r" % item)
            else:
                raise TypeError("Avoid must be a string, bytes, list, or tuple, not %r" % avoid)
            
            if _avoid_list:
                _query_params['avoid'] = ','.join(_avoid_list)

        return self._action(uuid, 'clone', data=_data, query_params=_query_params)

    def delete(self, uuid, recurse=None, query_params=None):
        """
        Deletes a single server.
        It is possible to delete a server together with its drives (recursive delete).
        There are three options: delete all attached drives, delete only disks
        (non-cdrom drives), or delete only attached cdroms.

        :param uuid:
            UUID of the server to delete.
        :param recurse:
            Optional parameter for recursive deletion of drives.
            Can be 'all_drives', 'disks', or 'cdroms'.
        :param query_params:
            Dictionary of query parameters to append to the request.
        :return:
            API response.
        """
        query_params = query_params or {}
        if recurse:
            if recurse not in ['all_drives', 'disks', 'cdroms']:
                raise ValueError("recurse must be one of 'all_drives', 'disks', 'cdroms'")
            query_params['recurse'] = recurse
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

    def list_availability_groups(self, query_params=None):
        url = self._get_url() + 'availability_groups/'
        _query_params = {
            'limit': 0,
        }
        if query_params:
            _query_params.update(query_params)
        return self.c.get(url, query_params=_query_params, return_list=True)

    def get_availability_group(self, uuid):
        url = self._get_url() + 'availability_groups/'
        if uuid is not None:
            if isinstance(uuid, bytes):
                uuid_str = uuid.decode('utf-8')
            else:
                uuid_str = uuid
            url += uuid_str + '/'
        return self.c.get(url, return_list=False)


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

    def list(self, status=None, resource=None, query_params=None):
        """
        Gets the list of subscriptions of the user.

        :param status:
            filters only subscriptions in that status. Can be one of active,
            inactive, expired, all, notexpired. Default is all.
        :type status: basestring or None
        :param resource:
            a list (comma separated) of resources. One or more of:
            dssd, cpu, mem, tx, ip, vlan.
        :type resource: basestring or None
        :param query_params:
            Additional query parameters.
        :type query_params: dict or None
        :return:
            List of subscriptions.
        """
        _query_params = {
            'limit': 0,  # get all results, do not use pagination
        }
        if status:
            _query_params['status'] = status
        if resource:
            _query_params['resource'] = resource
        if query_params:
            _query_params.update(query_params)
        return super(Subscriptions, self).list(query_params=_query_params)

    def extend(self, uuid, data=None, query_params=None): # Updated signature and implementation
        """
        Extends the subscription. An extended subscription is actually just
        another subscription that is linked to the original.
        If a period or and end_time are specified in the request, they are used.
        If neither are specified, the creation length of the subscription is used.

        :param uuid:
            ID of the subscription to extend. (Renamed from subscription_id for backwards compatibility)
        :type uuid: basestring
        :param data:
            Optional data to specify period or end_time.
        :type data: dict or None
        :param query_params:
            Additional query parameters.
        :type query_params: dict or None
        :return:
            Extended subscription definition.
        """
        data = data or {}
        return self._action(uuid, 'extend', data=data, query_params=query_params)

    def auto_renew(self, subscription_id, data=None, query_params=None):
        """
        Toggles the autorenew flag of the subscription. Optionally, the value
        can be specified in the request.

        :param subscription_id:
            ID of the subscription to modify.
        :type subscription_id: basestring
        :param data:
            Optional data to explicitly set auto_renew status (e.g., {'auto_renew': True}).
        :type data: dict or None
        :param query_params:
            Additional query parameters.
        :type query_params: dict or None
        :return:
            Modified subscription definition.
        """
        data = data or {}
        return self._action(subscription_id, 'auto_renew', data=data, query_params=query_params)


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

    def calculate(self, data, query_params=None):
        """
        Returns the price of the subscriptions POSTed in the same format
        as the normal subscriptions.

        :param data:
            Subscription details to calculate price for.
        :type data: dict or list
        :param query_params:
            Additional query parameters.
        :type query_params: dict or None
        :return:
            Price calculation response.
        """
        query_params = query_params or {}
        url = self._get_url()
        return self.c.post(
            url,
            self._pepare_data(data),
            return_list=False,
            query_params=query_params
        )

    def calculate_extension(self, subscription_id, data=None, query_params=None):
        """
        Calculates the price of extending a subscription.

        :param subscription_id:
            ID of the subscription to calculate extension price for.
        :type subscription_id: basestring
        :param data:
            Optional data for extension calculation (e.g., specific period or end_time).
        :type data: dict or None
        :param query_params:
            Additional query parameters.
        :type query_params: dict or None
        :return:
            Extension price calculation response.
        """
        data = data or {}
        return self._action(subscription_id, 'extend', data=data, query_params=query_params)


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


class AuditLogs(ResourceBase):
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

    def create_account(self, email, promo=None):
        """
        Creates an account on the system.

        :param email:
            The email of the account to be created.
        :type email: str
        :param promo:
            Promo code for initial subscriptions and demo server (optional).
        :type promo: str or None
        :return:
            A dictionary with success status and the UUID of the created account.
        :rtype: dict
        """
        data = {
            'email': email,
            'promo': promo
        }
        return self._action(None, 'create', data=data)

    def login(self, username, password):
        """
        Log in to the system using cookie auth.

        :param username:
            The username (email) for login.
        :type username: str
        :param password:
            The password for login.
        :type password: str
        :return:
            An empty response on success.
        """
        data = {
            'username': username,
            'password': password
        }
        return self._action(None, 'login', data=data)

    def logout(self):
        """
        Logout from the system when using cookie auth.

        :return:
            An empty response on success.
        """
        return self._action(None, 'logout', data={})

    def check_login(self):
        """
        Check if you are logged in to the system.

        :return:
            An empty response on success.
        """
        return self._action(None, 'check_login', data={})

    def check_login_with_return_uuid(self, username, password):
        """
        Check how an authenticated service can get a user uuid via CloudSigma API.

        :param username:
            The username (email) for checking login.
        :type username: str
        :param password:
            The password for checking login.
        :type password: str
        :return:
            The user UUID on success.
        """
        data = {
            'username': username,
            'password': password
        }
        return self._action(None, 'check_login_with_return_uuid', data=data)


class CurrentUsage(ResourceBase):
    resource_name = 'currentusage'


class Snapshot(ResourceBase):
    resource_name = 'snapshots'

    def delete_many(self, uuids):
        """
        Deletes multiple snapshots specified by their UUIDs.

        :param uuids: A list of snapshot UUIDs to delete.
        :type uuids: list of str
        :return: Response from the API call.
        """
        data = [{'uuid': u} for u in uuids]
        url = self._get_url()
        return self.c.delete(url, self._pepare_data(data))

    def clone(self, uuid, data=None, avoid=None):
        """
        Clones a snapshot to a drive.

        :param uuid: UUID of the snapshot to clone.
        :type uuid: basestring
        :param data: Optional new drive definition for the cloned drive.
        :type data: dict
        :param avoid: A list of drive or server UUIDs to avoid for the clone.
                      Avoid attempts to put the clone on a different physical storage
                      host from the resources in *avoid*.
        :type avoid: list or basestring
        :return: Cloned drive definition.
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

    def list_resources(self, tag_uuid, resource_type, query_params=None):
        """
        Lists resources (servers, drives, IPs, or VLANs) associated with a given tag.

        :param tag_uuid:
            UUID of the tag.
        :type tag_uuid: basestring
        :param resource_type:
            Type of resource to list. Must be one of 'servers', 'drives', 'ips', 'vlans'.
        :type resource_type: basestring
        :param query_params:
            Dictionary of query parameters to append to the request.
        :type query_params: dict or None
        :return:
            A list of resources associated with the tag.
        :rtype: list
        """
        if resource_type not in ['servers', 'drives', 'ips', 'vlans']:
            raise ValueError(
                "resource_type must be one of 'servers', 'drives', 'ips', 'vlans'"
            )

        url = self._get_url() + '{}/{}/'.format(tag_uuid, resource_type)
        _query_params = {
            'limit': 0,  # get all results, do not use pagination
        }
        if query_params:
            _query_params.update(query_params)
        return self.c.get(url, query_params=_query_params, return_list=True)


class Acls(ResourceBase):
    resource_name = 'acls'


class Acl(ResourceBase):
    resource_name = 'acls'


class Jobs(ResourceBase):
    resource_name = 'jobs'


class Job(ResourceBase):
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


class DailyBurstUsage(ResourceBase):
    resource_name = 'dailyburstusage'


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

    def delete_multiple(self, uuids, query_params=None):
        """
        Deletes multiple remote snapshots specified by their UUIDs.

        :param uuids:
            A list of remote snapshot UUIDs to delete.
        :type uuids: list
        :param query_params:
            Additional query parameters.
        :return:
            API response (204 No Content expected).
        """
        data = {'objects': [{'uuid': u} for u in uuids]}
        url = self._get_url()
        return self.c.delete(url, data=data, query_params=query_params)


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


class KvmServers(ResourceBase):
    resource_name = 'servers'

    def open_vnc(self, uuid):
        """
        Server’s console (virtual keyboard, mouse, and display) is exposed to the user through the VNC protocol.
        The `open_vnc` call opens a VNC tunnel to the server. The returned object contains a `vnc_url` specifying the
        endpoint to which to connect the VNC client. The password for the VNC connection is specified in the
        `vnc_password` field on the server definition. Note that the tunnel is not closed until reboot, so if you prefer
        you can close is using the `close_vnc` action.
        VNC URL will be different each time you close/open the tunnel.

        :param uuid:
            UUID of the server.
        :return:
            Server definition including vnc_url and other details.
        """
        return self._action(uuid, 'open_vnc', data={})

    def close_vnc(self, uuid):
        """
        Closes a VNC tunnel to a server with specific UUID.

        :param uuid:
            UUID of the server.
        :return:
            Action status.
        """
        return self._action(uuid, 'close_vnc', data={})

# === n8n:BEGIN auto-generated resources ===

class Backupschedulers(ResourceBase):
    resource_name = 'backupschedulers'

    def delete_many(self, data, query_params=None):
        """
        Deletes multiple backup schedulers.

        :param data:
            List of backup scheduler UUIDs to delete, or a dictionary
            with an 'objects' key containing a list of dictionaries with 'uuid' keys.
            Example: ['uuid1', 'uuid2'] or {'objects': [{'uuid': 'uuid1'}, {'uuid': 'uuid2'}]}
        :type data: list or dict
        :param query_params:
            Dictionary of query parameters to append to the URL.
        :type query_params: dict
        :return:
            API response from the delete operation.
        """
        data = data or []
        request_body = {}

        if isinstance(data, (list, tuple)):
            # Convert list of UUID strings to list of dictionaries with 'uuid' key
            request_body['objects'] = [{'uuid': u} for u in data]
        elif isinstance(data, dict):
            if 'objects' in data:
                # If data is already in the expected {'objects': [...]} format, use it directly.
                request_body = data
            else:
                # If it's a single dictionary (e.g., {'uuid': '...'}), wrap it in 'objects'.
                request_body['objects'] = [data]
        else:
            raise TypeError(
                "Data for bulk delete must be a list of UUIDs or a dictionary "
                "with an 'objects' key containing a list of dictionaries."
            )

        url = self._get_url()
        # The base client's delete method is assumed to accept a 'data' keyword argument for bulk deletes with a body.
        return self.c.delete(url, data=request_body, query_params=query_params)

    def list_by_type(self, scheduler_type, query_params=None):
        """
        Gets the list of backup schedulers of a specific type.

        :param scheduler_type:
            The type of scheduler to filter by (e.g., 'backup' or 'snapshot').
        :type scheduler_type: basestring
        :param query_params:
            Dictionary of additional query parameters to append to the URL.
        :type query_params: dict
        :return:
            List of backup schedulers of the specified type.
        """
        query_params = query_params or {}
        query_params['type'] = scheduler_type
        return self.list(query_params=query_params)

    def list_detail_by_type(self, scheduler_type, query_params=None):
        """
        Gets the detailed list of backup schedulers of a specific type.

        :param scheduler_type:
            The type of scheduler to filter by (e.g., 'backup' or 'snapshot').
        :type scheduler_type: basestring
        :param query_params:
            Dictionary of additional query parameters to append to the URL.
        :type query_params: dict
        :return:
            Detailed list of backup schedulers of the specified type.
        """
        query_params = query_params or {}
        query_params['type'] = scheduler_type
        return self.list_detail(query_params=query_params)


class Capabilities(ResourceBase):
    resource_name = 'capabilities'


class FeedbackTicket(ResourceBase):
    resource_name = 'feedback_ticket'


class Gpus(ResourceBase):
    resource_name = 'gpus'


class Keypairs(ResourceBase):
    resource_name = 'keypairs'

    def create(self, name, public_key=None, private_key=None, algorithm_type=None, query_params=None):
        """
        Creates a new keypair or multiple keypairs.

        :param name:
            Name of the keypair.
        :type name: basestring
        :param public_key:
            The public key string. If not provided, a new keypair will be generated
            if private_key is also not provided.
        :type public_key: basestring
        :param private_key:
            The private key string. If not provided, a new keypair will be generated
            if public_key is also not provided.
        :type private_key: basestring
        :param algorithm_type:
            Algorithm type for autogenerated keys (e.g., "rsa", "ed25519"). Required
            if neither public_key nor private_key are provided.
        :type algorithm_type: basestring
        :param query_params:
            Dictionary of query parameters.
        :type query_params: dict
        :return:
            Created keypair definition.
        :rtype: dict or list
        """
        data = {
            'name': name,
        }
        if public_key:
            data['public_key'] = public_key
        if private_key:
            data['private_key'] = private_key
        
        if not public_key and not private_key:
            if not algorithm_type:
                raise ValueError("algorithm_type must be provided if neither public_key nor private_key are given for autogeneration.")
            data['algorithm_type'] = algorithm_type

        return super(Keypairs, self).create(data, query_params=query_params)


class NotificationTypes(ResourceBase):
    resource_name = 'notification_types'


class ObjectStorage(ResourceBase):
    resource_name = 'object-storage'


class Pubkeys(ResourceBase):
    resource_name = 'pubkeys'


class SupportTickets(ResourceBase):
    resource_name = 'support_tickets'


class Tunnels(ResourceBase):
    resource_name = 'tunnels'


class Usage(ResourceBase):
    resource_name = 'usage'


class VmwareDriveAsync(ResourceBase):
    resource_name = 'vmware_drive_async'


class VmwareDrives(ResourceBase):
    resource_name = 'vmware_drives'


class VmwareLibrary(ResourceBase):
    resource_name = 'vmware_library'


class VmwareServerAsync(ResourceBase):
    resource_name = 'vmware_server_async'


class VmwareServerFromTemplate(ResourceBase):
    resource_name = 'vmware_server_from_template'


class VmwareServers(ResourceBase):
    resource_name = 'vmware_servers'


class VrouterRequests(ResourceBase):
    resource_name = 'vrouter_requests'


class GroupedSubscription(ResourceBase):
    resource_name = 'groupedsubscriptions'

# === n8n:END auto-generated resources ===
