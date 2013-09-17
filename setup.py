# encoding: utf-8
from setuptools import setup

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
