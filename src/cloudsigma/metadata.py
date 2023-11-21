from builtins import object
import serial
import json


class GetServerMetadata(object):
    result = None

    def __init__(self):
        try:

            # Open serial device (should always be ttyS1)
            ser = serial.Serial('/dev/ttyS1', timeout=1)

            # Trigger a read from the serial device
            ser.write('<\n\n>')

            # Read the data and convert it to json
            data = ser.readlines()
            self.result = json.loads(data[0])

            ser.close()
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
