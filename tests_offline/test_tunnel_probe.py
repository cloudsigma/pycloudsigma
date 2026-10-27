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
    def __init__(self, status_code=404, body=None, headers=None):
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


class TunnelProbeTests(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
