"""Bounded public-document refresh and reproducible response-field extraction.

Only public docs.cloudsigma.com/en/latest/*.html pages are fetched. Snapshots
retain normalized prose, operation declarations, response *shapes*, and public
schema definitions. HTTP headers and example scalar values are not retained.
No API credentials, SDK import, or provider operation is used.
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

BASE = "https://docs.cloudsigma.com/en/latest/"
INDEX = BASE + "index.html"
ROOT = Path(__file__).resolve().parent
MAX_PAGES = 100
MAX_PAGE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 30 * 1024 * 1024
EXCLUDED = {"genindex.html", "py-modindex.html", "search.html"}
METHODS = "GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS"
OPERATION = re.compile(r"^(" + METHODS + r")\s+(\S+)")
JSON_TYPES = {"null", "boolean", "integer", "number", "string", "array", "object"}


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def identifier(prefix, *parts):
    return prefix + "-" + digest(json.dumps(parts, separators=(",", ":")).encode())[:24]


def official_url(url):
    parsed = urlsplit(url)
    return (parsed.scheme == "https" and parsed.netloc == "docs.cloudsigma.com"
            and not parsed.query and not parsed.fragment
            and re.fullmatch(r"/en/latest/[a-zA-Z0-9_-]+\.html", parsed.path) is not None)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("documentation redirects require explicit review")


def fetch(url):
    if not official_url(url):
        raise ValueError("URL is outside the fixed official documentation scope")
    opener = build_opener(NoRedirect())
    with opener.open(Request(url, headers={"User-Agent": "Mozilla/5.0 pycloudsigma-contract/2"}), timeout=20) as response:
        body = response.read(MAX_PAGE_BYTES + 1)
    if len(body) > MAX_PAGE_BYTES:
        raise ValueError("documentation page exceeds the 2 MiB bound")
    return body


class Node:
    def __init__(self, tag="", attrs=None):
        self.tag, self.attrs, self.children = tag, dict(attrs or []), []

    def text(self):
        return "".join(child if isinstance(child, str) else child.text() for child in self.children)


class DocumentParser(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.stack = [self.root]
        self.links = set()

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag == "a" and "href" in node.attrs:
            self.links.add(node.attrs["href"])
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def clean(text):
    return " ".join(text.replace("\uf0c1", "").split())


def walk_nodes(node):
    yield node
    for child in node.children:
        if isinstance(child, Node):
            yield from walk_nodes(child)


def json_value_type(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object"


def response_shape(value, path="$", found=None):
    """Retain all observed field/type pairs, including heterogeneous arrays."""
    found = {} if found is None else found
    found.setdefault(path, set()).add(json_value_type(value))
    if isinstance(value, dict):
        for key, child in value.items():
            # JSON bracket notation avoids collisions with dots inside key names.
            response_shape(child, path + "[" + json.dumps(key, ensure_ascii=False) + "]", found)
    elif isinstance(value, list):
        for child in value:
            response_shape(child, path + "[*]", found)
    return [{"field_path": key, "observed_types": sorted(types)} for key, types in sorted(found.items())]


SENSITIVE_KEY_RE = re.compile(
    r"(?:password|passphrase|secret|token|authorization|credential|private[_-]?key|api[_-]?key|access[_-]?key)",
    re.I,
)


def sanitize_fixture(value, key=""):
    """Keep public example shape while removing credential-like scalar values."""
    if SENSITIVE_KEY_RE.search(key):
        return "<redacted>"
    if isinstance(value, dict):
        return {name: sanitize_fixture(child, name) for name, child in value.items()}
    if isinstance(value, list):
        return [sanitize_fixture(child, key) for child in value]
    return value


def api_path(path):
    if path.startswith("/api/"):
        return path
    if path.startswith("/"):
        return "/api/2.0" + path
    return path


def route_matches(operation, request):
    if operation["method"] != request["method"]:
        return False
    expected, actual = urlsplit(operation["path"]), urlsplit(api_path(request["path"]))
    expression = re.escape(expected.path)
    expression = re.sub(r"\\\{[^}]+\\\}", r"[^/]+", expression)
    if re.fullmatch(expression, actual.path) is None:
        return False
    # Query parameters besides the action may differ between examples.
    action = re.search(r"(?:^|&)do=([^&]+)", expected.query)
    actual_action = re.search(r"(?:^|&)do=([^&]+)", actual.query)
    return (action.group(1) if action else None) == (actual_action.group(1) if actual_action else None)


def parse_json_body(text):
    status = None
    text = text.strip()
    if text.startswith("HTTP/"):
        status_match = re.match(r"HTTP/\S+\s+(\d{3})", text)
        status = int(status_match.group(1)) if status_match else None
        parts = re.split(r"\r?\n\s*\r?\n", text, maxsplit=1)
        if len(parts) < 2:
            return None, status, "empty-body"
        text = parts[1].strip()
    if not text:
        return None, status, "empty-body"
    try:
        # Never repair invalid published JSON or accept duplicate keys silently.
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate JSON key")
                result[key] = value
            return result
        value = json.loads(text, object_pairs_hook=unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite JSON number")))
        return value, status, None
    except (ValueError, json.JSONDecodeError):
        return None, status, "invalid-or-non-json"


def normalize_document(url, html):
    parser = DocumentParser()
    parser.feed(html.decode("utf-8"))
    articles = [node for node in walk_nodes(parser.root) if node.attrs.get("itemprop") == "articleBody"]
    if len(articles) != 1:
        raise ValueError("expected exactly one Sphinx articleBody")
    blocks, section_ops = [], {}
    state = {"label": "", "request": None, "headings": []}

    def visit(node, sections=()):
        if node.tag == "section":
            sections += (node.attrs.get("id", ""),)
        anchor = sections[-1] if sections else ""
        if re.fullmatch("h[1-6]", node.tag):
            level = int(node.tag[1])
            state["headings"] = state["headings"][:level - 1] + [clean(node.text())]
            state["label"], state["request"] = "", None
            blocks.append({"kind": "heading", "anchor": anchor, "level": level, "text": clean(node.text())})
            return
        if node.tag == "dt":
            match = OPERATION.match(clean(node.text()))
            if match:
                operation = {"method": match.group(1), "path": api_path(match.group(2))}
                section_ops[sections] = operation
                blocks.append({"kind": "operation", "anchor": node.attrs.get("id", anchor), **operation})
                state["request"] = None
                return
        if node.tag == "p":
            text = clean(node.text())
            if text:
                blocks.append({"kind": "prose", "anchor": anchor, "text": text})
            if "example response" in text.lower():
                state["label"] = "response"
            elif "example request" in text.lower():
                state["label"] = "request"
            return
        if node.tag == "pre":
            raw = node.text()
            block = {"kind": "code", "anchor": anchor, "original_sha256": digest(raw.encode("utf-8"))}
            operation = next((section_ops[sections[:i]] for i in range(len(sections), -1, -1)
                              if sections[:i] in section_ops), None)
            request_match = OPERATION.match(raw.strip())
            if request_match and re.search(r"\sHTTP/\d", raw.splitlines()[0]):
                state["request"] = {"method": request_match.group(1), "path": request_match.group(2)}
                block.update(classification="request-example", method=request_match.group(1),
                             path=api_path(request_match.group(2)))
            else:
                schema_heading = bool(state["headings"] and "schema" in state["headings"][-1].lower())
                is_response = raw.lstrip().startswith("HTTP/") or state["label"] == "response"
                if schema_heading or is_response:
                    value, status, error = parse_json_body(raw)
                    block.update(classification="schema-definition" if schema_heading else "response-example",
                                 status_code=status)
                    if schema_heading:
                        block["direction"] = ("request" if "request" in state["headings"][-1].lower()
                                              else "response" if "response" in state["headings"][-1].lower()
                                              else "unbound")
                    elif operation and (state["request"] is None or route_matches(operation, state["request"])):
                        block["operation"] = operation
                    else:
                        block["binding_gap"] = "no-matching-operation-declaration"
                    if error:
                        block["parse_gap"] = error
                    elif schema_heading:
                        block["schema"] = value
                    else:
                        block["fixture_payload"] = sanitize_fixture(value)
                        block["shape"] = response_shape(block["fixture_payload"])
                else:
                    block["classification"] = "unclassified-code"
            blocks.append(block)
            return
        for child in node.children:
            if isinstance(child, Node):
                visit(child, sections)

    visit(articles[0])
    for block_index, block in enumerate(blocks):
        if (block.get("classification") == "response-example"
                and "fixture_payload" in block and block.get("operation")
                and not block.get("binding_gap")):
            block["fixture_id"] = identifier("fixture", url, block_index)
    links = []
    for href in parser.links:
        resolved = urlsplit(urljoin(url, href))._replace(fragment="").geturl()
        if official_url(resolved):
            links.append(resolved)
    return {"normalization_version": 1, "url": url, "html_sha256": digest(html),
            "links": sorted(set(links)), "blocks": blocks}


def schema_fields(schema, path="$", prefix=()):
    """Extract explicit schema facets without assigning schema to CRUD methods."""
    if not isinstance(schema, dict):
        return []
    result = []
    properties = schema.get("fields", schema.get("properties", {}))
    if not isinstance(properties, dict):
        return result
    required_names = schema.get("required") if isinstance(schema.get("required"), list) else []
    for key, definition in sorted(properties.items()):
        if not isinstance(definition, dict):
            continue
        child_path = path + "[" + json.dumps(key, ensure_ascii=False) + "]"
        facets = {name: definition[name] for name in (
            "type", "nullable", "required", "readonly", "readOnly", "writeOnly", "default", "enum", "choices",
            "minimum", "maximum", "minLength", "maxLength", "pattern", "blank", "unique", "help_text", "description")
                  if name in definition}
        if required_names and key in required_names and "required" not in facets:
            facets["required"] = True
        result.append({"field_path": child_path, "declared_facets": facets})
        result += schema_fields(definition, child_path)
        items = definition.get("items")
        if isinstance(items, dict):
            result += schema_fields(items, child_path + "[*]")
    return result


def build_contract(documents, bindings):
    operations, response_fields, schemas, gaps = {}, {}, {}, []
    for document in sorted(documents, key=lambda item: item["url"]):
        url = document["url"]
        for block_index, block in enumerate(document["blocks"]):
            source = {"url": url, "anchor": block.get("anchor", ""), "block": block_index}
            if block["kind"] == "operation":
                key = block["method"] + " " + block["path"]
                operation = operations.setdefault(key, {
                    "operation_id": key, "method": block["method"], "path": block["path"],
                    "sources": [], "response_examples": [], "field_contract": "incomplete",
                    "sdk_mapping": bindings.get(key, {"status": "unmapped", "symbols": [], "assertions": []}),
                })
                operation["sources"].append(source)
            if block.get("classification") == "schema-definition":
                fields = schema_fields(block.get("schema"))
                schema_id = identifier("schema", url, block.get("anchor", ""), block_index)
                schemas[schema_id] = {"schema_id": schema_id, "source": source,
                    "direction": block.get("direction", "unbound"), "operation_binding": "unreviewed",
                    "fields": fields}
                if not fields:
                    gaps.append({"kind": "schema-fields-unavailable", "source": source})
            if block.get("classification") == "response-example":
                operation = block.get("operation")
                if operation:
                    key = operation["method"] + " " + operation["path"]
                    if key not in operations:
                        raise ValueError("response binding precedes operation declaration")
                    fixture_payload = block.get("fixture_payload")
                    fixture_id = block.get("fixture_id")
                    fixture = None
                    if fixture_id is not None:
                        fixture_data = encoded(fixture_payload)
                        fixture = {
                            "fixture_id": fixture_id,
                            "path": "fixtures/response/" + fixture_id + ".json",
                            "sha256": digest(fixture_data),
                            "status_code": block.get("status_code"),
                            "source": source,
                        }
                    operations[key]["response_examples"].append(fixture or source)
                    for field in block.get("shape", []):
                        field_id = identifier("response", key, field["field_path"])
                        row = response_fields.setdefault(field_id, {
                            "field_id": field_id, "operation_id": key, "direction": "response",
                            "field_path": field["field_path"], "observed_types": [],
                            "required": None, "nullable": None, "writable": None,
                            "authority": "response-example", "sources": [], "fixture_ids": [],
                            "sdk_projection": "unverified", "assertion_evidence": [], "live_evidence": [],
                        })
                        row["observed_types"] = sorted(set(row["observed_types"]) | set(field["observed_types"]))
                        row["sources"].append(source)
                        if fixture_id is not None:
                            row["fixture_ids"].append(fixture_id)
                if block.get("binding_gap"):
                    gaps.append({"kind": block["binding_gap"], "source": source})
            if block.get("parse_gap") and block["parse_gap"] != "empty-body":
                gaps.append({"kind": block["parse_gap"], "source": source})
    # Some public method tables mention a collection route that has no
    # machine-readable operation block because the deployed provider returns
    # 404 by design.  Keep that route in the maintained inventory when its
    # binding carries explicit availability evidence.  This is deliberately
    # limited to provider-unavailable entries so a missing SDK mapping cannot
    # silently invent an operation.
    for key in sorted(set(bindings) - set(operations)):
        binding = bindings[key]
        if (not isinstance(binding, dict)
                or binding.get("status") != "provider-unavailable"
                or not isinstance(binding.get("availability"), dict)):
            continue
        availability = binding["availability"]
        try:
            method, path = key.split(" ", 1)
        except ValueError:
            continue
        source = availability.get("source")
        if (method not in METHODS.split("|") or not path
                or not isinstance(source, dict)
                or not isinstance(source.get("url"), str)
                or not isinstance(source.get("anchor"), str)
                or type(source.get("block")) is not int):
            continue
        sdk_mapping = {
            name: binding.get(name, []) if name != "status"
            else binding.get(name)
            for name in ("status", "symbols", "assertions")
        }
        operations[key] = {
            "availability_note": availability.get("note", ""),
            "disposition": availability.get("disposition"),
            "field_contract": availability.get("field_contract"),
            "method": method,
            "operation_id": key,
            "path": path,
            "response_examples": [],
            "sdk_mapping": sdk_mapping,
            "sources": [source],
        }
    for operation in operations.values():
        if not operation["response_examples"]:
            gaps.append({"kind": "response-example-unavailable", "operation_id": operation["operation_id"]})
    for key in sorted(set(bindings) - set(operations)):
        gaps.append({"kind": "sdk-binding-without-explicit-public-operation", "operation_id": key})
    rows = sorted(response_fields.values(), key=lambda row: (row["operation_id"], row["field_path"]))
    return {"schema_version": 2, "api_version": "2.0", "coverage_claim": "incomplete",
        "scope": "Public documentation declarations and response examples; schema-to-operation and request-field reconciliation remain open.",
        "operations": [operations[key] for key in sorted(operations)], "response_fields": rows,
        "schema_definitions": [schemas[key] for key in sorted(schemas)], "gaps": gaps,
        "summary": {"documents": len(documents), "declared_operations": len(operations),
                    "response_fields": len(rows), "schema_definitions": len(schemas),
                    "unbound_schema_fields": sum(len(item["fields"]) for item in schemas.values()),
                    "gaps": len(gaps), "field_assertions_verified": 0, "complete": False}}


def load_documents(root):
    manifest = json.loads((root / "sources.json").read_text(encoding="utf-8"))
    return [json.loads((root / source["file"]).read_text(encoding="utf-8")) for source in manifest["sources"]]


def rebuild(root):
    return build_contract(load_documents(root), json.loads((root / "bindings.json").read_text(encoding="utf-8")))


def refresh(output):
    if output.exists():
        raise ValueError("refresh output must be a new directory; review its diff before replacing tracked evidence")
    queue, documents, excluded, total_bytes = [INDEX], {}, set(), 0
    while queue:
        url = queue.pop(0)
        name = urlsplit(url).path.rsplit("/", 1)[-1]
        if name in EXCLUDED:
            excluded.add(url)
            continue
        if url in documents:
            continue
        if len(documents) >= MAX_PAGES:
            raise ValueError("documentation corpus exceeds 100 pages; review scope before raising the limit")
        html = fetch(url)
        total_bytes += len(html)
        if total_bytes > MAX_TOTAL_BYTES:
            raise ValueError("documentation corpus exceeds 30 MiB bound")
        documents[url] = normalize_document(url, html)
        queue += sorted(set(documents[url]["links"]) - set(documents) - set(queue))
    output.mkdir(parents=True)
    (output / "sources").mkdir()
    sources = []
    for url, document in sorted(documents.items()):
        name = urlsplit(url).path.rsplit("/", 1)[-1].replace(".html", ".json")
        relative = "sources/" + name
        data = encoded(document)
        (output / relative).write_bytes(data)
        for block in document["blocks"]:
            fixture_id = block.get("fixture_id")
            if fixture_id is not None:
                fixture_path = output / "fixtures" / "response" / (fixture_id + ".json")
                fixture_path.parent.mkdir(parents=True, exist_ok=True)
                fixture_path.write_bytes(encoded(block["fixture_payload"]))
        sources.append({"url": url, "file": relative, "sha256": digest(data), "html_sha256": document["html_sha256"]})
    manifest = {"schema_version": 1, "entry_point": INDEX, "fetched_at": datetime.now(timezone.utc).isoformat(),
                "discovery": "recursive same-directory public documentation links",
                "excluded_navigation": sorted(excluded), "sources": sources}
    (output / "sources.json").write_bytes(encoded(manifest))
    (output / "bindings.json").write_bytes((ROOT / "bindings.json").read_bytes())
    (output / "contract.json").write_bytes(encoded(rebuild(output)))
    return rebuild(output)["summary"]


def compare(previous, candidate):
    before, after = (json.loads((root / "contract.json").read_text()) for root in (previous, candidate))
    result = {"before": before["summary"], "after": after["summary"]}
    for collection, key in (("operations", "operation_id"), ("response_fields", "field_id")):
        old = {row[key]: row for row in before[collection]}
        new = {row[key]: row for row in after[collection]}
        result[collection] = {"added": sorted(new.keys() - old.keys()), "removed": sorted(old.keys() - new.keys()),
                              "changed": sorted(item for item in new.keys() & old.keys() if old[item] != new[item])}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    refresh_parser = sub.add_parser("refresh", help="Fetch bounded official docs into a new candidate directory")
    refresh_parser.add_argument("--output", required=True, type=Path)
    rebuild_parser = sub.add_parser("rebuild", help="Regenerate contract from retained normalized sources, offline")
    rebuild_parser.add_argument("--root", type=Path, default=ROOT)
    rebuild_parser.add_argument("--check", action="store_true")
    diff_parser = sub.add_parser("diff", help="Report operation/field identity changes, without response values")
    diff_parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "refresh":
            print(json.dumps(refresh(args.output), indent=2))
        elif args.command == "rebuild":
            data = encoded(rebuild(args.root))
            if args.check:
                if data != (args.root / "contract.json").read_bytes():
                    raise ValueError("contract.json is stale; regenerate from retained sources")
            else:
                (args.root / "contract.json").write_bytes(data)
            print("api-contract: reproducible extraction")
        else:
            print(json.dumps(compare(ROOT, args.candidate), indent=2))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("api-contract: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
