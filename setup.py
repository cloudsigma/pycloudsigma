#!/usr/bin/env python

from distutils.core import setup

setup(
    name='cloudsigma',
    version='0.1.0',
    packages=[
        'cloudsigma',
        'cloudsigma.testing',
    ],
    package_dir={
        'cloudsigma': 'src/cloudsigma',
        'cloudsigma.testing': 'src/testing',
    },
    package_data={
        'templates': [
            'request_template',
            'response_template',
        ]
    },
    author='CloudSigma',
    install_requires=[
        'configobj>=4.7',
        'requests>=1.2.0',
        'websocket-client>=0.9.0',
        'simplejson>=2.5.2',
        'nose>=1.1.2',
    ],
)
