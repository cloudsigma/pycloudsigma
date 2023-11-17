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
        except (serial.SerialException, ValueError) as e:
            # Handle the exception (print an error, log it, etc.)
            error_message =\
                "An error occurred: {}. Please check the documentation for troubleshooting:" \
                " https://docs.cloudsigma.com/en/2.14.1/server_context.html" \
                "#setting-up-the-virtual-serial-port".format(e)
            print(error_message)
            self.result = None

    def get(self):
        return self.result
