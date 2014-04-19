"""
Compatibility layer for python2/python3.
"""

try:                    # python2
    from itertools import ifilter as filter
except ImportError:     # python3
    filter = filter

try:                    # python2
    basestring = basestring
    unicode = unicode
except NameError:       # python3
    basestring = str
    unicode = str
