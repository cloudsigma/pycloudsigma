# Network GET fixtures

The six JSON files reproduce public CloudSigma API networking examples for IP
and VLAN summary, detail and singleton GET responses. Source:
https://docs.cloudsigma.com/en/latest/networking.html (IP and VLAN sections).
Public example snapshot SHA-256:
`b479ba9ce61326d2c21040c974ccffd5798c9ae45e9b45106025dd200238956f`.
They are public examples, not account captures or credentials. The singleton
VLAN response UUID differs from the documentation's request example; tests use
the response UUID as a synthetic request identity, not server validation.

`test_network_reads.py` explicitly synthesizes empty/two-object collections,
second object identifiers/owners and unknown scalar extensions. These are not
additional documented schema examples or writable-field authorization. Empty
permissions/grantees/tags/servers do not qualify populated nested schemas.

Tests use a fail-closed Requests adapter and synthetic Basic credentials.
They characterize current collection-envelope loss, permissive unknown envelopes
and legacy 401 message/request-ID behavior; intentional SDK fixes should update
these tests rather than preserve defects. The session has `trust_env=False`;
this does not qualify production default environment/netrc behavior.

Run with the repository's existing installed-package offline runner:
`python -I -B ci/run_offline.py` (Python 3.10–3.12). Focused discovery:
`python -m unittest discover -s tests_offline -p test_network_reads.py -v`.
The runner owns socket isolation; this portable module installs no audit hooks.
