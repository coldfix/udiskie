# encoding: utf-8
from setuptools import setup
from setuptools.command.install import install
from subprocess import call
import sys
import logging

log = logging.getLogger()

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
    log.warning("\n\t".join(["Missing runtime dependencies:"]
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


theme_base = sys.prefix + '/share/icons/hicolor'
icon_resolutions = ['scalable'] + ['{0}x{0}'.format(res) for res in [16]]
icon_names = {'actions': ('mount', 'unmount',
                          'lock', 'unlock',
                          'eject', 'detach')}
data_files = [
    ("%s/%s/%s" % (theme_base, icon_resolution, icon_type), [
        'icons/%s/%s/udiskie-%s.%s' %
            (icon_resolution, icon_type, icon_name,
            'svg' if icon_resolution == 'scalable' else 'png')
        for icon_name in icon_names[icon_type]])
    for icon_resolution in icon_resolutions
    for icon_type in icon_names
]

class custom_install(install):
    def run(self):
        install.run(self)
        try:
            # ignore failures since the tray icon is an optional component:
            call(['gtk-update-icon-cache', theme_base])
        except OSError:
            log.warning(sys.exc_info()[1])

setup(
    name='udiskie',
    version='0.6.1',
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
    namespace_packages=[
        'udiskie',
    ],
    data_files=data_files,
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
