from setuptools import setup, Command
from setuptools.command.install import install as orig_install
from distutils.command.build import build as orig_build

import fastentrypoints          # noqa: F401, import for side-effects!

from subprocess import call
import logging
from os import path
from glob import glob


# language files
po_source_folder = 'lang'
mo_build_prefix = path.join('build', 'locale')
mo_install_prefix = path.join('share', 'locale')

# completion files
comp_source_folder = 'completions'
comp_install_prefix = path.join('share', 'zsh', 'site-functions')

# menu icons
theme_base = path.join('share', 'icons', 'hicolor')


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
            logging.warning(e)


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
            logging.warning(e)


data_files = [
    (path.join(mo_install_prefix, lang, 'LC_MESSAGES'),
     [path.join(mo_build_prefix, lang, 'LC_MESSAGES', 'udiskie.mo')])
    for po_filename in glob(path.join(po_source_folder, '*.po'))
    for lang in [path.splitext(path.split(po_filename)[1])[0]]
]

data_files += [
    (path.join(theme_base, 'scalable', 'actions'),
     glob(path.join('icons', 'scalable', 'actions', 'udiskie-*.svg'))),
    (comp_install_prefix,
     glob(path.join(comp_source_folder, '_*'))),
]

setup(
    cmdclass={
        'install': install,
        'build': build,
        'build_mo': build_mo,
    },
    data_files=data_files,
)
