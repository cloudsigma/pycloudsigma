"""Check matrix identities, evidence custody and reproducible offline extraction."""
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "api_contract" / "contract.json"
SPEC = importlib.util.spec_from_file_location("api_contract_update", ROOT / "api_contract" / "update.py")
UPDATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UPDATE)
SHA = re.compile(r"[a-f0-9]{64}")
SOURCE_FILE = re.compile(r"sources/[a-zA-Z0-9_-]+\.json")


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON object key")
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite JSON number")))


def validate(path=MATRIX):
    path = Path(path)
    root = path.parent
    errors = []
    try:
        document = read_json(path)
    except (OSError, ValueError, UnicodeError) as exc:
        return [f"cannot read valid matrix JSON: {exc}"]
    if not isinstance(document, dict):
        return ["matrix must be a JSON object"]
    if document.get("schema_version") != 2 or type(document.get("schema_version")) is not int:
        errors.append("schema_version must be integer 2")
    if document.get("api_version") != "2.0":
        errors.append("api_version must be 2.0")
    if document.get("coverage_claim") != "incomplete":
        errors.append("unsupported complete claim: extracted observations are not field qualification")
    summary = document.get("summary")
    if not isinstance(summary, dict) or summary.get("complete") is not False:
        errors.append("summary must explicitly record complete=false")
    elif summary.get("field_assertions_verified") != 0:
        errors.append("unsupported assertion claim: this corpus has no field qualification evidence")

    def rows(name, id_key):
        entries = document.get(name)
        if not isinstance(entries, list):
            errors.append(f"{name} must be a list")
            return []
        seen, valid = set(), []
        for i, row in enumerate(entries):
            if not isinstance(row, dict):
                errors.append(f"{name}[{i}] must be an object")
                continue
            identity = row.get(id_key)
            if not isinstance(identity, str) or not identity:
                errors.append(f"{name}[{i}].{id_key} must be a non-empty string")
                continue
            if identity in seen:
                errors.append(f"{name} duplicates stable ID {identity!r}")
            seen.add(identity)
            valid.append(row)
        return valid

    operations = rows("operations", "operation_id")
    fields = rows("response_fields", "field_id")
    schemas = rows("schema_definitions", "schema_id")
    if not operations:
        errors.append("operations must not be empty")
    operation_ids = {row["operation_id"] for row in operations}
    for operation in operations:
        method, api_path = operation.get("method"), operation.get("path")
        if (not isinstance(method, str) or method not in UPDATE.METHODS.split("|")
                or not isinstance(api_path, str) or not api_path):
            errors.append("operation has an invalid method or path")
        elif operation["operation_id"] != method + " " + api_path:
            errors.append("operation stable ID differs from method/path")
        field_contract = operation.get("field_contract")
        if field_contract == "schema-unavailable":
            # A documented route can be represented in the matrix even when
            # the provider intentionally returns 404.  That disposition is a
            # provider availability result, not a claim that its response
            # fields are qualified.  Keep this exception explicit and narrow
            # so other unsupported completeness claims remain rejected.
            if operation.get("disposition") != "provider-unavailable":
                errors.append(
                    "schema-unavailable field contract requires "
                    "provider-unavailable disposition")
        elif field_contract != "incomplete":
            errors.append("unsupported complete field contract")
        if not isinstance(operation.get("sources"), list) or not operation["sources"]:
            errors.append("operation sources must be a non-empty list")
        mapping = operation.get("sdk_mapping")
        if not isinstance(mapping, dict) or not isinstance(mapping.get("symbols"), list):
            errors.append("sdk_mapping must keep source symbols distinct from assertions")
    for field in fields:
        operation_id, field_path = field.get("operation_id"), field.get("field_path")
        if not isinstance(operation_id, str) or operation_id not in operation_ids:
            errors.append("response field refers to an unknown operation")
        if not isinstance(field_path, str) or not field_path.startswith("$"):
            errors.append("response field_path must start with $")
        elif isinstance(operation_id, str) and field["field_id"] != UPDATE.identifier("response", operation_id, field_path):
            errors.append("response field stable ID differs from operation/path")
        types = field.get("observed_types")
        if (not isinstance(types, list) or not types or any(
                not isinstance(item, str) or item not in UPDATE.JSON_TYPES for item in types)):
            errors.append("observed_types must be a non-empty list of JSON type names")
        for name in ("required", "nullable", "writable"):
            if name not in field or field[name] is not None:
                errors.append(f"response example cannot establish {name}; use null for unknown")
        if field.get("authority") != "response-example" or field.get("direction") != "response":
            errors.append("response example authority/direction must be preserved")
        if (field.get("sdk_projection") != "unverified" or field.get("assertion_evidence") != []
                or field.get("live_evidence") != []):
            errors.append("unsupported field verification claim")
    for schema in schemas:
        if schema.get("operation_binding") != "unreviewed":
            errors.append("schema must remain unbound until operation-specific review")
        if not isinstance(schema.get("fields"), list):
            errors.append("schema fields must be a list")

    try:
        manifest = read_json(root / "sources.json")
        bindings = read_json(root / "bindings.json")
    except (OSError, ValueError, UnicodeError) as exc:
        return errors + [f"cannot read contract evidence: {exc}"]
    if not isinstance(bindings, dict):
        errors.append("bindings must be an object")
    if not isinstance(manifest, dict):
        return errors + ["sources manifest must be an object"]
    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        return errors + ["sources must be a non-empty list"]
    documents, urls, files, discovered = [], set(), set(), set()
    fixture_ids = set()
    for i, source in enumerate(sources):
        if not isinstance(source, dict):
            errors.append(f"sources[{i}] must be an object")
            continue
        url, relative, expected = source.get("url"), source.get("file"), source.get("sha256")
        if not isinstance(url, str) or not UPDATE.official_url(url):
            errors.append(f"sources[{i}] URL is outside the fixed official docs scope")
            continue
        if url in urls:
            errors.append(f"duplicate source URL {url}")
        urls.add(url)
        if not isinstance(relative, str) or SOURCE_FILE.fullmatch(relative) is None:
            errors.append(f"sources[{i}] file must be a local sources/name.json")
            continue
        if relative in files:
            errors.append(f"duplicate source file {relative}")
        files.add(relative)
        if not isinstance(expected, str) or SHA.fullmatch(expected) is None:
            errors.append(f"sources[{i}] sha256 is malformed")
            continue
        raw_hash = source.get("html_sha256")
        if not isinstance(raw_hash, str) or SHA.fullmatch(raw_hash) is None:
            errors.append(f"sources[{i}] original HTML hash is malformed")
            continue
        try:
            data = (root / relative).read_bytes()
            snapshot = read_json(root / relative)
        except (OSError, ValueError, UnicodeError) as exc:
            errors.append(f"cannot read {relative}: {exc}")
            continue
        if hashlib.sha256(data).hexdigest() != expected:
            errors.append(f"stale source hash for {relative}")
        if not isinstance(snapshot, dict):
            errors.append(f"{relative} must be an object")
            continue
        if snapshot.get("url") != url or snapshot.get("html_sha256") != source.get("html_sha256"):
            errors.append(f"source provenance mismatch for {relative}")
        if not isinstance(snapshot.get("blocks"), list) or not isinstance(snapshot.get("links"), list):
            errors.append(f"{relative} blocks/links must be lists")
            continue
        for link in snapshot["links"]:
            if not isinstance(link, str) or not UPDATE.official_url(link):
                errors.append(f"{relative} has invalid discovery URL")
            else:
                discovered.add(link)
        if any(not isinstance(block, dict) for block in snapshot["blocks"]):
            errors.append(f"{relative} has a malformed block")
            continue
        for block in snapshot["blocks"]:
            fixture_id = block.get("fixture_id")
            if fixture_id is None:
                continue
            if not isinstance(fixture_id, str) or not fixture_id.startswith("fixture-"):
                errors.append(f"{relative} has malformed fixture_id")
                continue
            fixture_ids.add(fixture_id)
            fixture_path = root / "fixtures" / "response" / (fixture_id + ".json")
            try:
                fixture_data = fixture_path.read_bytes()
                fixture_payload = read_json(fixture_path)
            except (OSError, ValueError, UnicodeError) as exc:
                errors.append(f"cannot read fixture {fixture_id}: {exc}")
                continue
            if hashlib.sha256(fixture_data).hexdigest() != hashlib.sha256(
                    json.dumps(block.get("fixture_payload"), indent=2, sort_keys=True,
                               ensure_ascii=False).encode("utf-8") + b"\n").hexdigest():
                errors.append(f"fixture payload mismatch for {fixture_id}")
            def sensitive_values_are_redacted(value, key=""):
                if UPDATE.SENSITIVE_KEY_RE.search(key):
                    return value == "<redacted>"
                if isinstance(value, dict):
                    return all(sensitive_values_are_redacted(child, name)
                               for name, child in value.items())
                if isinstance(value, list):
                    return all(sensitive_values_are_redacted(child, key) for child in value)
                return True
            if not sensitive_values_are_redacted(fixture_payload):
                errors.append(f"fixture {fixture_id} contains an unsanitized sensitive value")
        documents.append(snapshot)
    excluded = manifest.get("excluded_navigation")
    if not isinstance(excluded, list) or any(not isinstance(item, str) for item in excluded):
        errors.append("excluded_navigation must be a list of URLs")
        excluded = []
    if any(item.rsplit("/", 1)[-1] not in UPDATE.EXCLUDED for item in excluded):
        errors.append("only navigation utilities may be excluded from corpus discovery")
    if UPDATE.INDEX not in urls:
        errors.append("documentation index is missing from source manifest")
    if discovered - urls - set(excluded):
        errors.append("discovered documentation pages missing from source manifest")
    if errors:
        return errors
    fixture_root = root / "fixtures" / "response"
    existing_fixtures = {path.stem for path in fixture_root.glob("*.json")} if fixture_root.exists() else set()
    if existing_fixtures != fixture_ids:
        errors.append("fixture directory does not match retained fixture IDs")
    contract_fixture_refs = {}
    for operation in document.get("operations", []):
        for example in operation.get("response_examples", []):
            if not isinstance(example, dict) or "fixture_id" not in example:
                continue
            fixture_id = example["fixture_id"]
            contract_fixture_refs[fixture_id] = example
            fixture_path = root / example.get("path", "")
            try:
                fixture_data = fixture_path.read_bytes()
            except OSError:
                errors.append(f"contract references missing fixture {fixture_id}")
                continue
            if hashlib.sha256(fixture_data).hexdigest() != example.get("sha256"):
                errors.append(f"contract fixture hash mismatch for {fixture_id}")
    if set(contract_fixture_refs) != fixture_ids:
        errors.append("contract response examples do not reference every fixture")
    if errors:
        return errors
    try:
        expected_document = UPDATE.build_contract(documents, bindings)
    except (ValueError, KeyError, TypeError, AttributeError, IndexError) as exc:
        return [f"malformed retained evidence prevents extraction: {type(exc).__name__}"]
    if document != expected_document:
        errors.append("matrix is stale or altered: rebuild from retained evidence and reviewed bindings")
    return errors


def main():
    errors = validate()
    if errors:
        for error in errors[:25]:
            print(f"api-contract: {error}", file=sys.stderr)
        if len(errors) > 25:
            print(f"api-contract: {len(errors) - 25} further errors", file=sys.stderr)
        return 1
    summary = read_json(MATRIX)["summary"]
    print("api-contract: valid reproducible inventory " + json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
