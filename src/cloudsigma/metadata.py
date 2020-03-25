from builtins import object
import serial
import json


class GetServerMetadata(object):
    result = None

    def __init__(self):

        # Open serial device (should always be ttyS1)
        ser = serial.Serial('/dev/ttyS1', timeout=1)

        # Trigger a read from the serial device
        ser.write('<\n\n>')

        # Read the data and convert it to json
        data = ser.readlines()
        self.result = json.loads(data[0])

        ser.close()

    def get(self):
        return self.result
