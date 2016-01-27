#!/usr/bin/env python

import pkgutil
from setuptools import setup, find_packages

VERSION = '0.2.3'

setup(name='pappyproxy',
      version=VERSION,
      description='The Pappy Intercepting Proxy',
      author='Rob Glew',
      author_email='rglew56@gmail.com',
      url='https://www.github.com/roglew/pappy-proxy',
      packages=['pappyproxy', 'pappyproxy.schema', 'pappyproxy.plugins'],
      include_package_data = True,
      license='MIT',
      entry_points = {
          'console_scripts':['pappy = pappyproxy.pappy:start'],
          },
      long_description=open('docs/source/overview.rst').read(),
      keywords='http proxy hacking 1337hax pwnurmum',
      download_url='https://github.com/roglew/pappy-proxy/archive/%s.tar.gz'%VERSION,
      install_requires=[
          'beautifulsoup4>=4.4.1',
          'clipboard>=0.0.4',
          'cmd2>=0.6.8',
          'crochet>=1.4.0',
          'Jinja2>=2.8',
          'pygments>=2.0.2',
          'pytest-cov>=2.2.0',
          'pytest-mock>=0.9.0',
          'pytest-twisted>=1.5',
          'pytest>=2.8.3',
          'service_identity>=14.0.0',
          'twisted>=15.4.0',
          ],
      classifiers=[
          'Intended Audience :: Developers',
          'Intended Audience :: Information Technology',
          'Operating System :: MacOS',
          'Operating System :: POSIX :: Linux',
          'Development Status :: 2 - Pre-Alpha',
          'Programming Language :: Python :: 2.6',
          'Programming Language :: Python :: 2.7',
          'License :: OSI Approved :: MIT License',
          'Topic :: Security',
        ]
)
