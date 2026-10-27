# Maintained API response-field inventory

This directory contains a reproducible inventory of the public CloudSigma API
reference. It records API operation declarations, response field observations,
and public resource schema definitions in versioned JSON. It provides a source
of reviewable changes when the API documentation changes.

The current snapshot contains 62 public documentation pages, 181 explicit
method/path declarations plus one explicitly classified provider-unavailable
route, 2,587 response field observations, and 430 schema field definitions
across 31 schema blocks. There are 131 explicit extraction or
contract gaps. These are discovery counts, not percentages of API coverage.
No field-level SDK assertion is claimed by this inventory.

## Files and authority

- `sources.json`: entry point, discovery scope, retrieval time, normalized and
  original HTML SHA256 fingerprints, and excluded navigation pages.
- `sources/*.json`: normalized documentation. These retain headings, prose,
  explicit HTTP operation declarations, response shapes, and public schema
 definitions. HTTP headers are omitted. Sanitized response-example payloads are
 retained as fixture files so offline transport and projection tests can replay
 the documented response shape without network access.
- `contract.json`: generated operation and field matrix, schema definitions,
  unresolved gaps, and summary counts.
- `bindings.json`: reviewed SDK symbols mapped to exact method/path declarations.
  An unmapped operation is not evidence that the SDK cannot perform it. The
  mapping remains open until its public interface and assertions are traced.
  A binding may also carry explicit availability evidence for a documented
  route whose provider behavior prevents an operation block from being
  extracted. Such a row is retained as `provider-unavailable` and does not
  claim a response schema.
- `update.py`: dependency-free discovery, normalization, extraction and diff tool.

Operation IDs preserve the documented HTTP method, path parameters and query
suffix. They do not silently merge differently spelled routes or parameter
names. Response field IDs derive from that operation ID and a JSON bracket path;
`$["objects"][*]["uuid"]` identifies every object's UUID without assuming an
array length. Root, envelope, container and array-element observations are also
included, so the row count is not a count of business fields.

Published response examples establish field presence and observed JSON types
only. A missing, null, false, empty or omitted value is not enough to establish
requiredness, nullability, default, writable state, or lifecycle behavior.
Those contract properties stay `null` (unknown). Fixture scalar values are
retained only where they help a deterministic roundtrip test; keys that look
credential-like are replaced with `<redacted>`, and HTTP Authorization headers
are never copied into this repository. Fixture IDs and SHA256 hashes are exposed
on each operation's `response_examples` entry and on each response-field row's
`fixture_ids` list.

Resource-wide `fields`/`properties` schemas preserve their explicit facets,
including nested fields, nullable/required/readonly flags, choices and defaults.
They stay separate from operation-specific response rows with
`operation_binding: unreviewed`. A resource schema may describe write rules or
an internal resource definition; it does not automatically describe every GET,
POST or action response. Request examples are never promoted to response fields.

An authoritative schema or explicit normative documentation takes precedence
when a row is reviewed. A sanitized live observation supplies dated provider
evidence; it does not redefine the public contract. SDK symbol presence,
projection behavior, field assertions and live evidence are distinct columns.
Generic dictionary transport is not a field-level assertion.

## Offline CI checks

```sh
python -I -B ci/validate_api_contract.py
python -I -B api_contract/update.py rebuild --check
```

The validator rejects malformed JSON types, duplicate operation/field/schema
identities, stale source and fixture hashes, missing discovered pages, unsafe
source paths, unredacted sensitive fixture values, and unsupported completeness
or assertion claims. It then rebuilds the matrix from retained snapshots and
reviewed bindings and compares the result exactly. It needs no SDK dependency,
account or network access. The sole non-`incomplete` operation state,
`schema-unavailable`, is accepted only when the row is explicitly marked
`provider-unavailable`.

The extractor does not repair invalid published JSON. It records a gap at the
source page, section and block. Response examples with no matching operation
declaration also remain gaps. This avoids assigning an action response to a
nearby collection operation merely because it appears later in the page.

## Refresh after API updates

Run a bounded refresh into a **new** directory, then review its diff:

```sh
python -I -B api_contract/update.py refresh --output /tmp/pycloudsigma-contract-candidate
python -I -B api_contract/update.py diff /tmp/pycloudsigma-contract-candidate
```

Refresh follows only `https://docs.cloudsigma.com/en/latest/*.html` links starting
from `index.html`. It refuses redirects, credentials, query strings, other
hosts, paths outside this directory, existing output directories, pages over
2 MiB, more than 100 pages, or more than 30 MiB in total. Fetches use a 20-second
request timeout. Failed fetches abort instead of silently shrinking the corpus.
Only Sphinx navigation utilities (`genindex`, `py-modindex`, `search`) are
excluded; other product references remain visible for scope adjudication.

Review added/removed operation IDs and field/type changes. Reconcile applicable
API source or schema changes, add SDK mappings and meaningful regressions, then
copy the candidate `sources/`, `sources.json`, `bindings.json` and `contract.json`
into this directory in the same PR. Preserve prior snapshots through Git history.
Run the offline validator, fixture-backed transport tests and installed SDK
qualification workflow before merge.
A public-documentation refresh does not require or consume QA account credentials.

## Remaining qualification work

The 181 explicit declarations plus one provider-unavailable route are a
documentation-derived starting inventory, not an
independently confirmed production endpoint denominator. Prose-only operations,
request fields, async semantics, permission conditions and newer endpoint
families still need reconciliation. Schema binding and field assertions must
be reviewed before making field-completeness claims. Existing live QA validates
only its selected operations and account/location; empty collections cannot
exercise individual object fields.

The tunnel page has explicit singleton GET/PUT/DELETE and collection POST
operations, but no explicit collection GET declaration, no populated examples
and an empty rendered schema section. The earlier SDK collection read is
represented as a synthesized `schema-unavailable` operation row with an
explicit `provider-unavailable` disposition, source block and QA evidence.
That row records the gap; it is not a field or support claim.
