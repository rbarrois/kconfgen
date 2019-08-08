#!/usr/bin/env python
# -*- coding: utf-8 -*-

import codecs
import os
import re

from setuptools import setup

root_dir = os.path.abspath(os.path.dirname(__file__))


def get_version(version_file_name):
    version_re = re.compile(r"^__version__ = [\"']([\w_.-]+)[\"']$")
    init_path = os.path.join(root_dir, version_file_name)
    with codecs.open(init_path, 'r', 'utf-8') as f:
        for line in f:
            match = version_re.match(line[:-1])
            if match:
                return match.groups()[0]
    return '0.1.0'


PACKAGE = 'kconfgen'
SRC_DIR = 'src'

setup(
    name='kconfgen',
    version=get_version('%s/%s/__init__.py' % (SRC_DIR, PACKAGE)),
    description="A generator of (minimal) Linux kernel configuration files.",
    long_description=codecs.open(os.path.join(root_dir, 'README.rst'), 'r', 'utf-8').read(),
    author="Raphaël Barrois",
    author_email='raphael.barrois+%s@polytechnique.org' % PACKAGE,
    url='https://github.com/rbarrois/%s' % PACKAGE,
    keywords=['kconfgen', 'kconfig', 'kernel', 'linux', 'configuration', 'generator'],
    packages=[PACKAGE],
    package_dir={'': SRC_DIR},
    zip_safe=False,
    license='MIT',
    python_requires=">=3.5",
    install_requires=[
        'kconfiglib',
        'toml',
    ],
    setup_requires=[
        'setuptools>=0.8',
    ],
    tests_require=[
        # 'mock',
    ],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
    ],
    test_suite='',
    test_loader='unittest:TestLoader',
    entry_points={
        'console_scripts': [
            'kconfgen=kconfgen.cli:main',
        ],
    },
)
