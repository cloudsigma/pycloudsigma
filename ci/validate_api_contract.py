"""Validate the versioned API operation/response-field contract matrix."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "api_contract" / "contract.json"

REQUIRED_OPERATION_KEYS = {
    "operation_id", "method", "path", "sdk_symbol", "direction",
    "status_codes", "authority", "source_ref", "field_contract",
    "response_fields", "disposition",
}
ALLOWED_DIRECTIONS = {"request", "response"}
ALLOWED_DISPOSITIONS = {
    "implemented", "partial", "generic-passthrough", "read-only",
    "unknown", "provider-unavailable", "blocked",
}
ALLOWED_AUTHORITIES = {
    "schema", "canonical-documentation", "approved-internal-contract",
    "sanitized-live-observation", "example-only",
}
FIELD_KEYS = {
    "field_path", "type", "required", "nullable", "mutability",
    "authority", "source_ref", "evidence", "disposition",
}


def validate(path=MATRIX):
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read valid JSON: {exc}"]

    errors = []
    if document.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if not isinstance(document.get("api_version"), str) or not document["api_version"]:
        errors.append("api_version must be a non-empty string")
    operations = document.get("operations")
    if not isinstance(operations, list) or not operations:
        return errors + ["operations must be a non-empty list"]
    seen = set()
    for index, operation in enumerate(operations):
        prefix = f"operations[{index}]"
        if not isinstance(operation, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing = REQUIRED_OPERATION_KEYS - set(operation)
        errors.extend(f"{prefix} missing {key}" for key in sorted(missing))
        key = tuple(operation.get(name) for name in ("operation_id", "method", "path", "direction"))
        if key in seen:
            errors.append(f"{prefix} duplicates operation identity {key!r}")
        seen.add(key)
        if not isinstance(operation.get("operation_id"), str) or not operation.get("operation_id"):
            errors.append(f"{prefix}.operation_id must be non-empty")
        if operation.get("method") not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
            errors.append(f"{prefix}.method is invalid")
        if not isinstance(operation.get("path"), str) or not operation.get("path", "").startswith("/api/"):
            errors.append(f"{prefix}.path must be an /api/ path")
        if operation.get("direction") not in ALLOWED_DIRECTIONS:
            errors.append(f"{prefix}.direction is invalid")
        if operation.get("authority") not in ALLOWED_AUTHORITIES:
            errors.append(f"{prefix}.authority is invalid")
        if not isinstance(operation.get("status_codes"), list) or not operation["status_codes"]:
            errors.append(f"{prefix}.status_codes must be a non-empty list")
        if operation.get("disposition") not in ALLOWED_DISPOSITIONS:
            errors.append(f"{prefix}.disposition is invalid")
        fields = operation.get("response_fields")
        if not isinstance(fields, list):
            errors.append(f"{prefix}.response_fields must be a list")
            continue
        field_seen = set()
        for field_index, field in enumerate(fields):
            field_prefix = f"{prefix}.response_fields[{field_index}]"
            if not isinstance(field, dict):
                errors.append(f"{field_prefix} must be an object")
                continue
            missing_fields = FIELD_KEYS - set(field)
            errors.extend(f"{field_prefix} missing {key}" for key in sorted(missing_fields))
            field_path = field.get("field_path")
            if not isinstance(field_path, str) or not field_path:
                errors.append(f"{field_prefix}.field_path must be non-empty")
            elif field_path in field_seen:
                errors.append(f"{field_prefix} duplicates field_path {field_path!r}")
            field_seen.add(field_path)
            if not isinstance(field.get("required"), bool) or not isinstance(field.get("nullable"), bool):
                errors.append(f"{field_prefix}.required and nullable must be booleans")
            if field.get("authority") not in ALLOWED_AUTHORITIES:
                errors.append(f"{field_prefix}.authority is invalid")
            if field.get("disposition") not in ALLOWED_DISPOSITIONS:
                errors.append(f"{field_prefix}.disposition is invalid")
    return errors


def main():
    errors = validate()
    if errors:
        for error in errors:
            print(f"api-contract: {error}", file=sys.stderr)
        return 1
    print(f"api-contract: valid ({MATRIX})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
