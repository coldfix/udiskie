# encoding: utf-8
from setuptools import setup, Command
from setuptools.command.install import install as orig_install
from distutils.command.install_data import install_data as orig_install_data
from distutils.command.build import build as orig_build
from distutils.util import convert_path

# monkey-patch: use faster entry points!
import fastentrypoints

from subprocess import call
import sys
import logging
from os import path, listdir
from glob import glob
import io

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('DBus', '1.0')
gi.require_version('Notify', '0.7')

# check availability of runtime dependencies
def check_dependency(package, version):
    """Issue a warning if the package is not available."""
    try:
        import gi
        gi.require_version(package.rsplit('.')[-1], version)
        __import__(package)
    except ImportError as e:
        # caused by either of the imports, probably the first
        logging.warn("Missing runtime dependencies:\n\t" + str(e))
    except ValueError as e:
        # caused by the gi.require_version() statement
        logging.warn("Missing runtime dependencies:\n\t" + str(e))
    except RuntimeError as e:
        # caused by the final __import__() statement
        logging.warn("Bad runtime dependency:\n\t" + str(e))


check_dependency('gi.repository.Gio', '2.0')
check_dependency('gi.repository.GLib', '2.0')
check_dependency('gi.repository.Gtk', '3.0')
check_dependency('gi.repository.Notify', '0.7')


# read long_description from README.rst
long_description = None
try:
    long_description = io.open('README.rst', encoding='utf-8').read()
    long_description += '\n' + io.open('CHANGES.rst', encoding='utf-8').read()
except IOError:
    pass


def exec_file(path):
    """Execute a python file and return the `globals` dictionary."""
    namespace = {}
    with open(convert_path(path), 'rb') as f:
        exec(f.read(), namespace, namespace)
    return namespace

metadata = exec_file('udiskie/__init__.py')


# language files
po_source_folder = 'lang'
mo_build_prefix = path.join('build', 'locale')
mo_install_prefix = path.join('share', 'locale')

# completion files
comp_source_folder = 'completions'
comp_install_prefix = path.join('share', 'zsh', 'site-functions')

# menu icons
theme_base = path.join('share', 'icons', 'hicolor')
icon_names = ['mount', 'unmount', 'lock', 'unlock', 'eject', 'detach']


class build(orig_build):
    """Subclass build command to add a subcommand for building .mo files."""
    sub_commands = orig_build.sub_commands + [('build_mo', None)]


class build_mo(Command):

    """Create machine specific translation files (for i18n via gettext)."""

    description = 'Compile .po files into .mo files'

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        for po_filename in glob(path.join(po_source_folder, '*.po')):
            lang = path.splitext(path.split(po_filename)[1])[0]
            mo_filename = path.join(mo_build_prefix, lang,
                                    'LC_MESSAGES', 'udiskie.mo')
            self.mkpath(path.dirname(mo_filename))
            self.make_file(
                po_filename,
                mo_filename,
                self.make_mo,
                [po_filename, mo_filename])

    def make_mo(self, po_filename, mo_filename):
        """Create a machine object (.mo) from a portable object (.po) file."""
        try:
            call(['msgfmt', po_filename, '-o', mo_filename])
        except OSError as e:
            # ignore failures since i18n support is optional:
            logging.warn(e)


# NOTE: we want the install logic from *distutils* rather than the one from
# *setuptools*. distutils does NOT automatically install dependencies. On the
# other hand, setuptools fails to invoke the build commands properly before
# trying to install and it puts the data files in the egg directory (we want
# them in `sys.prefix` or similar).
# NOTE: Subclassing the setuptools install command alters its behaviour to use
# the distutils code. This is due to some really odd call-context checks in
# the setuptools command.
# NOTE: We need to subclass the setuptools install command rather than the
# distutils command to make installing with pip from the source distribution
# work.
class install(orig_install):

    """Custom install command used to update the gtk icon cache."""

    def run(self):
        """
        Perform old-style (distutils) install, then update GTK icon cache.

        Extends ``distutils.command.install.install.run``.
        """
        orig_install.run(self)
        try:
            call(['gtk-update-icon-cache', theme_base])
        except OSError as e:
            # ignore failures since the tray icon is an optional component:
            logging.warn(e)


class install_data(orig_install_data):

    def run(self):
        """Add built translation files and then install data files."""
        self.data_files += [
            (path.join(mo_install_prefix, lang, 'LC_MESSAGES'),
             [path.join(mo_build_prefix, lang, 'LC_MESSAGES', 'udiskie.mo')])
            for lang in listdir(mo_build_prefix)
        ]
        self.data_files += [
            (comp_install_prefix, [
                path.join(comp_source_folder, cmd)
                for cmd in listdir(comp_source_folder)
            ])
        ]
        orig_install_data.run(self)


setup(
    name='udiskie',
    version=metadata['__version__'],
    description=metadata['__summary__'],
    long_description=long_description,
    author=metadata['__author__'],
    author_email=metadata['__author_email__'],
    maintainer=metadata['__maintainer__'],
    maintainer_email=metadata['__maintainer_email__'],
    url=metadata['__uri__'],
    license=metadata['__license__'],
    cmdclass={
        'install': install,
        'install_data': install_data,
        'build': build,
        'build_mo': build_mo,
    },
    packages=[
        'udiskie',
    ],
    data_files=[
        (path.join(theme_base, 'scalable', 'actions'), [
            path.join('icons', 'scalable', 'actions',
                      'udiskie-{0}.svg'.format(icon_name))
            for icon_name in icon_names])
    ],
    entry_points={
        'console_scripts': [
            'udiskie = udiskie.cli:Daemon.main',
            'udiskie-mount = udiskie.cli:Mount.main',
            'udiskie-umount = udiskie.cli:Umount.main',
            'udiskie-info = udiskie.cli:Info.main',
        ],
    },
    install_requires=[
        'PyYAML',
        'docopt',
        # Currently not building out of the box:
        # 'PyGObject',
    ],
    extras_require={
        'password-cache': [
            'keyutils==0.3'
        ],
    },
    tests_require=[
    ],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Environment :: X11 Applications :: GTK',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'License :: OSI Approved :: MIT License',
        'Topic :: Desktop Environment',
        'Topic :: Software Development',
        'Topic :: System :: Filesystems',
        'Topic :: System :: Hardware',
        'Topic :: Utilities',
    ],
)
