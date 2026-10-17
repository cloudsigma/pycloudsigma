"""Owned serial cleanup, without opening a device or changing legacy errors."""
import unittest
from unittest.mock import patch
from cloudsigma import metadata


class Device:
    def __init__(self, stage=None, error=None, close_error=None, lines=None):
        self.stage, self.error, self.close_error = stage, error, close_error
        self.lines = lines if lines is not None else [b'{"meta":{"name":"fixture"}}']
        self.closes = 0
        self.writes = []

    def write(self, data):
        self.writes.append(data)
        if self.stage == 'write':
            raise self.error

    def readlines(self):
        if self.stage == 'read':
            raise self.error
        return self.lines

    def close(self):
        self.closes += 1
        if self.close_error is not None:
            raise self.close_error


class GuestMetadataCleanupTests(unittest.TestCase):
    def invoke(self, device):
        with patch.object(metadata.serial, 'Serial', return_value=device) as factory:
            try:
                return metadata.GetServerMetadata().get()
            finally:
                factory.assert_called_once_with('/dev/ttyS1', timeout=1)

    def test_success_closes_once(self):
        device = Device()
        self.assertEqual(self.invoke(device), {'meta': {'name': 'fixture'}})
        self.assertEqual(device.writes, [b'<\n\n>'])
        self.assertEqual(device.closes, 1)

    def test_io_failures_close_and_preserve_identity(self):
        for stage in ('write', 'read'):
            for cls in (OSError, RuntimeError, KeyboardInterrupt):
                with self.subTest(stage=stage, cls=cls):
                    error = cls('original')
                    device = Device(stage, error)
                    with self.assertRaises(cls) as caught:
                        self.invoke(device)
                    self.assertIs(caught.exception, error)
                    self.assertEqual(device.closes, 1)

    def test_serial_failure_keeps_legacy_wrapper(self):
        for stage in ('write', 'read'):
            with self.subTest(stage=stage):
                error = metadata.serial.SerialException('serial-failure')
                device = Device(stage, error)
                with self.assertRaises(metadata.serial.SerialException) as caught:
                    self.invoke(device)
                self.assertIs(caught.exception.__context__, error)
                self.assertEqual(str(caught.exception), 'An error occurred: serial-failure. Please check the documentation for troubleshooting: https://docs.cloudsigma.com/en/2.14.1/server_context.html #setting-up-the-virtual-serial-port')
                self.assertEqual(device.closes, 1)

    def test_json_failure_keeps_legacy_wrapper_and_closes(self):
        error = ValueError('json-failure')
        device = Device()
        with patch.object(metadata.json, 'loads', side_effect=error):
            with self.assertRaises(ValueError) as caught:
                self.invoke(device)
        self.assertIs(caught.exception.__context__, error)
        self.assertEqual(str(caught.exception), 'An error occurred: json-failure. Please check the documentation for troubleshooting: https://docs.cloudsigma.com/en/2.14.1/server_context.html#setting-up-the-virtual-serial-port')
        self.assertEqual(device.closes, 1)

    def test_actual_malformed_json_closes(self):
        device = Device(lines=[b'{'])
        with self.assertRaises(ValueError):
            self.invoke(device)
        self.assertEqual(device.closes, 1)

    def test_empty_response_retains_indexerror_and_closes(self):
        device = Device(lines=[])
        with self.assertRaises(IndexError):
            self.invoke(device)
        self.assertEqual(device.closes, 1)

    def test_constructor_failure_keeps_legacy_wrapper(self):
        error = metadata.serial.SerialException('open-failure')
        with patch.object(metadata.serial, 'Serial', side_effect=error):
            with self.assertRaises(metadata.serial.SerialException) as caught:
                metadata.GetServerMetadata()
        self.assertIs(caught.exception.__context__, error)

    def test_close_failure_after_success_still_propagates(self):
        error = OSError('close-failure')
        device = Device(close_error=error)
        with self.assertRaises(OSError) as caught:
            self.invoke(device)
        self.assertIs(caught.exception, error)
        self.assertEqual(device.closes, 1)

    def test_close_failure_does_not_mask_existing_failure(self):
        for stage in ('write', 'read'):
            with self.subTest(stage=stage):
                error = RuntimeError('original')
                device = Device(stage, error, OSError('close-failure'))
                with self.assertRaises(RuntimeError) as caught:
                    self.invoke(device)
                self.assertIs(caught.exception, error)
                self.assertEqual(device.closes, 1)
