#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os.path
import io
from setuptools import setup
from pip.req import parse_requirements


readme_file = io.open('README.rst', 'rt', encoding='UTF-8')
long_description = readme_file.read()
readme_file.close()

package_data = {
    '': ['LICENSE', 'README.rst'],
}

scripts = ['tx_pull']

extra_args = {}
install_reqs = parse_requirements('requirements.txt')
reqs = [str(ir.req) for ir in install_reqs]

setup(
    name="transifex-puller",
    version="1.0",
    scripts=scripts,
    description="A command line interface to pull translations from Transifex",
    long_description=long_description,
    author="OCA - Odoo Community Associatin",
    license="GPLv2",
    dependency_links=[
    ],
    setup_requires=[
    ],
    install_requires=reqs,
    tests_require=["mock", ],
    data_files=[
    ],
    test_suite="tests",
    zip_safe=False,
    packages=[
    ],
    include_package_data=True,
    package_data=package_data,
    keywords=('translation', 'localization', 'internationalization',),
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
    ],
    **extra_args
)
