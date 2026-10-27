import contextlib
import io
import json
from unittest import TestCase, mock

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "ci_run_live_smoke", Path(__file__).parents[1] / "ci" / "run_live_smoke.py")
ci_run_live_smoke = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ci_run_live_smoke)


class LiveSmokeRunnerTests(TestCase):
    def test_shape_is_non_sensitive(self):
        self.assertEqual(ci_run_live_smoke._shape([1, 2]), {
            'type': 'list', 'count': 2})
        self.assertEqual(ci_run_live_smoke._shape({'password': 'secret'}), {
            'type': 'dict', 'key_count': 1})

    def test_missing_credentials_fails_without_network(self):
        output = io.StringIO()
        with mock.patch.object(ci_run_live_smoke, 'USERNAME', None), \
                mock.patch.object(ci_run_live_smoke, 'PASSWORD', None), \
                contextlib.redirect_stdout(output):
            result = ci_run_live_smoke.main()
        self.assertEqual(result, 2)
        decoded = json.loads(output.getvalue())
        self.assertEqual(decoded['error_type'], 'ConfigurationError')
        self.assertNotIn('secret', output.getvalue())


if __name__ == '__main__':
    unittest.main()
