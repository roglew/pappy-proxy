#!/usr/bin/env python

from distutils.core import setup

setup(name='pappyproxy',
      version='0.0.1',
      description='The Pappy Intercepting Proxy',
      author='Rob Glew',
      author_email='rglew56@gmail.com',
      url='https://www.github.com/roglew/pappy-proxy',
      packages=['pappyproxy'],
      license='MIT',
      entry_points = {
          'console_scripts':['pappy = pappyproxy.pappy:start'],
          },
      long_description=open('README.md').read(),
      keywords='http proxy hacking 1337hax pwnurmum',
      install_requires=[
          'cmd2>=0.6.8',
          'crochet>=1.4.0',
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
          'Operating System :: MacOS',
          'Operating System :: POSIX :: Linux',
          'Development Status :: 2 - Pre-Alpha',
          'Programming Language :: Python :: 2.6',
          'Programming Language :: Python :: 2.7',
          'License :: OSI Approved :: MIT License',
          'Topic :: Security',
<<<<<<< HEAD
          'Topic :: Security :: Pwning Ur Mum',
=======
>>>>>>> master
        ]
)
