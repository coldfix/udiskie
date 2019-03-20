"""
Monkey patch setuptools to write faster console_scripts.

NOTE: `pip install` already does the right thing (at least for pip 19.0)
without our help, but this is still needed for setuptools install, i.e.
``python setup.py install`` or develop.
"""

TEMPLATE = r'''
# encoding: utf-8
import sys
from {ep.module_name} import {ep.attrs[0]}

if __name__ == '__main__':
    sys.exit({func}())
'''.lstrip()


class ScriptTemplate(str):
    def __mod__(self, context):
        func = '.'.join(context['ep'].attrs)
        return self.format(func=func, **context)


def monkey_patch():
    from setuptools.command import easy_install
    easy_install.ScriptWriter.template = ScriptTemplate(TEMPLATE)
