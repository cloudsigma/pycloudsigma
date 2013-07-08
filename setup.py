#!/usr/bin/env python

from setuptools import setup

execfile('src/cloudsigma/version.py')


with open('requirements.txt') as f:
    required = f.read().splitlines()


setup(
    name='cloudsigma',
    version=0.1,
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
    author='CloudSigma AG',
    author_email='dev-support@cloudsigma.com',
    url='https://github.com/cloudsigma/pycloudsigma',
    install_requires=required,
    description="CloudSigma's official python library.",
    keywords=[
        'cloud',
        'cloudsigma',
        'api',
        'cloud computing'
    ],
    classifiers=[
        "Programming Language :: Python",
        "Development Status :: 4 - Beta",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Developers",
    ],
    long_description="""\
CloudSigma's official python library
------------------------------------

With this library, you can easily manage your entire infrastructure from within Python.


More information:
 * pycloudsigma documentation[1]
 * CloudSigma API documentation[2]

[1] https://github.com/cloudsigma/pycloudsigma/blob/master/README.md
[2] https://zrh.cloudsigma.com/docs/

    """
)
