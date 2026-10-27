from builtins import object
import serial
import json


class _SerialDevice:
    """Close a serial device without masking an earlier body exception."""

    def __init__(self):
        self.device = serial.Serial('/dev/ttyS1', timeout=1)

    def __enter__(self):
        return self.device

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            self.device.close()
        else:
            try:
                self.device.close()
            except Exception:
                return False
        return False


class GetServerMetadata(object):
    result = None

    def __init__(self):
        try:
            with _SerialDevice() as ser:
                # Trigger a read from the serial device
                ser.write(b'<\n\n>')

                # Read the data and convert it to json
                data = ser.readlines()
                self.result = json.loads(data[0])
        except serial.SerialException as e:
            error_message =\
                "An error occurred: {}. Please check the documentation for troubleshooting: " \
                "https://docs.cloudsigma.com/en/2.14.1/server_context.html " \
                "#setting-up-the-virtual-serial-port".format(e)
            raise serial.SerialException(error_message)
        except ValueError as e:
            error_message = \
                "An error occurred: {}. Please check the documentation for troubleshooting: " \
                "https://docs.cloudsigma.com/en/2.14.1/server_context.html" \
                "#setting-up-the-virtual-serial-port".format(e)
            self.result = None
            raise ValueError(error_message)

    def get(self):
        return self.result
