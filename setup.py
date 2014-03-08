# encoding: utf-8
from setuptools import setup
from setuptools.command.install import install
from subprocess import call
import sys
import logging
from os import path

# check availability of runtime dependencies
def check_any(*packages):
    """Issue a warning if none of the packages is available."""
    errors = []
    for package in packages:
        try:
            __import__(package)
            return True
        except ImportError:
            errors.append(sys.exc_info()[1])
    logging.warn("\n\t".join(["Missing runtime dependencies:"]
                             + [str(e) for e in errors]))
    return False

check_any('dbus')
check_any('gobject')
check_any('pynotify', 'notify2')
check_any('gtk')

# read long_description from README.rst
long_description = None
try:
    long_description = open('README.rst').read()
    long_description += '\n' + open('CHANGES.rst').read()
except IOError:
    pass


theme_base = path.join(sys.prefix, 'share/icons/hicolor')
icon_resolutions = ([('scalable', 'svg')] +
                    [('{0}x{0}'.format(res), 'png') for res in [16]])
icon_classes = {'actions': ('mount', 'unmount',
                            'lock', 'unlock',
                            'eject', 'detach')}

class custom_install(install):
    def run(self):
        install.run(self)
        try:
            # ignore failures since the tray icon is an optional component:
            call(['gtk-update-icon-cache', theme_base])
        except OSError:
            logging.warn(sys.exc_info()[1])

setup(
    name='udiskie',
    version='0.6.4',
    description='Removable disk automounter for udisks',
    long_description=long_description,
    author='Byron Clark',
    author_email='byron@theclarkfamily.name',
    maintainer='Thomas Gläßle',
    maintainer_email='t_glaessle@gmx.de',
    url='https://github.com/coldfix/udiskie',
    license='MIT',
    cmdclass={'install': custom_install},
    packages=[
        'udiskie',
    ],
    data_files=[
        (path.join(theme_base, icon_resolution, icon_class), [
            path.join('icons', icon_resolution, icon_class,
                      'udiskie-%s.%s' % (icon_name, icon_ext))
            for icon_name in icon_names])
        for icon_resolution,icon_ext in icon_resolutions
        for icon_class,icon_names in icon_classes.items()
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
        # 'pygtk>=2.10',
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
