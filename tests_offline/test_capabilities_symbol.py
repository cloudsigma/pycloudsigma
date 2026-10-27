import unittest

from cloudsigma.resource import Capabilities, Capabilites


class CapabilitiesSymbolTests(unittest.TestCase):
    def test_correct_spelling_and_legacy_alias(self):
        self.assertIs(Capabilities, Capabilites)
        self.assertEqual(Capabilities.resource_name, 'capabilities')


if __name__ == '__main__':
    unittest.main()
