"""
Compatibility layer for python2/python3.
"""

from __future__ import absolute_import
from __future__ import unicode_literals

try:                    # python2
    basestring = basestring
    unicode = unicode
except NameError:       # python3
    basestring = str
    unicode = str
