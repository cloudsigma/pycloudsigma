import copy
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_api_contract", ROOT / "ci" / "validate_api_contract.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
UPDATE = MODULE.UPDATE


def article(body):
    return ('<html><div itemprop="articleBody">' + body + '</div></html>').encode()


def normalized(body):
    return UPDATE.normalize_document(UPDATE.BASE + "example.html", article(body))


class ApiContractTests(unittest.TestCase):
    def test_checked_in_matrix_is_valid_and_reproducible(self):
        self.assertEqual(MODULE.validate(), [])
        self.assertEqual(json.loads(MODULE.MATRIX.read_text()), UPDATE.rebuild(MODULE.MATRIX.parent))

    def test_malformed_json_types_fail_without_tracebacks(self):
        original = json.loads(MODULE.MATRIX.read_text())
        examples = [None, [], "matrix", 4]
        for name, value in (("operations", {}), ("operations", [None]),
                            ("response_fields", [None]), ("schema_definitions", [False]),
                            ("summary", [])):
            candidate = copy.deepcopy(original)
            candidate[name] = value
            examples.append(candidate)
        for column in ("operation_id", "method", "path"):
            candidate = copy.deepcopy(original)
            candidate["operations"][0][column] = ["unhashable"]
            examples.append(candidate)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "contract.json"
            for payload in examples:
                with self.subTest(payload_type=type(payload).__name__):
                    path.write_text(json.dumps(payload))
                    self.assertTrue(MODULE.validate(path))

    def test_source_hash_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "contract"
            shutil.copytree(MODULE.MATRIX.parent, root)
            manifest = json.loads((root / "sources.json").read_text())
            source = root / manifest["sources"][0]["file"]
            source.write_bytes(source.read_bytes() + b"\n")
            self.assertTrue(any("stale source hash" in error for error in MODULE.validate(root / "contract.json")))

    def test_duplicate_ids_and_unsupported_complete_claims_are_rejected(self):
        original = json.loads(MODULE.MATRIX.read_text())
        candidates = []
        for name in ("operations", "response_fields", "schema_definitions"):
            value = copy.deepcopy(original)
            value[name].append(copy.deepcopy(value[name][0]))
            candidates.append((value, "duplicates stable ID"))
        value = copy.deepcopy(original)
        value["coverage_claim"] = "complete"
        candidates.append((value, "unsupported complete claim"))
        value = copy.deepcopy(original)
        value["response_fields"][0]["required"] = True
        candidates.append((value, "cannot establish required"))
        value = copy.deepcopy(original)
        value["response_fields"][0]["sdk_projection"] = "verified"
        candidates.append((value, "unsupported field verification claim"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "contract.json"
            for payload, expected in candidates:
                with self.subTest(expected=expected):
                    path.write_text(json.dumps(payload))
                    self.assertTrue(any(expected in error for error in MODULE.validate(path)))

    def test_provider_unavailable_route_keeps_schema_contract_explicit(self):
        """The known tunnel collection 404 is a qualified availability gap."""
        original = json.loads(MODULE.MATRIX.read_text())
        tunnel = next(row for row in original["operations"]
                      if row["operation_id"] == "GET /api/2.0/tunnels/")
        self.assertEqual(tunnel["field_contract"], "schema-unavailable")
        self.assertEqual(tunnel["disposition"], "provider-unavailable")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "contract.json"
            invalid = copy.deepcopy(original)
            invalid_tunnel = next(row for row in invalid["operations"]
                                  if row["operation_id"] == tunnel["operation_id"])
            invalid_tunnel["disposition"] = "documented"
            path.write_text(json.dumps(invalid))
            errors = MODULE.validate(path)
            self.assertTrue(any("schema-unavailable field contract requires"
                                in error for error in errors))

    def test_manual_matrix_drift_requires_regeneration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "contract"
            shutil.copytree(MODULE.MATRIX.parent, root)
            path = root / "contract.json"
            payload = json.loads(path.read_text())
            payload["response_fields"][0]["observed_types"] = ["string", "boolean"]
            path.write_text(json.dumps(payload))
            self.assertTrue(any("matrix is stale or altered" in error for error in MODULE.validate(path)))

    def test_response_examples_keep_nullability_and_requiredness_unknown(self):
        document = normalized('''<section id="read"><h2>Read</h2>
          <dl><dt id="get-resource">GET /resources/</dt></dl>
          <p>Example response:</p><pre>HTTP/1.1 200 OK
Content-Type: application/json

{"objects":[{"name":null,"a.b":"private-value"},{"name":"second","count":2}]}</pre></section>''')
        contract = UPDATE.build_contract([document], {})
        fields = {item["field_path"]: item for item in contract["response_fields"]}
        name = fields['$["objects"][*]["name"]']
        self.assertEqual(name["observed_types"], ["null", "string"])
        self.assertIsNone(name["required"])
        self.assertIsNone(name["nullable"])
        self.assertIsNone(name["writable"])
        self.assertIn('$["objects"][*]["a.b"]', fields)
        self.assertIn("private-value", json.dumps(document))

    def test_operation_examples_expose_sanitized_fixture_ids_and_payloads(self):
        document = normalized('''<section id="read"><h2>Read</h2>
          <dl><dt>GET /resources/</dt></dl><p>Example response:</p>
          <pre>HTTP/1.1 200 OK
Content-Type: application/json

{"objects":[{"uuid":"resource-1","unknown_provider_field":"retained",
"password":"must-not-leak"}]}</pre></section>''')
        contract = UPDATE.build_contract([document], {})
        example = contract["operations"][0]["response_examples"][0]
        self.assertRegex(example["fixture_id"], r"^fixture-[0-9a-f]{24}$")
        self.assertEqual(example["status_code"], 200)
        fixture = document["blocks"][3]["fixture_payload"]
        self.assertEqual(fixture["objects"][0]["password"], "<redacted>")
        self.assertEqual(fixture["objects"][0]["unknown_provider_field"], "retained")
        field_ids = {row["field_path"]: row for row in contract["response_fields"]}
        unknown = field_ids['$["objects"][*]["unknown_provider_field"]']
        self.assertEqual(unknown["fixture_ids"], [example["fixture_id"]])
        self.assertEqual(unknown["assertion_evidence"], [])

    def test_request_fields_never_become_response_fields(self):
        document = normalized('''<section id="create"><h2>Create</h2>
          <dl><dt>POST /resources/</dt></dl><p>Example request:</p>
          <pre>POST /api/2.0/resources/ HTTP/1.1
Authorization: Basic secret

{"password":"secret"}</pre><p>Example response:</p>
          <pre>HTTP/1.1 201 CREATED
Content-Type: application/json

{"uuid":"id"}</pre></section>''')
        contract = UPDATE.build_contract([document], {})
        self.assertEqual([row["field_path"] for row in contract["response_fields"]], ["$", '$["uuid"]'])
        self.assertNotIn("secret", json.dumps(document))

    def test_invalid_published_json_is_a_gap_without_silent_repair(self):
        document = normalized('''<section id="read"><h2>Read</h2>
          <dl><dt>GET /resources/</dt></dl><p>Example response:</p>
          <pre>HTTP/1.1 200 OK
Content-Type: application/json

{"name":"value",}</pre></section>''')
        contract = UPDATE.build_contract([document], {})
        self.assertEqual(contract["response_fields"], [])
        self.assertTrue(any(gap["kind"] == "invalid-or-non-json" for gap in contract["gaps"]))
        value, _, error = UPDATE.parse_json_body('{"same":1,"same":2}')
        self.assertIsNone(value)
        self.assertEqual(error, "invalid-or-non-json")

    def test_scope_inheritance_and_request_mismatch_do_not_misbind_fields(self):
        document = normalized('''<section id="create"><h2>Create</h2>
          <dl><dt>POST /resources/</dt></dl><section id="child"><h3>Example</h3>
          <pre>POST /api/2.0/resources/ HTTP/1.1

{}</pre><pre>HTTP/1.1 201 CREATED

{"uuid":"id"}</pre></section></section>
          <section id="other"><h2>Other</h2><pre>HTTP/1.1 200 OK

{"unbound":1}</pre></section>
          <section id="calculator"><h2>Calculator</h2><dl><dt>POST /calculator/</dt></dl>
          <pre>POST /api/2.0/calculator/1/action/?do=extend HTTP/1.1

{}</pre><pre>HTTP/1.1 200 OK

{"different_action":1}</pre></section>''')
        contract = UPDATE.build_contract([document], {})
        self.assertEqual({row["field_path"] for row in contract["response_fields"]}, {"$", '$["uuid"]'})
        self.assertEqual(sum(gap["kind"] == "no-matching-operation-declaration" for gap in contract["gaps"]), 2)
        self.assertTrue(UPDATE.route_matches({"method": "GET", "path": "/api/2.0/resources/{uuid}/"},
                                           {"method": "GET", "path": "/api/2.0/resources/abc/?limit=1"}))

    def test_resource_schema_remains_unbound_with_declared_facets(self):
        document = normalized('''<section id="schema"><h2>Schema</h2>
          <pre>{"fields":{"uuid":{"type":"string","readonly":true,"required":true},
          "nested":{"type":"related","fields":{"enabled":{"type":"boolean","nullable":false}}}}}</pre></section>''')
        contract = UPDATE.build_contract([document], {})
        self.assertEqual(contract["operations"], [])
        self.assertEqual(contract["response_fields"], [])
        schema = contract["schema_definitions"][0]
        self.assertEqual(schema["direction"], "unbound")
        self.assertEqual(schema["operation_binding"], "unreviewed")
        by_path = {field["field_path"]: field["declared_facets"] for field in schema["fields"]}
        self.assertEqual(by_path['$["uuid"]']["required"], True)
        self.assertEqual(by_path['$["nested"]["enabled"]']["nullable"], False)

    def test_refresh_scope_and_existing_destination_are_guarded(self):
        for url in ("http://docs.cloudsigma.com/en/latest/index.html",
                    "https://evil.test/en/latest/index.html",
                    "https://docs.cloudsigma.com/en/latest/../secrets.html",
                    "https://docs.cloudsigma.com/en/latest/index.html?token=secret",
                    "https://user:secret@docs.cloudsigma.com/en/latest/index.html"):
            with self.subTest(url=url):
                self.assertFalse(UPDATE.official_url(url))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "new directory"):
                UPDATE.refresh(Path(directory))


if __name__ == "__main__":
    unittest.main()
