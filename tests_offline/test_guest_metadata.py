"""Guest serial trigger bytes; no device is opened by these tests."""
import unittest
from unittest.mock import patch
from serial.serialutil import to_bytes
from cloudsigma import metadata


class SerialFixture:
    def __init__(self):
        self.writes = []
        self.closed = False

    def write(self, data):
        # Actual pyserial conversion rejects Python 3 str before OS writes.
        self.writes.append(to_bytes(data))

    def readlines(self):
        return [b'{"meta":{"name":"fixture"},"cpu":1000}\n']

    def close(self):
        self.closed = True


class GuestMetadataTests(unittest.TestCase):
    def test_trigger_bytes_and_decode(self):
        device = SerialFixture()
        with patch.object(metadata.serial, 'Serial', return_value=device) as factory:
            result = metadata.GetServerMetadata().get()
        factory.assert_called_once_with('/dev/ttyS1', timeout=1)
        self.assertEqual(device.writes, [b'<\n\n>'])
        self.assertEqual(result, {'meta': {'name': 'fixture'}, 'cpu': 1000})
        self.assertTrue(device.closed)


if __name__ == '__main__':
    unittest.main()
