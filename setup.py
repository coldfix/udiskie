# encoding: utf-8
from __future__ import print_function
from setuptools import setup
import sys

# check availability of runtime dependencies
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('-f', '--force', dest="force",
        action="store_true", default=False)
args, sys.argv = parser.parse_known_args(sys.argv)
if not args.force:
    try:
        import dbus
        import gobject
        import pynotify
    except ImportError:
        err = sys.exc_info()[1]
        print("Missing runtime dependency:", err)
        print("Use --force if you want to continue anyway.")
        sys.exit(1)

# read long_description from README.rst
try:
    f = open('README.rst')
    long_description = f.read()
    f.close()
except:
    long_description = None

setup(
    name='udiskie',
    version='0.5.0',
    description='Removable disk automounter for udisks',
    long_description=long_description,
    author='Byron Clark',
    author_email='byron@theclarkfamily.name',
    maintainer='Thomas Gläßle',
    maintainer_email='t_glaessle@gmx.de',
    url='https://github.com/coldfix/udiskie',
    license='MIT',
    packages=[
        'udiskie',
    ],
    scripts=[
        'bin/udiskie',
        'bin/udiskie-umount',
        'bin/udiskie-mount'
    ],
    install_requires=[
    ],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Environment :: X11 Applications',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'License :: OSI Approved :: MIT License',
        'Topic :: Desktop Environment',
        'Topic :: Software Development',
        'Topic :: System :: Filesystems',
        'Topic :: System :: Hardware',
        'Topic :: Utilities',
    ],
)
