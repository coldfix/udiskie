"""
Compatibility layer for python2/python3.
"""

from __future__ import absolute_import
from __future__ import unicode_literals

import sys


try:                    # python2
    basestring = basestring
    unicode = unicode
except NameError:       # python3
    basestring = str
    unicode = str


def fix_str_conversions(cls):
    """Enable python2/3 compatible behaviour for __str__."""
    def __bytes__(self):
        return self.__unicode__().encode('utf-8')
    cls.__unicode__ = __unicode__ = cls.__str__
    cls.__bytes__ = __bytes__
    if sys.version_info[0] == 2:
        cls.__str__ = __bytes__
    else:
        cls.__str__ = __unicode__
    return cls
