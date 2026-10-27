import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_api_contract", ROOT / "ci" / "validate_api_contract.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ApiContractTests(unittest.TestCase):
    def test_checked_in_matrix_is_valid(self):
        self.assertEqual(MODULE.validate(), [])

    def test_duplicate_operation_identity_is_rejected(self):
        document = MODULE.MATRIX.read_text(encoding="utf-8")
        with tempfile.NamedTemporaryFile(suffix=".json") as handle:
            duplicate = Path(handle.name)
            import json
            payload = json.loads(document)
            payload["operations"].append(dict(payload["operations"][0]))
            duplicate.write_text(json.dumps(payload), encoding="utf-8")
            self.assertTrue(any("duplicates operation identity" in error
                                for error in MODULE.validate(duplicate)))


if __name__ == "__main__":
    unittest.main()
