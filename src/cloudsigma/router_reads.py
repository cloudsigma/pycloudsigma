"""Explicit public router reads; existing generic resource behavior is unchanged."""
import copy
import json
from decimal import Decimal
from cloudsigma.generic import GenericClient
from cloudsigma.resource import ResourceBase, _AvailabilityGroups


class _RawReadClient(GenericClient):
    def _login_session(self):
        # Login decoding is the inherited auth contract, not a router response.
        self._decoding_login = True
        try:
            return super()._login_session()
        finally:
            self._decoding_login = False

    def _process_response(self, resp, return_list=False):
        if getattr(self, '_decoding_login', False) or resp.status_code != 200:
            return super()._process_response(resp, return_list)
        value = json.loads(resp.text, parse_float=Decimal)
        if type(value) is not dict:
            raise ValueError('router response must be an object')
        return copy.deepcopy(value)


class VirtualRouterReads(ResourceBase):
    """One-page raw object reads. Decimal values avoid binary float rounding.

    Existing VirtualRouters methods remain unchanged. No automatic traversal,
    mutation, field writability or placement/ownership guarantee is provided.
    """
    resource_name = 'virtualrouters'

    _client_class = _RawReadClient

    def _page(self, detail=False, query_params=None, *, otp=None):
        query = {} if query_params is None else dict(query_params)
        if any(k not in ('limit', 'offset') for k in query):
            raise ValueError('unsupported router page query')
        if any(type(v) is not int or v < 0 for v in query.values()):
            raise ValueError('page values must be nonnegative integers')
        value = self.c.get(self._get_url() + ('detail/' if detail else ''),
                           query_params=query, return_list=True, otp=otp)
        if type(value) is not dict:
            raise ValueError('router page must be an object')
        objects = value.get('objects')
        if objects is not None and (type(objects) is not list or
                                    any(type(x) is not dict for x in objects)):
            raise ValueError('router objects must be object arrays')
        return value

    def list(self, query_params=None, *, otp=None):
        return self._page(query_params=query_params, otp=otp)

    def list_detail(self, query_params=None, *, otp=None):
        return self._page(detail=True, query_params=query_params, otp=otp)

    def get(self, uuid=None, query_params=None, *, otp=None, limit=None, offset=None):
        identifier = _AvailabilityGroups._identifier(uuid)
        return self.c.get(self._get_url() + identifier + '/',
                          query_params=query_params, otp=otp)


class VirtualRouterPolicyRead(ResourceBase):
    """GET /vrfwpolicies/{id}/ only; not the existing fwpolicies resource.

    Only get is qualified. Inherited methods do not establish public contracts.
    """
    resource_name = 'vrfwpolicies'

    _client_class = _RawReadClient

    def get(self, uuid=None, query_params=None, *, otp=None, limit=None, offset=None):
        identifier = _AvailabilityGroups._identifier(uuid)
        return self.c.get(self._get_url() + identifier + '/',
                          query_params=query_params, otp=otp)
