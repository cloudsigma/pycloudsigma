import json
import unittest

import requests

from cloudsigma.resource import Keypairs


class Wire:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        status, body = self.responses.pop(0)
        response = requests.Response()
        response.status_code = status
        response._content = b'' if body is None else json.dumps(body).encode()
        response.headers['X-REQUEST-ID'] = 'synthetic-request'
        response.request = requests.Request(method, url).prepare()
        return response

    def __getattr__(self, method):
        return lambda url, **kwargs: self.request(method.upper(), url, **kwargs)


class KeypairsTests(unittest.TestCase):
    def test_documented_crud_routes_forward_explicit_otp(self):
        responses = [
            (200, {'objects': [{'uuid': 'key-1'}],
                   'meta': {'limit': 1, 'offset': 0, 'total_count': 1}}),
            (200, {'objects': [{'uuid': 'key-1',
                                'private_key': 'synthetic-private-key'}]}),
            (201, {'objects': [{'uuid': 'key-2'}]}),
            (200, {'objects': [{'uuid': 'key-2'}]}),
            (204, None),
        ]
        wire = Wire(responses)
        keypairs = Keypairs(
            api_endpoint='https://next.cloudsigma.com/api/2.0/',
            username='synthetic',
            password='synthetic',
            login_method='basic',
        )
        keypairs.c._session = wire

        self.assertEqual(keypairs.list({'limit': 1}, otp='123456'),
                         [{'uuid': 'key-1'}])
        self.assertEqual(keypairs.get('key-1', otp='123456'), {
            'uuid': 'key-1', 'private_key': 'synthetic-private-key'})
        self.assertEqual(keypairs.create({'name': 'synthetic'}, otp='123456'),
                         {'uuid': 'key-2'})
        self.assertEqual(keypairs.update(
            'key-2', {'name': 'renamed'}, otp='123456'), {'uuid': 'key-2'})
        self.assertIsNone(keypairs.delete('key-2', otp='123456'))

        self.assertEqual(
            [(method, url) for method, url, _ in wire.calls],
            [
                ('GET', 'https://next.cloudsigma.com/api/2.0/keypairs/'),
                ('GET', 'https://next.cloudsigma.com/api/2.0/keypairs/key-1/'),
                ('POST', 'https://next.cloudsigma.com/api/2.0/keypairs/'),
                ('PUT', 'https://next.cloudsigma.com/api/2.0/keypairs/key-2/'),
                ('DELETE', 'https://next.cloudsigma.com/api/2.0/keypairs/key-2/'),
            ],
        )
        for _, _, kwargs in wire.calls:
            self.assertEqual(kwargs['headers']['OTP'], '123456')
        self.assertEqual(wire.calls[0][2]['params'], {'limit': 1})
        self.assertEqual(json.loads(wire.calls[2][2]['data']), {
            'objects': [{'name': 'synthetic'}]})
        self.assertEqual(json.loads(wire.calls[3][2]['data']), {
            'name': 'renamed'})


if __name__ == '__main__':
    unittest.main()
