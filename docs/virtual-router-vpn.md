# Modern virtual-router VPN access

The current customer-facing API represents a router at
`/api/2.0/virtual_routers/{uuid}/`. IPsec tunnels are returned inside
`configuration.vpn.tunnels`; the SDK helper is
`cloudsigma.virtual_router.VirtualRouter.list_tunnels(uuid)`. The helper
validates only that the documented containers are objects and returns each
tunnel mapping unchanged, including provider additions and write-only/native
fields.

Scoped tunnel changes use the router action endpoint:

```python
router.add_ipsec_tunnel(router_uuid, payload)
router.edit_ipsec_tunnel(router_uuid, payload)
router.remove_ipsec_tunnel(router_uuid, {"name": "office-a"})
```

The action payload is passed through unchanged. The API validates names,
selectors, identities, secrets and native security choices. A successful
action acknowledges acceptance; callers must read router configuration and
status to establish convergence. `ipsec_capabilities(uuid)` and
`ipsec_status(uuid)` expose the documented read-only routes.

The historical `/api/2.0/tunnels/` collection is registered by the provider
but its collection GET currently returns 404. It is therefore not used for
discovery by this SDK. `/api/v1/vpn/ipsec/*` belongs to an internal
Manager/OPNsense facade documented separately and is not a public CloudSigma
customer route.

Sources: [Turlo public API reference](https://csigma.atlassian.net/wiki/spaces/DEVOPS/pages/2191360247),
[VPN service reference](https://csigma.atlassian.net/wiki/spaces/DEVOPS/pages/2190868648),
[engineering handbook](https://csigma.atlassian.net/wiki/spaces/DEVOPS/pages/2121203714).
