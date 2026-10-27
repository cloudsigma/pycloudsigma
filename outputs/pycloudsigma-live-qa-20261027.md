# pycloudsigma live QA acceptance — 2026-10-27

## Account and endpoint

- Endpoint: `https://next.cloudsigma.com/api/2.0/`
- Account source: recovered QA credential file on `snowcrash`; credentials were passed through environment variables and were not logged or committed.
- Repository secret names: `CLOUDSIGMA_QA_USERNAME`, `CLOUDSIGMA_QA_PASSWORD`
- Test mode: HTTP Basic authentication; read-only requests only.

## Direct smoke result

The updated installed SDK was exercised directly against the QA endpoint:

| Check | Result |
|---|---|
| `Profile.get` | passed |
| `Locations.list(limit=1)` | passed |
| `Capabilities.list(limit=1)` | passed |
| `Usage.list(limit=1)` | passed |
| `VirtualRouters.list(limit=1)` | passed |
| `VpnTunnels.list(limit=1)` | skipped: provider returned HTTP 404 |

No create, update, delete, action, upload, or websocket operation was issued. The 404 indicates that the documented `/tunnels/` route is not deployed or exposed in this QA location; it is surfaced in the smoke output rather than treated as a successful endpoint.

## Automated workflow

`.github/workflows/live-qa.yml` runs the same read-only smoke runner on every push to `master`, which covers merged pull requests, and supports manual dispatch. Secrets are injected only at runtime. The workflow builds and installs the exact SDK artifact before running `ci/run_live_smoke.py`.

The runner emits only check names, result state, response shape, elapsed time, and typed error metadata. It never prints credentials or response bodies.

The post-merge run [40541180791](https://github.com/cloudsigma/pycloudsigma/actions/runs/40541180791) passed on merge commit `6d8e78ee41972bd28c2420b380acc8cea7c1f9ee`: 5 checks passed, 1 documented provider 404 was skipped, and 0 checks failed.

## Local validation

- Installed-artifact offline suite: **292 tests passed**.
- `python3 -m py_compile ci/run_live_smoke.py tests_offline/test_live_smoke_runner.py` passed.
- `git diff --check` passed.
