"""Existing bulk lookup fallback; no clone or cloud operations."""
import json
import unittest
from unittest.mock import patch

import requests
from cloudsigma.bulk import DrivesBulk
from cloudsigma.conf import config
from cloudsigma.errors import ClientError


class LookupAdapter(requests.adapters.BaseAdapter):
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def send(self, request, **kwargs):
        self.requests.append(request)
        status, body = self.responses.pop(0)
        response = requests.Response()
        response.status_code = status
        response._content = json.dumps(body).encode('utf-8')
        response.request = request
        response.headers['X-REQUEST-ID'] = 'lookup-fixture'
        return response

    def close(self):
        pass


class BulkLibraryLookupTests(unittest.TestCase):
    def lookup(self, key, owned, library=None, failure=None):
        responses = [(200, {'objects': owned})]
        if library is not None:
            responses.append((200, {'objects': library}))
        elif failure is not None:
            responses.append((failure, {'error_message': 'fixture refusal'}))
        adapter = LookupAdapter(responses)
        with patch.dict(config, {'api_endpoint': 'https://fixture.invalid/api/2.0/',
                                 'username': 'fixture', 'password': 'synthetic',
                                 'login_method': 'basic'}, clear=True):
            bulk = DrivesBulk(id_prefix='fixture')
        self.addCleanup(bulk.c.http.close)
        for resource in (bulk.c_drive, bulk.c_libdrive, bulk.c_guest):
            self.addCleanup(resource.c.http.close)
            resource.c.http.mount('https://', adapter)
        try:
            result = bulk.lookup(key)
        except AttributeError:
            raise
        except Exception:
            self.assertEqual(len(adapter.requests), len(responses))
            raise
        else:
            self.assertEqual([r.method for r in adapter.requests],
                             ['GET'] * len(adapter.requests))
            expected = ['https://fixture.invalid/api/2.0/drives/detail/?limit=0']
            if library is not None or failure is not None:
                expected.append('https://fixture.invalid/api/2.0/libdrives/detail/?limit=0')
            self.assertEqual([r.url for r in adapter.requests], expected)
            self.assertTrue(all(r.body is None for r in adapter.requests))
            self.assertEqual(adapter.responses, [])
            return result

    def test_owned_match_does_not_query_library(self):
        owned = {'uuid': 'owned', 'name': 'target image', 'meta': {'keep': 'value'}}
        self.assertEqual(self.lookup('target', [owned]), owned)

    def test_library_uuid_fallback(self):
        library = {'uuid': 'library', 'name': 'image', 'owner': None,
                   'size': 9007199254740993, 'meta': {'keep': 'value'}}
        self.assertEqual(self.lookup('library', [], [library]), library)

    def test_library_substring_preserves_first_match(self):
        first = {'uuid': 'first', 'name': 'target image A'}
        second = {'uuid': 'second', 'name': 'target image B'}
        self.assertEqual(self.lookup('target', [{'uuid': 'other', 'name': 'other'}],
                                     [first, second]), first)

    def test_no_match_preserves_lookup_error(self):
        with self.assertRaisesRegex(Exception, '^Could not find DrivesBulk with lookup key absent$'):
            self.lookup('absent', [], [{'uuid': 'other', 'name': 'other'}])

    def test_empty_library_preserves_lookup_error(self):
        with self.assertRaisesRegex(Exception, '^Could not find DrivesBulk with lookup key absent$'):
            self.lookup('absent', [], [])

    def test_library_http_error_propagates(self):
        with self.assertRaises(ClientError) as caught:
            self.lookup('absent', [], failure=404)
        self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(caught.exception.request_id, 'lookup-fixture')
