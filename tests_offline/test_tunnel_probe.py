import contextlib
import io
import json
import unittest
from pathlib import Path
from unittest import mock

import importlib.util


_spec = importlib.util.spec_from_file_location(
    'run_tunnel_probe', Path(__file__).parents[1] / 'ci' / 'run_tunnel_probe.py')
run_tunnel_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_tunnel_probe)


class Response:
    def __init__(self, status_code=200, body=None, headers=None):
        self.status_code = status_code
        self._body = body
        self.headers = headers or {'Content-Type': 'application/json'}

    def json(self):
        return self._body


class Session:
    def __init__(self):
        self.auth = None
        self.trust_env = True
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Response(
            body={'secret': 'must not be printed'},
            headers={'Content-Type': 'application/json', 'X-REQUEST-ID': 'req-1'},
        )


class AuthFailureSession(Session):
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Response(status_code=401, body={'detail': 'hidden'})


class TunnelProbeTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(run_tunnel_probe, 'ENDPOINT',
                                    run_tunnel_probe.ALLOWED_ENDPOINT)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_probe_uses_get_only_and_summarizes_without_values(self):
        session = Session()
        with mock.patch.object(run_tunnel_probe, 'USERNAME', 'user'), \
                mock.patch.object(run_tunnel_probe, 'PASSWORD', 'password'):
            result = run_tunnel_probe.probe(session)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(len(session.calls), len(run_tunnel_probe.ROUTES))
        self.assertEqual(session.auth, ('user', 'password'))
        self.assertFalse(session.trust_env)
        for _, kwargs in session.calls:
            self.assertFalse(kwargs['allow_redirects'])
            self.assertEqual(kwargs['headers'], {'Accept': 'application/json'})
        output = json.dumps(result)
        self.assertNotIn('must not be printed', output)
        self.assertNotIn('password', output)

    def test_missing_credentials_is_configuration_failure(self):
        with mock.patch.object(run_tunnel_probe, 'USERNAME', None), \
                mock.patch.object(run_tunnel_probe, 'PASSWORD', None):
            result = run_tunnel_probe.probe(Session())
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['error_type'], 'ConfigurationError')

    def test_main_calls_probe_once(self):
        output = io.StringIO()
        with mock.patch.object(run_tunnel_probe, 'probe', return_value={
                'status': 'passed', 'checks': [], 'failed': 0}), \
                contextlib.redirect_stdout(output):
            self.assertEqual(run_tunnel_probe.main(), 0)
        self.assertEqual(output.getvalue().count('"status": "passed"'), 1)

    def test_authentication_failure_fails_probe(self):
        with mock.patch.object(run_tunnel_probe, 'USERNAME', 'user'), \
                mock.patch.object(run_tunnel_probe, 'PASSWORD', 'password'):
            result = run_tunnel_probe.probe(AuthFailureSession())
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['failed'], len(run_tunnel_probe.ROUTES))
        self.assertTrue(all(
            item['status'] == 'authentication_or_permission_failure'
            for item in result['checks']))

    def test_known_provider_gaps_are_reported_without_hiding_other_errors(self):
        statuses = [200, 200, 200, 404, 301, 500, 200, 200]
        client = Session()
        responses = [Response(status, headers={
            'Content-Type': 'application/json',
            'Location': '/api/2.0/tunnels/'}) for status in statuses]
        with mock.patch.object(run_tunnel_probe, 'USERNAME', 'user'), \
                mock.patch.object(run_tunnel_probe, 'PASSWORD', 'password'), \
                mock.patch.object(client, 'get', side_effect=responses):
            result = run_tunnel_probe.probe(client)
        self.assertEqual(result['status'], 'passed_with_known_gaps')
        self.assertEqual(result['known_provider_gaps'], 2)
        self.assertEqual(result['checks'][4]['status'], 'redirect_observed')
        self.assertEqual(result['failed'], 0)

    def test_unexpected_route_failure_and_cross_origin_redirect_fail(self):
        for index, response in ((0, Response(404)), (3, Response(500)),
                                (4, Response(301, headers={
                                    'Location': 'https://other.example/tunnels/'}))):
            with self.subTest(index=index):
                responses = [Response() for _ in run_tunnel_probe.ROUTES]
                responses[index] = response
                client = Session()
                with mock.patch.object(run_tunnel_probe, 'USERNAME', 'user'), \
                        mock.patch.object(run_tunnel_probe, 'PASSWORD', 'password'), \
                        mock.patch.object(client, 'get', side_effect=responses):
                    result = run_tunnel_probe.probe(client)
                self.assertEqual(result['status'], 'failed')
                self.assertEqual(result['failed'], 1)

    def test_endpoint_refused_before_credential_dispatch(self):
        client = Session()
        with mock.patch.object(run_tunnel_probe, 'USERNAME', 'user'), \
                mock.patch.object(run_tunnel_probe, 'PASSWORD', 'password'), \
                mock.patch.object(run_tunnel_probe, 'ENDPOINT', 'http://other.example/'):
            result = run_tunnel_probe.probe(client)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(client.calls, [])
        self.assertIsNone(client.auth)

    def test_failure_exit_status_is_nonzero(self):
        with mock.patch.object(run_tunnel_probe, 'probe', return_value={
                'status': 'failed', 'checks': [], 'failed': 1}), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(run_tunnel_probe.main(), 1)


if __name__ == '__main__':
    unittest.main()
