"""Customer-facing modern virtual-router helpers.

The legacy :class:`cloudsigma.resource.VirtualRouters` resource targets the
historical ``/virtualrouters/`` endpoint.  Current Turlo documentation uses
``/virtual_routers/`` and stores IPsec tunnels inside a router configuration.
This module keeps that route distinct and leaves the response object
unchanged; callers can use :meth:`ResourceBase.get` when they need fields not
yet modelled by the SDK.
"""

from __future__ import absolute_import

from cloudsigma.resource import ResourceBase


class VirtualRouter(ResourceBase):
    """Read and operate on the documented ``virtual_routers`` resource.

    ``get`` and the inherited collection methods return the provider response
    using the SDK's normal envelope unwrapping.  Scoped action bodies are
    passed through unchanged so additions to the provider contract do not get
    silently discarded by the SDK.
    """

    resource_name = 'virtual_routers'

    @staticmethod
    def _tunnels_from_router(router):
        """Validate and return ``configuration.vpn.tunnels`` from a GET.

        This deliberately validates only the documented container shape.  The
        provider owns tunnel field evolution (including write-only and native
        fields), so each tunnel mapping is returned verbatim.
        """
        if not isinstance(router, dict):
            raise ValueError('virtual router response must be an object')
        configuration = router.get('configuration')
        if not isinstance(configuration, dict):
            raise ValueError('virtual router response lacks configuration')
        vpn = configuration.get('vpn')
        if not isinstance(vpn, dict):
            raise ValueError('virtual router configuration lacks vpn')
        tunnels = vpn.get('tunnels')
        if not isinstance(tunnels, list):
            raise ValueError('virtual router vpn.tunnels must be a list')
        if any(not isinstance(tunnel, dict) for tunnel in tunnels):
            raise ValueError('virtual router vpn.tunnels entries must be objects')
        return tunnels

    def list_tunnels(self, virtual_router_uuid, *, otp=None):
        """Read a router and return its configured IPsec tunnel mappings.

        The provider has no supported public tunnel collection GET in the
        legacy ``/tunnels/`` resource.  Tunnel discovery therefore belongs to
        the modern router representation and is a single read of
        ``/virtual_routers/{uuid}/``.
        """
        return self._tunnels_from_router(self.get(virtual_router_uuid, otp=otp))

    def add_ipsec_tunnel(self, virtual_router_uuid, data, *, otp=None):
        """Submit the documented ``add_ipsec_tunnel`` scoped action."""
        return self._action(virtual_router_uuid, 'add_ipsec_tunnel', data,
                            otp=otp)

    def edit_ipsec_tunnel(self, virtual_router_uuid, data, *, otp=None):
        """Submit the documented secret-preserving edit action."""
        return self._action(virtual_router_uuid, 'edit_ipsec_tunnel', data,
                            otp=otp)

    def remove_ipsec_tunnel(self, virtual_router_uuid, data, *, otp=None):
        """Submit the documented ``remove_ipsec_tunnel`` scoped action."""
        return self._action(virtual_router_uuid, 'remove_ipsec_tunnel', data,
                            otp=otp)

    def ipsec_capabilities(self, virtual_router_uuid, *, otp=None):
        """Read appliance-derived native IPsec capabilities."""
        url = self._get_url() + virtual_router_uuid + '/ipsec/capabilities/'
        return self.c.get(url, return_list=False, otp=otp)

    def ipsec_status(self, virtual_router_uuid, *, otp=None):
        """Read the router's current IPsec status counters."""
        url = self._get_url() + virtual_router_uuid + '/ipsec/status/'
        return self.c.get(url, return_list=False, otp=otp)
