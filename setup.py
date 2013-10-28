#!/usr/bin/env python

from setuptools import setup

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
====================================
CloudSigma's official python library
====================================

pycloudsigma allows you to easily manage your entire infrastructure from within Python.

Creating a server is a simple as:

::

    import cloudsigma
    server = cloudsigma.resource.Server()
    test_server = { 'name': 'My Test Server', 'cpu': 1000, 'mem': 512 * 1024 ** 2, 'vnc_password': 'test_server' }
    my_test_server = server.create(test_server)


For more examples, please visit pycloudsigma_.

For more detailed information about CloudSigma's, please visit the `API documentation <https://zrh.cloudsigma.com/docs/>`_.

.. _pycloudsigma: https://github.com/cloudsigma/pycloudsigma/blob/master/README.md
    """
)
