"""Offline IP/VLAN GET regressions through real Requests preparation and SDK decode.

Public examples are in fixtures/network; generated collection/extension variants
are synthetic. Legacy envelope loss and 401 fields are characterization, not
normative API policy: intentional fixes should supersede these expectations.
No audit hooks, installed-path assumptions or evidence writes belong here.
"""
import copy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

# Select an empty portable config before the first SDK import. Restore the caller's
# environment; the configured singleton remains as in the other offline tests.
with patch.dict(os.environ, {"CLOUDSIGMA_CONFIG": os.devnull}):
    from cloudsigma import errors, resource
import requests
from requests.adapters import BaseAdapter

FIXTURES = Path(__file__).parent / "fixtures" / "network"
KINDS = ("ip", "vlan")
VARIANTS = ("summary", "detail", "single")


def fixture(kind, variant):
    return json.loads((FIXTURES / (kind + "_" + variant + ".json")).read_text())


class FixtureAdapter(BaseAdapter):
    """Fail closed at the adapter boundary; never delegate to an HTTP adapter."""

    def __init__(self, case, url, payload, status, exception):
        self.case = case
        self.url = url
        self.payload = payload
        self.status = status
        self.exception = exception
        self.calls = 0
        self.response = None

    def send(self, request, **kwargs):
        self.calls += 1
        case = self.case
        case.assertEqual(request.url, self.url)
        case.assertEqual(request.method, "GET")
        case.assertIsNone(request.body)
        case.assertEqual(kwargs["timeout"], 15)
        case.assertIs(kwargs["verify"], True)
        case.assertEqual(kwargs["proxies"], {})
        case.assertEqual(request.headers["Authorization"],
                         "Basic Zml4dHVyZTpzeW50aGV0aWM=")
        case.assertEqual(request.headers["Content-Type"], "application/json")
        if self.exception is not None:
            raise self.exception
        response = requests.Response()
        response.status_code = self.status
        response.request = request
        response.url = request.url
        response.headers["X-REQUEST-ID"] = "fixture-request-id"
        response.headers["Content-Type"] = "application/json"
        if 300 <= self.status < 400:
            response.headers["Location"] = "https://elsewhere.invalid/forbidden/"
        response._content = (self.payload if isinstance(self.payload, bytes)
                             else json.dumps(self.payload).encode("utf-8"))
        self.response = response
        return response

    def close(self):
        pass


class NetworkReadTests(unittest.TestCase):
    def assert_json_exact(self, actual, expected):
        """Also reject bool/int and int/float substitutions hidden by ==."""
        self.assertIs(type(actual), type(expected))
        if isinstance(expected, dict):
            self.assertEqual(actual.keys(), expected.keys())
            for key in expected:
                self.assert_json_exact(actual[key], expected[key])
        elif isinstance(expected, list):
            self.assertEqual(len(actual), len(expected))
            for item, wanted in zip(actual, expected):
                self.assert_json_exact(item, wanted)
        else:
            self.assertEqual(actual, expected)

    def read(self, kind, variant, payload, params=None, status=200,
             exception=None, wrong_url=False):
        cls = resource.IP if kind == "ip" else resource.VLAN
        obj = cls(api_endpoint="https://fixture.invalid/api/2.0/",
                  username="fixture", password="synthetic")
        uid = fixture(kind, "single")["uuid"]
        route = "ips/" if kind == "ip" else "vlans/"
        route += "detail/" if variant == "detail" else uid + "/" if variant == "single" else ""
        query = ("" if variant == "single" else "?limit=0" if params is None
                 else "?limit=2&offset=3&name=a+b%26c")
        url = "https://fixture.invalid/api/2.0/" + route + query
        adapter = FixtureAdapter(self, url + ("WRONG" if wrong_url else ""),
                                 payload, status, exception)
        before = copy.deepcopy(params)
        with requests.Session() as session:
            session.trust_env = False
            session.mount("https://", adapter)
            session.mount("http://", adapter)
            obj.c._session = session
            try:
                if variant == "single":
                    result = obj.get(uid)
                elif variant == "detail":
                    result = obj.list_detail(params)
                else:
                    result = obj.list(params)
                self.assertIs(obj.c.resp, adapter.response)
                return result
            finally:
                self.assert_json_exact(params, before)
                self.assertEqual(adapter.calls, 1)

    def test_public_examples_and_queries(self):
        for kind in KINDS:
            for variant in VARIANTS:
                queries = [None] if variant == "single" else [
                    None, {"limit": 2, "offset": 3, "name": "a b&c"}]
                for params in queries:
                    with self.subTest(kind=kind, variant=variant, params=params):
                        payload = fixture(kind, variant)
                        expected = payload if variant == "single" else payload["objects"]
                        result = self.read(kind, variant, payload, params)
                        self.assert_json_exact(result, expected)
                        target = result if variant == "single" else result[0]
                        target["owner"]["uuid"] = "mutated"
                        self.assertEqual(target["owner"]["uuid"], "mutated")
                        original = payload if variant == "single" else payload["objects"][0]
                        self.assertNotEqual(original["owner"]["uuid"], "mutated")

    def test_synthetic_empty_and_two_object_collections(self):
        for kind in KINDS:
            for variant in ("summary", "detail"):
                for count in (0, 2):
                    with self.subTest(kind=kind, variant=variant, count=count):
                        payload = fixture(kind, variant)
                        first = payload["objects"][0]
                        second = copy.deepcopy(first)
                        second["uuid"] = ("192.0.2.42" if kind == "ip" else
                                          "00000000-0000-4000-8000-000000000002")
                        route = "ips" if kind == "ip" else "vlans"
                        second["resource_uri"] = "/api/2.0/" + route + "/" + second["uuid"] + "/"
                        second["owner"]["uuid"] = "00000000-0000-4000-8000-000000000003"
                        second["owner"]["resource_uri"] = "/api/2.0/user/" + second["owner"]["uuid"] + "/"
                        payload["objects"] = [] if count == 0 else [first, second]
                        payload["meta"]["total_count"] = count
                        result = self.read(kind, variant, payload)
                        self.assert_json_exact(result, payload["objects"])
                        if count:
                            self.assertNotEqual(result[0]["uuid"], result[1]["uuid"])
                            result[0]["owner"]["uuid"] = "mutated-first"
                            self.assertEqual(result[0]["owner"]["uuid"], "mutated-first")
                            self.assertEqual(result[1]["owner"]["uuid"], second["owner"]["uuid"])
                            self.assertNotEqual(first["owner"]["uuid"], "mutated-first")

    def test_synthetic_scalars_and_legacy_envelope_loss(self):
        extension = {"ordered": [3, 1, 2], "null": None,
                     "large": 9007199254740993, "zero": 0,
                     "flag": False, "text": "", "fraction": 1.25}
        for kind in KINDS:
            for variant in VARIANTS:
                with self.subTest(kind=kind, variant=variant):
                    payload = fixture(kind, variant)
                    target = payload if variant == "single" else payload["objects"][0]
                    target["synthetic_extension"] = copy.deepcopy(extension)
                    if variant != "single":
                        payload["meta"].update(offset=3, total_count=99)
                        payload["envelope_extension"] = "not returned"
                    result = self.read(kind, variant, payload)
                    self.assert_json_exact(result, payload if variant == "single" else payload["objects"])
                    decoded = result if variant == "single" else result[0]
                    self.assert_json_exact(decoded["synthetic_extension"], extension)

    def test_legacy_http_error_fields(self):
        for kind in KINDS:
            for variant in VARIANTS:
                for status, cls in ((401, errors.AuthError), (403, errors.PermissionError),
                                    (404, errors.ClientError), (500, errors.ServerError)):
                    with self.subTest(kind=kind, variant=variant, status=status):
                        with self.assertRaises(cls) as caught:
                            self.read(kind, variant, b"fixture error", status=status)
                        error = caught.exception
                        self.assertIs(type(error.status_code), int)
                        self.assertEqual(error.status_code, status)
                        # Known legacy 401 defect, not a desired new error policy.
                        self.assertEqual(error.message, "fixture-request-id" if status == 401 else "fixture error")
                        self.assertEqual(error.request_id, "" if status == 401 else "fixture-request-id")

    def test_malformed_json_and_transport_identity(self):
        for kind in KINDS:
            for variant in VARIANTS:
                with self.subTest(kind=kind, variant=variant):
                    with self.assertRaises(requests.exceptions.JSONDecodeError):
                        self.read(kind, variant, b"{bad")
                    sentinel = requests.exceptions.ConnectionError("synthetic transport")
                    with self.assertRaises(requests.exceptions.ConnectionError) as caught:
                        self.read(kind, variant, {}, exception=sentinel)
                    self.assertIs(caught.exception, sentinel)

    def test_redirect_refusal(self):
        for kind in KINDS:
            for variant in VARIANTS:
                for status in (301, 302, 303, 307, 308):
                    with self.subTest(kind=kind, variant=variant, status=status):
                        with self.assertRaises(errors.ApiClientError) as caught:
                            self.read(kind, variant, b"", status=status)
                        self.assertEqual(caught.exception.message, "redirect refused")
                        self.assertEqual(caught.exception.status_code, status)
                        self.assertEqual(caught.exception.request_id, "fixture-request-id")

    def test_legacy_permissive_wrong_envelope(self):
        for kind in KINDS:
            for variant in VARIANTS:
                with self.subTest(kind=kind, variant=variant):
                    payload = {"unexpected": ["not objects"]}
                    result = self.read(kind, variant, payload)
                    self.assert_json_exact(result, payload)
                    expected = fixture(kind, variant)
                    with self.assertRaises(AssertionError):
                        self.assert_json_exact(result, expected if variant == "single" else expected["objects"])

    def test_oracle_negative_controls(self):
        with self.assertRaises(AssertionError):
            self.read("ip", "single", fixture("ip", "single"), wrong_url=True)
        for actual, expected in ((True, 1), (1.0, 1), (False, 0),
                                 (9007199254740992, 9007199254740993),
                                 ([1, 2], [2, 1]), ({}, {"null": None})):
            with self.subTest(actual=actual, expected=expected):
                with self.assertRaises(AssertionError):
                    self.assert_json_exact(actual, expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
