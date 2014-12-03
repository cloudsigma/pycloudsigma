"""Configuration of the client."""
import os

CONFIG_LOCATION = os.getenv('CLOUDSIGMA_CONFIG',
                            os.path.join(os.path.expanduser('~'), '.cloudsigma.conf')
                            )

from configobj import ConfigObj

config = ConfigObj(CONFIG_LOCATION)
