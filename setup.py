#!/usr/bin/env python
from setuptools import setup

try:
    import pypandoc
    long_description = pypandoc.convert('README.md', 'rst')
except(IOError, ImportError):
    long_description = ""

packages = [
    'selenium_respectful',
]

requires = [
    'selenium',
    'redis',
    'PyYAML'
]

setup(
    name='selenium-respectful',
    version="0.1.0",
    description='Minimalist Selenium webdriver wrapper to work within rate limits of any amount of services simultaneously. Parallel processing friendly.',
    long_description=long_description,
    author="Nicholas Brochu",
    author_email='nicholas@serpent.ai',
    packages=packages,
    include_package_data=True,
    install_requires=requires,
    license='Apache License v2',
    url='https://github.com/nbrochu/selenium-respectful',
    zip_safe=False,
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6'
    ]
)
