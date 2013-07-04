#!/usr/bin/env python

from distutils.core import setup


execfile('src/cloudsigma/version.py')


with open('requirements.txt') as f:
    required = f.read().splitlines()


setup(
    name='cloudsigma',
    version=__version__,
    packages=[
        'cloudsigma',
    ],
    package_dir={
        '': 'src'
    },
    package_data={
        'templates': [
            'request_template',
            'response_template',
        ]
    },
    author='CloudSigma',
    install_requires=required
)
