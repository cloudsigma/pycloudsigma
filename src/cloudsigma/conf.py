# Configuration of the client.
import os

from configobj import ConfigObj

CONFIG_LOCATION = os.getenv(
    'CLOUDSIGMA_CONFIG',
    os.path.join(os.path.expanduser('~'), '.cloudsigma.conf')
)

config = ConfigObj(CONFIG_LOCATION)
