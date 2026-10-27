# API contract matrix

`contract.json` is the checked-in contract inventory for the SDK. It deliberately
separates operation coverage from response-field coverage. An operation may be
implemented while its field contract remains `pending-field-extraction` or
`schema-unavailable`.

Each operation row is keyed by `operation_id`, HTTP method, path and direction.
`response_fields` contains one row per nested response field when an authoritative
schema is available. Fields are not inferred as writable request fields merely
because they appear in a response or an example.

Authority is ordered by strength: sanctioned schema, canonical public
documentation, approved internal contract, sanitized live observation, then
example-only evidence. A live observation can confirm provider behavior for a
given environment and date; it cannot redefine the public contract.

Run the validator locally:

```text
python -I -B ci/validate_api_contract.py
```

The validator is intentionally dependency-free so pull requests can check the
matrix before installing the SDK. Extend the matrix in the same pull request as
new SDK operations or response fixtures, and keep unresolved fields explicitly
marked instead of claiming field-level completeness.
