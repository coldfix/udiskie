from setuptools import setup, Command
from setuptools.command.install import install as orig_install
from distutils.command.build import build as orig_build

from subprocess import call
import logging
from os import path
from glob import glob

import fastentrypoints
fastentrypoints.monkey_patch()


comp_files = glob('completions/_*')
icon_files = glob('icons/scalable/actions/udiskie-*.svg')
languages  = [path.splitext(path.split(po_file)[1])[0]
              for po_file in glob('lang/*.po')]


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
        for lang in languages:
            po_file = path.join('lang', lang + '.po')
            mo_file = path.join('build/locale', lang, 'LC_MESSAGES/udiskie.mo')
            self.mkpath(path.dirname(mo_file))
            self.make_file(
                po_file, mo_file, self.make_mo,
                [po_file, mo_file])

    def make_mo(self, po_filename, mo_filename):
        """Create a machine object (.mo) from a portable object (.po) file."""
        try:
            call(['msgfmt', po_filename, '-o', mo_filename])
        except OSError as e:
            # ignore failures since i18n support is optional:
            logging.warning(e)


# NOTE: Subclassing the setuptools install command alters its behaviour to use
# the distutils code. This is due to some really odd call-context checks in
# the setuptools command.
#
# In fact this is desirable because distutils (correctly) installs data files
# to `sys.prefix` whereas setuptools by default installs to the egg folder
# (which is pretty much useless) and doesn't invoke build commands before
# install. The only real drawback with the distutils behaviour is that it does
# not automatically install dependencies, but we can easily live with that.
#
# Note further that we need to subclass the *setuptools* install command
# rather than the *distutils* one to prevent errors when installing with pip
# from the source distribution.
class install(orig_install):

    """Custom install command used to update the gtk icon cache."""

    def run(self):
        """
        Perform old-style (distutils) install, then update GTK icon cache.

        Extends ``distutils.command.install.install.run``.
        """
        orig_install.run(self)
        try:
            call(['gtk-update-icon-cache', 'share/icons/hicolor'])
        except OSError as e:
            # ignore failures since the tray icon is an optional component:
            logging.warning(e)


data_files = [
    (path.join('share/locale', lang, 'LC_MESSAGES'),
     [path.join('build/locale', lang, 'LC_MESSAGES/udiskie.mo')])
    for lang in languages
]

data_files += [
    ('share/icons/hicolor/scalable/actions', icon_files),
    ('share/zsh/site-functions', comp_files),
]

setup(
    cmdclass={
        'install': install,
        'build': build,
        'build_mo': build_mo,
    },
    data_files=data_files,
)
