#!/usr/bin/python

import os
import sys

from setuptools import find_packages, setup

from monitoring import __version__


SCRIPTDIR = os.path.dirname(__file__) or '.'
PY3 = sys.version_info >= (3, 0, 0)

VERSION = '0.4.dev1'


def read(fname):
    """ Return content of specified file """
    path = os.path.join(SCRIPTDIR, fname)
    if PY3:
        f = open(path, 'r', encoding='utf8')
    else:
        f = open(path, 'r')
    content = f.read()
    f.close()
    return content


setup(
    name='monitoring',
    version=__version__,
    author='Outernet Inc',
    author_email='apps@outernet.is',
    description='Server and client for monitoring ONDD internal state',
    license='GPLv3',
    keywords='broadcast, outernet, signal, service, monitoring',
    url='https://github.com/Outernet-Project/monitoring',
    packages=find_packages(),
    include_package_data=True,
    long_description=read('README.rst'),
    install_requires=read('requirements.txt').strip().split('\n'),
    entry_points={
        'console_scripts': [
            'monitoring = monitoring.app:main',
            'monitoring-client = client.monitor:main'
        ]
    },
)
