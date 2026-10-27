# API contract matrix and tunnel availability evidence

This repository now carries a versioned contract inventory at
`api_contract/contract.json`. The inventory separates operation coverage from
response-field coverage. Each operation records its method, path, SDK symbol,
status codes, authority, source, field-contract state, capability gate and
current disposition. Response fields are added only when a schema or other
authoritative source supports them; response examples and live observations do
not create writable request-field claims.

The validator is dependency-free and runs before SDK dependency installation in
the offline workflow. It rejects duplicate operation identities, missing
provenance, invalid authority/disposition values and malformed field rows.
Focused regression tests cover a valid matrix and duplicate detection. The
matrix is intentionally seeded with the read-only smoke operations first so
future API additions can be reviewed in small, evidence-backed changes.
The current offline guard is 298 tests, including the matrix and probe tests.

## Tunnel disposition

The public API reference documents `/api/2.0/tunnels/` and the internal NEXT
feature inventory lists the resource as enabled while marking its schema
unavailable:

- [Public VPN tunnel reference](https://docs.cloudsigma.com/en/latest/virtualrouters_vpn_tunnels.html)
- [NEXT API feature inventory](https://csigma.atlassian.net/wiki/spaces/DEV/pages/1810792449/NEXT+API+-+Feature+List+Acceptance+Criteria)
- [Virtual Router API catalog](https://csigma.atlassian.net/wiki/spaces/DEV/pages/2068742205/VRP2+-+Source+Virtual+Router+API+Catalog)

The QA smoke run against `next.cloudsigma.com` returned HTTP 404 for the
canonical tunnel collection, HTTP 301 for the slashless spelling, and HTTP 500
for the schema route. The SDK path therefore remains the documented path,
while the matrix records `provider-unavailable` and `schema-unavailable`. The
CI live workflow now runs a GET-only diagnostic over
the API root, capabilities, cloud status, canonical and slashless tunnel
routes, tunnel schema, and both virtual-router route spellings. It records
status, safe response shape, `Allow`, content type and request ID, then uploads
the JSON as a workflow artifact. Authentication and permission failures fail
the probe so credential regressions cannot be mistaken for provider route
absence.

The backend source currently available on Snowcrash registers the `/tunnels/`
resource but deliberately raises `PageNotFound` from its collection handler;
the latest reachable Turlo `main` ref is `9c14200c51da7f783c91e9bc7169f5352dcd00ae`.
This explains the observed collection 404 as an intentional provider behavior,
subject to deployment verification. It does not make the modern
`/api/v1/vpn/ipsec/tunnels` route interchangeable with the public v2 contract.
The next provider-side action is an API-owner decision on whether to remove,
enable, or replace the legacy collection route and to publish its authoritative
schema. Once that decision is available, add the route or a separate SDK
resource and populate the tunnel field rows in the same matrix change.

No mutating tunnel request is included in CI. The QA workflow runs on every
push to `master`, on manual dispatch and weekly, so route availability evidence
stays current without spending account credit or changing provider state.
