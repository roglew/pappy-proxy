#!/usr/bin/env python

from distutils.core import setup

setup(name='Pappy',
      version='0.0.1',
      description='The Pappy Intercepting Proxy',
      author='Rob Glew',
      author_email='rglew56@gmail.com',
      url='https://www.github.com/roglew/pappy-proxy',
      packages=['pappy-proxy'],
      license='MIT',
      install_requires=[
          'twisted',
          'crochet',
          'cmd2',
          'service_identity',
          'pytest',
          'pytest-cov',
          'pytest-twisted',
          ]
     )
