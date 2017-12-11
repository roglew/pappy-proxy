#!/usr/bin/env python

import pkgutil
#import pappyproxy
from setuptools import setup, find_packages

VERSION = "0.3.1"

setup(name='pappyproxy',
      version=VERSION,
      description='The Pappy Intercepting Proxy',
      author='Rob Glew',
      author_email='rglew56@gmail.com',
      #url='https://www.github.com/roglew/puppy-proxy',
      packages=['pappyproxy', 'pappyproxy.interface'],
      include_package_data = True,
      package_data={'pappyproxy': ['templates', 'lists']},
      license='MIT',
      entry_points = {
          'console_scripts':['pappy = pappyproxy.pap:start'],
          },
      #long_description=open('docs/source/overview.rst').read(),
      long_description="The Pappy Proxy",
      keywords='http proxy hacking 1337hax pwnurmum',
      #download_url='https://github.com/roglew/pappy-proxy/archive/%s.tar.gz'%VERSION,
      install_requires=[
          'cmd2>=0.6.8',
          'Jinja2>=2.8',
          'pygments>=2.0.2',
          ],
      classifiers=[
          'Intended Audience :: Developers',
          'Intended Audience :: Information Technology',
          'Operating System :: MacOS',
          'Operating System :: POSIX :: Linux',
          'Development Status :: 2 - Pre-Alpha',
          'Programming Language :: Python :: 3.6',
          'License :: OSI Approved :: MIT License',
          'Topic :: Security',
        ]
)
