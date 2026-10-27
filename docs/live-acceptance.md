# Live acceptance

`ci/run_live_lifecycle.py` exercises create, read, update, read, delete and
confirmed absence through the installed `cloudsigma` SDK. It always targets
`https://next.cloudsigma.com/api/2.0/`. The default `tags` scenario creates one
unassociated tag; the optional `drive` scenario creates one empty 1 GiB disk,
waits for `unmounted`, renames it and removes it. Storage may incur small QA
account charges until deletion completes. Neither scenario attaches resources,
starts a VM or purchases a subscription.

## Configuration

Use the existing GitHub Actions secrets `CLOUDSIGMA_QA_USERNAME` and
`CLOUDSIGMA_QA_PASSWORD`. Inject them only into the acceptance step after building
and installing the exact commit's wheel. Required variables:

```text
CLOUDSIGMA_QA_ENDPOINT=https://next.cloudsigma.com/api/2.0/
CLOUDSIGMA_QA_ALLOW_MUTATIONS=true
CLOUDSIGMA_QA_SCENARIOS=tags,drive
```

Omit `CLOUDSIGMA_QA_SCENARIOS` to run only tags. Execute:

```sh
python -I -B ci/run_live_lifecycle.py
```

Run this only on trusted merged commits or manual dispatch of reviewed code.
Do not expose QA secrets to fork pull requests. Use a CI timeout that leaves
room for cleanup and avoid cancelling an active lifecycle job to replace it
with a newer commit. Pin action revisions and install dependencies from the
repository's existing hash locks.

## Ownership and cleanup

Every invocation assigns a new random `pycloudsigma-qa-<uuid>` name. An object
becomes eligible for cleanup only after the create acknowledgement contains a
canonical UUID and that exact name. Every update and delete is preceded by a
read that verifies identity and an expected invocation name. Tags must have no
associated resources; drives must have an explicitly empty `mounted_on` list.
There is no list-and-adopt or account-wide cleanup path.

POST, PUT and DELETE are issued at most once per scenario. Only GET is polled,
with at most eight attempts per phase and two seconds between attempts. Requests
use explicit connect/read timeouts. A successful delete is not acceptance until
a subsequent singleton read returns HTTP 404. Cleanup runs in `finally` after
an acknowledged creation even when a later assertion or request fails, and a
termination signal requests cleanup. Forced process termination or runner loss
can still prevent cleanup.

The runner emits JSON containing scenario/check names, its own resource UUID and
run name, safe error type/status, and cleanup outcome. It does not emit API
responses or exception messages. Before POST it flushes a receipt with the run
name; immediately after a valid acknowledgement it flushes the assigned UUID.
These breadcrumbs survive a later process loss in the CI log. If create has an
ambiguous outcome, it does not
retry or guess which object to delete; it reports `manual_review_required` and
the unique run name. If an owned object's cleanup fails, its acknowledged UUID
is also reported. Inspect that specific QA resource and the run evidence before
manual removal. Retain these JSON lines as CI evidence, especially on failure.

The old `src/testing/acceptance` discovery is not used: its tag fixture deletes
all account tags, and other historical fixtures create unrelated resources.

## Contract sources and coverage

- [Tags](https://docs.cloudsigma.com/en/latest/tags.html): create with `name`,
  edit using `name` and `resources`, and delete with HTTP 204 acknowledgement.
- [Drives](https://docs.cloudsigma.com/en/latest/drives.html): documented
  1 GiB disk creation payload, editable name, asynchronous creation and deletion.

These are two live lifecycle scenarios, not complete API certification. Expand
with separate scenarios tied to the maintained contract matrix, each declaring
its required capabilities, bounded resource cost, ownership evidence, success
assertions and cleanup. Unsupported location features stay explicit gaps.
