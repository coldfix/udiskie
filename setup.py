# encoding: utf-8
from setuptools import setup

# check availability of runtime dependencies
def check_any(*packages):
    """Issue a warning if none of the packages is available."""
    errors = []
    for package in packages:
        try:
            __import__(package)
            return True
        except ImportError:
            import sys
            errors.append(sys.exc_info()[1])
    if len(errors) == 1:
        print("Missing runtime dependency: %s" % errors[0])
    else:
        print("Missing runtime dependencies:")
        for err in errors:
            print("\t%s" % err)
    return False

check_any('dbus')
check_any('gobject')
check_any('pynotify', 'notify2')

# read long_description from README.rst
try:
    f = open('README.rst')
    long_description = f.read()
    f.close()
except IOError:
    long_description = None

setup(
    name='udiskie',
    version='0.5.2',
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
    namespace_packages=[
        'udiskie',
    ],
    entry_points={
        'console_scripts': [
            'udiskie = udiskie.cli:daemon',
            'udiskie-mount = udiskie.cli:mount',
            'udiskie-umount = udiskie.cli:umount',
        ],
    },
    extras_require={
        'notifications': ['notify2']
    },
    install_requires=[
        # Currently not building out of the box:
        # 'PyGObject',
        # 'dbus-python',
    ],
    tests_require=[
        'python-dbusmock>=0.7.2'
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
