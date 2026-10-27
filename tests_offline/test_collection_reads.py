"""Complete one-page envelopes; synthetic extensions are not API schema claims."""
import copy
from unittest import TestCase
from unittest.mock import patch
import requests
from cloudsigma import resource, errors
from test_network_reads import FixtureAdapter, fixture
import test_network_reads


class CollectionReadTests(TestCase):
    assert_json_exact = test_network_reads.NetworkReadTests.assert_json_exact

    def read(self, kind, detail, payload, params=None, status=200, exception=None,
             legacy=False):
        cls = resource.IP if kind == 'ip' else resource.VLAN
        route = ('ips/' if kind == 'ip' else 'vlans/') + ('detail/' if detail else '')
        query = '?limit=0' if params is None else '?limit=2&offset=3&name=a+b%26c'
        adapter = FixtureAdapter(self, 'https://fixture.invalid/api/2.0/' + route + query,
                                 payload, status, exception)
        before = copy.deepcopy(params)
        with requests.Session() as session:
            session.mount('https://', adapter)
            session.mount('http://', adapter)
            obj = cls(api_endpoint='https://fixture.invalid/api/2.0/',
                      username='fixture', password='synthetic', session=session)
            method = ('list_detail' if detail else 'list') + ('' if legacy else '_raw')
            try:
                value = getattr(obj, method)(params)
                self.assertIs(obj.c.resp, adapter.response)
                return value
            finally:
                self.assertEqual(adapter.calls, 1)
                self.assert_json_exact(params, before)

    def test_public_complete_envelope(self):
        for kind in ('ip', 'vlan'):
            for detail in (False, True):
                payload = fixture(kind, 'detail' if detail else 'summary')
                self.assertEqual(set(payload['meta']), {'limit', 'offset', 'total_count'})
                for params in (None, {'limit': 2, 'offset': 3, 'name': 'a b&c'}):
                    self.assert_json_exact(self.read(kind, detail, payload, params), payload)
                    self.assert_json_exact(self.read(kind, detail, payload, params, legacy=True), payload['objects'])

    def test_cardinality_presence_types_and_ownership(self):
        extension = {'large': 9007199254740993, 'fraction': 1.25, 'null': None,
                     'false': False, 'zero': 0, 'text': '', 'ordered': [3, 1, 2]}
        for kind in ('ip', 'vlan'):
            for detail in (False, True):
                for count in (0, 1, 2):
                    for meta in ({}, {'limit': 2, 'offset': 3, 'total_count': 99},
                                 {'limit': None, 'offset': 0, 'total_count': 0}):
                        payload = fixture(kind, 'detail' if detail else 'summary')
                        first = payload['objects'][0]
                        payload['objects'] = [copy.deepcopy(first) for _ in range(count)]
                        for i, item in enumerate(payload['objects']):
                            item['synthetic_index'] = i
                            item['extension'] = copy.deepcopy(extension)
                        payload['meta'] = meta
                        payload['extension'] = copy.deepcopy(extension)
                        before = copy.deepcopy(payload)
                        result = self.read(kind, detail, payload)
                        self.assert_json_exact(result, before)
                        self.assertNotIn('next', result['meta'])
                        self.assertNotIn('previous', result['meta'])
                        result['extension']['ordered'].append(4)
                        self.assertEqual(result['extension']['ordered'], [3, 1, 2, 4])
                        self.assert_json_exact(payload, before)
                        if count:
                            result['objects'][0]['owner']['uuid'] = 'mutated'
                            self.assertEqual(result['objects'][0]['owner']['uuid'], 'mutated')
                            self.assert_json_exact(payload, before)
                            if count == 2:
                                self.assertNotEqual(result['objects'][1]['owner']['uuid'], 'mutated')
                        self.assert_json_exact(self.read(kind, detail, payload), before)
                for payload in ({'objects': []}, {'objects': None, 'meta': None},
                                {'meta': {}}, {'objects': [], 'extension': None}):
                    self.assert_json_exact(self.read(kind, detail, payload), payload)

    def test_errors_redirects_and_transport(self):
        for kind in ('ip', 'vlan'):
            for detail in (False, True):
                for status, cls in ((401, errors.AuthError), (403, errors.PermissionError),
                                    (404, errors.ClientError), (500, errors.ServerError),
                                    *((s, errors.ApiClientError) for s in (301,302,303,307,308))):
                    with self.assertRaises(cls) as caught:
                        self.read(kind, detail, b'fixture error', status=status)
                    self.assertIs(type(caught.exception.status_code), int)
                    self.assertEqual(caught.exception.status_code, status)
                    self.assertEqual(caught.exception.request_id, '' if status == 401 else 'fixture-request-id')
                    self.assertEqual(caught.exception.message, 'fixture-request-id' if status == 401 else
                                     'redirect refused' if 300 <= status < 400 else 'fixture error')
                with self.assertRaises(requests.exceptions.JSONDecodeError):
                    self.read(kind, detail, b'{bad')
                sentinel = requests.exceptions.ConnectionError('synthetic')
                with self.assertRaises(requests.exceptions.ConnectionError) as caught:
                    self.read(kind, detail, {}, exception=sentinel)
                self.assertIs(caught.exception, sentinel)

    def test_strict_oracle_negative_controls(self):
        expected = {'meta': {'limit': 0}, 'objects': [{'n': 9007199254740993}, {'n': 2}]}
        changes = [ {'meta': {'limit': False}, 'objects': expected['objects']},
                    {'objects': expected['objects']},
                    {'meta': {'limit': 0}, 'objects': list(reversed(expected['objects']))},
                    {'meta': {'limit': 0}, 'objects': [{'n': 9007199254740992}, {'n': 2}]}]
        for actual in changes:
            with self.assertRaises(AssertionError):
                self.assert_json_exact(actual, expected)

    def test_raw_decoder_not_overridden_legacy_scoped_policy(self):
        # New raw GET explicitly uses the generic numeric policy, not Decimal readers.
        from cloudsigma.router_reads import _RawReadClient
        from cloudsigma.generic import GenericClient
        self.assertIs(_RawReadClient.get_raw, GenericClient.get_raw)
        # A cached response object must be copied, not merely returned.
        client = GenericClient(api_endpoint='https://fixture.invalid/api/2.0/',
                               username='fixture', password='synthetic')
        try:
            response = requests.Response(); response.status_code = 200
            original = {'objects': [{'nested': [1]}], 'meta': {'total_count': 1}}
            with patch.object(response, 'json', return_value=original):
                result = client._decode_response(response, preserve_envelope=True)
            result['objects'][0]['nested'].append(2)
            self.assertEqual(result['objects'][0]['nested'], [1, 2])
            self.assertEqual(original['objects'][0]['nested'], [1])
        finally:
            client.http.close()
