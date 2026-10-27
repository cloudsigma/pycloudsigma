from builtins import str, object
import socket
import os
import time
import requests

from past.builtins import basestring

from cloudsigma.generic import get_client, WebsocketClient, GenericClient


class ResourceBase(object):
    resource_name = None
    _client_class = None

    def __init__(self, *args, **kwargs):
        client_class = self._client_class or get_client()
        self.c = client_class(*args, **kwargs)

    def attach_response_hook(self, func):
        self.c.response_hook = func

    def detach_response_hook(self):
        self.c.response_hook = None

    def _get_url(self):
        assert self.resource_name, \
            'Descendant class must set the resource_name field'
        return '/%s/' % (self.resource_name,)

    def get(self, uuid=None, query_params=None, *, otp=None, limit=None,
            offset=None):
        """Read a resource, forwarding documented singleton query filters."""
        url = self._get_url()
        if uuid is not None:
            if isinstance(uuid, bytes):
                uuid_str = uuid.decode('utf-8')
            else:
                uuid_str = uuid
            url += uuid_str
        if limit is not None or offset is not None:
            query_params = dict(query_params or {})
            if limit is not None:
                query_params['limit'] = limit
            if offset is not None:
                query_params['offset'] = offset
        return self.c.get(url, query_params=query_params,
                          return_list=False, otp=otp)

    def get_schema(self):
        url = self._get_url() + 'schema'
        return self.c.get(url)

    def get_from_url(self, url):
        return self.c.get(url, return_list=False)

    def list(self, query_params=None, *, otp=None):
        url = self._get_url()
        _query_params = {
            'limit': 0,  # get all results, do not use pagination
        }
        if query_params:
            _query_params.update(query_params)
        return self.c.get(
            url, query_params=_query_params, return_list=True, otp=otp)

    def list_detail(self, query_params=None, *, otp=None):
        url = self._get_url() + 'detail/'
        _query_params = {
            'limit': 0,  # get all results, do not use pagination
        }
        if query_params:
            _query_params.update(query_params)
        return self.c.get(
            url, query_params=_query_params, return_list=True, otp=otp)

    def list_raw(self, query_params=None, *, otp=None):
        """Return one complete collection response; do not follow pages."""
        query = {'limit': 0}
        if query_params:
            query.update(query_params)
        return self.c.get_raw(self._get_url(), query_params=query, otp=otp)

    def list_detail_raw(self, query_params=None, *, otp=None):
        """Return one complete detail collection response; do not follow pages."""
        query = {'limit': 0}
        if query_params:
            query.update(query_params)
        return self.c.get_raw(
            self._get_url() + 'detail/', query_params=query, otp=otp)

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

    def create(self, data, query_params=None, image_path=None, *, otp=None,
               avoid=None):
        if image_path is not None or avoid is not None:
            raise TypeError('image_path and avoid are only supported by InitUpload')
        query_params = query_params or {}
        url = self._get_url()
        return self.c.post(
            url,
            self._pepare_data(data),
            return_list=False,
            query_params=query_params,
            otp=otp
        )

    def update(self, uuid=None, data=None, *, otp=None):
        if data is None:
            raise TypeError('update requires uuid and data')
        url = self._get_url() + uuid + '/'
        return self.c.put(url, data, return_list=False, otp=otp)

    def delete(self, uuid, query_params=None, *, otp=None):
        url = self._get_url() + uuid
        return self.c.delete(url, query_params=query_params, otp=otp)

    def _action(self, uuid, action, data=None, query_params=None, *, otp=None):
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
            return_list=False,
            otp=otp
        )


class Profile(ResourceBase):
    resource_name = 'profile'

    def get(self, uuid=None, query_params=None, *, otp=None, limit=None, offset=None):
        if uuid is not None:
            raise ValueError('profile does not accept a resource identifier')
        return self.c.get(self._get_url(), query_params=query_params,
                          return_list=False, otp=otp)

    def update(self, uuid=None, data=None, *, otp=None):
        if data is None:
            data = uuid
        return self.c.put(self._get_url(), data, return_list=False, otp=otp)


class GlobalContext(ResourceBase):
    resource_name = 'global_context'

    def get(self, uuid=None, query_params=None, *, otp=None, limit=None, offset=None):
        if uuid is not None:
            raise ValueError('global context does not accept a resource identifier')
        return self.c.get(self._get_url(), query_params=query_params,
                          return_list=False, otp=otp)

    def update(self, uuid=None, data=None, *, otp=None):
        if data is None:
            data = uuid
        return self.c.post(self._get_url(), data, return_list=False, otp=otp)


class NotificationContact(ResourceBase):
    resource_name = 'notification_contacts'


class NotificationPreference(ResourceBase):
    resource_name = 'notification_preferences'

    def update(self, uuid=None, data=None, *, otp=None):
        if data is None:
            data = uuid
        return self.c.put(self._get_url(), data, return_list=True, otp=otp)


class LibDrive(ResourceBase):
    resource_name = 'libdrives'

    def clone(self, uuid, data=None):
        """Clone a library drive into the account with an optional definition.

        A successful acknowledgment does not establish clone completion.
        """
        return self._action(uuid, 'clone', data if data is not None else {})


class Drive(ResourceBase):
    resource_name = 'drives'

    def delete_many(self, uuids):
        """Request ordinary drive collection deletion in one HTTP request.

        Accept a nonempty list/tuple of nonempty ASCII letters, digits, hyphens
        and underscores. This conservative SDK identifier policy is not public
        UUID grammar. Validate the entire batch before sending; preserve order
        and duplicates without changing the caller's sequence. HTTP 204 returns
        None and acknowledges deletion started, not completion or atomicity.
        No polling, retries, remote snapshots or snapshot deletion.
        https://docs.cloudsigma.com/en/latest/drives.html#deleting
        """
        if not isinstance(uuids, (list, tuple)) or not uuids:
            raise ValueError('drive identifiers must be a nonempty list or tuple')
        objects = []
        for uuid in uuids:
            if not isinstance(uuid, str) or not uuid or any(
                    char not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_'
                    for char in uuid):
                raise ValueError('invalid drive identifier')
            objects.append({'uuid': uuid})
        return self.c.delete(self._get_url(), data={'objects': objects})

    def set_scheduler(self, uuid, backup_policy_uuid):
        """Link an existing backup scheduler to a drive.

        Uses the documented backup_policy_uuid request field. The returned
        acknowledgment does not establish completion. Scheduler creation,
        unlinking and scheduling policy are not part of this method.
        """
        return self._action(uuid, 'set_scheduler',
                            {'backup_policy_uuid': backup_policy_uuid})

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
        with open(image_path, 'rb') as f:
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

    def create(self, data, query_params=None, image_path=None, *, otp=None,
               avoid=None):
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
        if avoid is None and query_params is not None and not isinstance(query_params, dict):
            avoid = query_params
            query_params = None
        query_params = dict(query_params or {})
        if not data.get('name'):
            data['name'] = os.path.split(image_path)[1]
        if not data.get('size'):
            data['size'] = os.path.getsize(image_path)
        if avoid:
            if isinstance(avoid, basestring):
                avoid = [avoid]
            query_params['avoid'] = ','.join(avoid)
        return super(InitUpload, self).create(
            data, query_params=query_params, otp=otp)


class Server(ResourceBase):
    resource_name = 'servers'

    def start(self, uuid, allocation_method=None, avoid=None):
        """Start with optional ordered, best-effort compute-host avoidance.

        ``avoid`` is a server UUID or sequence of server UUIDs, as documented
        at https://docs.cloudsigma.com/en/latest/availability_groups.html.
        Empty values omit the hint. Acknowledgment does not prove placement
        or completion. The existing allocation_method argument is unchanged.
        """
        data = {}
        if allocation_method:
            data = {'allocation_method': str(allocation_method)}
        query_params = {}
        if avoid:
            if isinstance(avoid, basestring):
                avoid = [avoid]
            query_params['avoid'] = ','.join(avoid)
        return self._action(uuid, 'start', data, query_params=query_params)

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

    def delete(self, uuid, query_params=None, *, otp=None, recurse=None):
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
        if recurse is None and query_params is not None and not isinstance(query_params, dict):
            recurse = query_params
            query_params = None
        query_params = dict(query_params or {})
        if recurse is not None:
            query_params.update(recurse=recurse)
        if not query_params:
            query_params = None

        return super(Server, self).delete(
            uuid, query_params=query_params, otp=otp)

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


class _AvailabilityGroups(ResourceBase):
    """Availability reads with explicit array shapes, not object pagination.

    Identifier policy: accept UTF-8 bytes or nonempty ASCII letters, digits,
    hyphen and underscore. This is route safety, not UUID/account validation.
    Existing inherited mutation methods are unchanged, not newly authorized.
    """
    @staticmethod
    def _identifier(value):
        if isinstance(value, bytes):
            value = value.decode('utf-8')
        if not isinstance(value, str) or not value or any(
                c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_'
                for c in value):
            raise ValueError('invalid availability identifier')
        return value

    @staticmethod
    def _shape(value, grouped):
        if type(value) is not list:
            raise ValueError('availability response must be an array')
        groups = value if grouped else [value]
        for group in groups:
            if type(group) is not list or any(type(item) is not str for item in group):
                raise ValueError('availability members must be string arrays')
        return value

    def get(self, uuid=None):
        url = self._get_url()
        if uuid is not None:
            url += self._identifier(uuid) + '/'
        return self._shape(self.c.get(url, return_list=False), uuid is None)

    def list(self, query_params=None):
        # Availability arrays have no documented pagination envelope.
        # Preserve explicit caller query mappings; do not invent limit=0.
        return self._shape(self.c.get(self._get_url(), query_params=query_params,
                                      return_list=True), True)


class ServersAvailabilityGroups(_AvailabilityGroups):
    resource_name = 'servers/availability_groups'


class DrivesAvailabilityGroups(_AvailabilityGroups):
    resource_name = 'drives/availability_groups'


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

    def auto_renew(self, uuid, data=None):
        """Enable automatic renewal for a documented subscription."""
        return self._action(uuid, 'auto_renew', data or {})


class GroupedSubscriptions(ResourceBase):
    """Read grouped subscriptions with list() or list_raw().

    The public API returns first subscriptions in extension chains, with
    descendants and the last subscription's end_time. Values are preserved
    using the existing JSON decoder; no chain calculation or schema validation
    is performed. Inherited methods do not imply other routes are supported.
    """
    resource_name = 'groupedsubscriptions'


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


class Capabilities(ResourceBase):
    resource_name = 'capabilities'


# Preserve the historical misspelling for callers that already use it.
Capabilites = Capabilities


class Accounts(ResourceBase):
    resource_name = 'accounts'

    def logout(self):
        """Request cookie-auth logout and return the empty HTTP 200 acknowledgment.

        Uses the caller's existing cookie session; does not acquire cookies,
        clear credentials or the caller's jar, or guarantee session invalidation.
        For a caller-managed session without constructor login, pass that session
        with login_method='none'. Basic/Bearer logout support is not implied.
        No retries or follow-up requests are added.
        https://docs.cloudsigma.com/en/latest/accounts.html
        """
        return self.c.post_empty_ack(
            self._get_url() + 'action/', {}, query_params={'do': 'logout'})

    def check_login(self):
        """Send the documented {} check and return its empty acknowledgment.

        Uses existing client authentication, without acquiring cookies, logging
        in, performing OTP, or guaranteeing a durable session. No retries or
        follow-up requests. https://docs.cloudsigma.com/en/latest/accounts.html
        """
        return self.c.post_empty_ack(
            self._get_url() + 'action/', {}, query_params={'do': 'check_login'})

    def authenticate_asynchronous(self):
        # data empty see TUR-1346
        return self._action(None, 'authenticate_asynchronous', data={})

    def create(self, email, promo_code=None):
        self.c._session = None
        self.c.login_method = GenericClient.LOGIN_METHOD_NONE
        return self._action(
            None, 'create', data={'email': email, 'promo': promo_code})


class Keypairs(ResourceBase):
    """Manage keypairs with the generic CRUD methods and optional OTP.

    Keypair responses may include private-key material. For public-only reads,
    use :class:`cloudsigma.public_key_read.PublicKeyRead` instead.
    """
    resource_name = 'keypairs'


class BackupScheduler(ResourceBase):
    """Manage documented backup-scheduler CRUD operations.

    The read-specialized :class:`cloudsigma.scheduler_reads.BackupSchedulerReads`
    remains available for complete response envelopes and collection deletion.
    """
    resource_name = 'backupschedulers'


class CurrentUsage(ResourceBase):
    resource_name = 'currentusage'


class Usage(ResourceBase):
    """Read usage records from the documented usage collection."""
    resource_name = 'usage'


class Snapshot(ResourceBase):
    resource_name = 'snapshots'

    def delete_many(self, uuids):
        """Request ordinary snapshot collection deletion in one HTTP request.

        Accept a nonempty list/tuple of nonempty ASCII letters, digits, hyphens
        and underscores. This conservative SDK identifier policy is not public
        UUID grammar. Validate the entire batch before sending; preserve order
        and duplicates without changing the caller's sequence. HTTP 204 returns
        None and acknowledges deletion started, not completion or atomicity.
        No polling, retries, remote snapshots or drive deletion.
        https://docs.cloudsigma.com/en/latest/snapshots.html#deleting
        """
        if not isinstance(uuids, (list, tuple)) or not uuids:
            raise ValueError('snapshot identifiers must be a nonempty list or tuple')
        objects = []
        for uuid in uuids:
            if not isinstance(uuid, str) or not uuid or any(
                    char not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_'
                    for char in uuid):
                raise ValueError('invalid snapshot identifier')
            objects.append({'uuid': uuid})
        return self.c.delete(self._get_url(), data={'objects': objects})

    def clone(self, uuid, data=None, avoid=None):
        """
        Clones a snapshot (creates a drive).

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

    def list_resource(self, uuid, resource_name, query_params=None):
        """Read one tagged-resource page with optional limit/offset parameters.

        Omitted parameters preserve the server default page. Pass limit=0
        explicitly to request all resources. No pages are followed implicitly;
        the existing list return shape is unchanged.
        """
        url = '{base}{tag_uuid}/{res_name}/'.format(
            base=self._get_url(),
            tag_uuid=uuid,
            res_name=resource_name
        )
        return self.c.get(url, query_params=query_params, return_list=True)

    def drives(self, uuid, query_params=None):
        return self.list_resource(uuid, 'drives', query_params=query_params)

    def servers(self, uuid, query_params=None):
        return self.list_resource(uuid, 'servers', query_params=query_params)

    def ips(self, uuid, query_params=None):
        return self.list_resource(uuid, 'ips', query_params=query_params)

    def vlans(self, uuid, query_params=None):
        return self.list_resource(uuid, 'vlans', query_params=query_params)


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
        ret = self.wait({"resource_type": resource_type}, timeout=timeout)[-1]
        return cls().get_from_url(ret['resource_uri'])

    def wait_obj_uri(self, resource_uri, cls, timeout=None):
        self.wait({"resource_uri": resource_uri}, timeout=timeout)
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
    """Accumulated daily usage via list/list_raw, with optional date filters.

    Pass date__gt/date__lt in query_params; dates and decimal amount strings
    are returned unchanged. Inherited mutations/detail routes are not a
    supported contract. Listing does not verify charges or follow pages.
    """
    resource_name = 'dailyburstusage'


class Locations(ResourceBase):
    resource_name = 'locations'


class RemoteSnapshot(ResourceBase):
    resource_name = 'remotesnapshots'

    def delete_many(self, uuids):
        """Request remote snapshot collection deletion in one HTTP request.

        Accept a nonempty list/tuple of nonempty ASCII letters, digits, hyphens
        and underscores. This conservative SDK identifier policy is not public
        UUID grammar. Validate the entire batch before sending; preserve order
        and duplicates without changing the caller's sequence. HTTP 204 returns
        None and acknowledges deletion started, not completion or atomicity.
        No added polling or retries; no ordinary snapshot or drive deletion.
        https://docs.cloudsigma.com/en/latest/remote_snapshots.html#deleting
        """
        if not isinstance(uuids, (list, tuple)) or not uuids:
            raise ValueError('remote snapshot identifiers must be a nonempty list or tuple')
        objects = []
        for uuid in uuids:
            if not isinstance(uuid, str) or not uuid or any(
                    char not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_'
                    for char in uuid):
                raise ValueError('invalid remote snapshot identifier')
            objects.append({'uuid': uuid})
        return self.c.delete(self._get_url(), data={'objects': objects})

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

    def create(self, data, query_params=None):
        """Send plain definitions as the documented singleton RDS request.

        Preserve explicit objects wrappers and list/tuple inputs through the
        legacy base implementation for compatibility; those alternative wire
        shapes are not established public contracts. Do not coerce fields or
        infer count bounds. Query forwarding and response unwrapping remain
        unchanged. Other resources retain ResourceBase.create behavior.
        https://docs.cloudsigma.com/en/latest/drives.html#creating-defining-rds-drive
        """
        if isinstance(data, dict) and 'objects' not in data:
            return self.c.post(self._get_url(), data, return_list=False,
                               query_params=query_params or {})
        return super(DriveUsers, self).create(data, query_params=query_params)

    def update_amount(self, drive_uuid, amount):
        """Update an RDS drive's user count with an amount-only definition.

        Accept a nonempty ASCII alphanumeric/hyphen/underscore identifier and
        a Python int (not bool). This is conservative SDK input policy, not
        public UUID grammar or provider count bounds. Zero and negative counts
        are forwarded without claiming server acceptance. Return the existing
        unwrapped update response; do not retry, poll or infer completion.
        The inherited arbitrary-definition update method is unchanged.
        https://docs.cloudsigma.com/en/latest/drives.html#editing-updating-rds-drive
        """
        if not isinstance(drive_uuid, str) or not drive_uuid or any(
                char not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_'
                for char in drive_uuid):
            raise ValueError('invalid drive identifier')
        if type(amount) is not int:
            raise ValueError('amount must be an integer')
        return self.update(drive_uuid, {'amount': amount})


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

    def enable_vpn(self, virtual_router_uuid, data=None):
        """Enable the documented VPN feature on a virtual router."""
        return self._action(virtual_router_uuid, 'enable_vpn', data or {})

    def disable_vpn(self, virtual_router_uuid, data=None):
        """Disable the documented VPN feature on a virtual router."""
        return self._action(virtual_router_uuid, 'disable_vpn', data or {})

    def get_keys(self, virtual_router_uuid, data=None):
        """Get keys associated with a documented virtual router."""
        return self._action(virtual_router_uuid, 'get_keys', data or {})

    def export_key(self, virtual_router_uuid, key_uuid, data=None):
        """Export one virtual-router key by its documented key identifier."""
        return self._action(
            virtual_router_uuid, 'export_key', data or {},
            query_params={'key_uuid': key_uuid})


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


class VpnTunnels(ResourceBase):
    """Manage documented virtual-router VPN tunnels."""
    resource_name = 'tunnels'
