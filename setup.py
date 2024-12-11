from setuptools import setup, Command
from distutils.command.build import build as orig_build
from distutils.command.install import install as orig_install

from subprocess import call
import logging
from os import path
from glob import glob


completions_zsh = glob('completions/zsh/_*')
completions_bash = glob('completions/bash/*')
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
            po_file = 'lang/{}.po'.format(lang)
            mo_file = 'build/locale/{}/LC_MESSAGES/udiskie.mo'.format(lang)
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


setup(
    cmdclass={
        'build': build,
        'build_mo': build_mo,
        # Using distutils' install command because:
        # - distutils installs data files to the correct location
        # - distutils correctly calls "build" before "install"
        'install': orig_install,
    },
    data_files=[
        ('share/bash-completion/completions', completions_bash),
        ('share/zsh/site-functions', completions_zsh),
        *[('share/locale/{}/LC_MESSAGES'.format(lang),
           ['build/locale/{}/LC_MESSAGES/udiskie.mo'.format(lang)])
          for lang in languages],
    ],
)
