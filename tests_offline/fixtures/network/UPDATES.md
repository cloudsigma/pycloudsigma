# Synthetic metadata update qualification

Public contracts inspected 2026-10-16:
- https://docs.cloudsigma.com/en/latest/networking.html — PUT /ips/{id}/
  and PUT /vlans/{id}/ show a direct JSON object containing meta and status 200.
- https://docs.cloudsigma.com/en/latest/meta.html — metadata applies to IPs
  and VLANs; keys limited to 32 characters, values should be strings; the whole
  meta is replaced, so old keys must be included unless intended for deletion.

`test_network_updates.py` adds three tests through real Requests preparation and
an in-memory adapter: six success requests (omitted metadata, empty metadata,
Unicode/empty-string/32-character-key populated metadata), twenty typed error or
redirect requests, two malformed responses and two timeout requests. All 30 are
synthetic. Existing tests already cover empty PUT metadata with a fake session;
these are not newly discovered routes. This adds previously unqualified prepared
request and failure facets, not a production fix. The SDK forwards the exact
payload without merging metadata or mutating caller input. Omission is tested as
wire preservation only, not a documented server no-op. Mock 200 does not prove
server replacement/deletion or writable-field validation. Populated IP server,
VLAN servers and IPv6 remain unresolved and are not invented or credited here.
