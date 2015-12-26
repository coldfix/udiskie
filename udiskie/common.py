"""
Common DBus utilities.
"""

from __future__ import absolute_import
from __future__ import unicode_literals

import os.path
import traceback


__all__ = [
    'wraps',
    'check_call',
    'Emitter',
    'samefile',
    'setdefault',
    'extend',
    'cachedproperty',
    'decode_ay',
    # dealing with py2 strings:
    'str2unicode',
    'exc_message',
    'format_exc',
]


try:
    from black_magic.decorator import wraps
except ImportError:
    from functools import wraps


def check_call(exc_type, func, *args):
    try:
        func(*args)
        return True
    except exc_type:
        return False


class Emitter(object):

    """
    Event emitter class.

    Provides a simple event engine featuring a known finite set of events.
    """

    def __init__(self, event_names=(), *args, **kwargs):
        """
        Initialize with empty lists of event handlers.

        :param iterable event_names: names of known events.
        """
        super(Emitter, self).__init__(*args, **kwargs)
        self._event_handlers = {}
        for evt in event_names:
            self._event_handlers[evt] = []

    def trigger(self, event, *args):
        """
        Trigger event handlers.

        :param str event: event name
        :param *args: event parameters
        """
        for handler in self._event_handlers[event]:
            handler(*args)

    def connect(self, event, handler):
        """
        Connect an event handler.

        :param str event: event name
        :param callable handler: event handler
        """
        self._event_handlers[event].append(handler)

    def disconnect(self, event, handler):
        """
        Disconnect an event handler.

        :param str event: event name
        :param callable handler: event handler
        """
        self._event_handlers[event].remove(handler)


def samefile(a, b):
    """Check if two pathes represent the same file."""
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.normpath(a) == os.path.normpath(b)


def setdefault(self, other):
    """
    Merge two dictionaries like .update() but don't overwrite values.

    :param dict self: updated dict
    :param dict other: default values to be inserted
    """
    for k, v in other.items():
        self.setdefault(k, v)


def extend(a, b):
    """Merge two dicts and return a new dict. Much like subclassing works."""
    res = a.copy()
    res.update(b)
    return res


def cachedproperty(func):
    """A memoize decorator for class properties."""
    key = '_' + func.__name__
    @wraps(func)
    def get(self):
        try:
            return getattr(self, key)
        except AttributeError:
            val = func(self)
            setattr(self, key, val)
            return val
    return property(get)


# ----------------------------------------
# udisks.Device helper classes
# ----------------------------------------

class AttrDictView(object):

    """Provide attribute access view to a dictionary."""

    def __init__(self, data):
        self.__data = data

    def __getattr__(self, key):
        try:
            return self.__data[key]
        except KeyError:
            raise AttributeError


# ----------------------------------------
# byte array to string conversion
# ----------------------------------------

try:
    unicode
except NameError:
    unicode = str


def decode_ay(ay):
    """Convert binary blob from DBus queries to strings."""
    if ay is None:
        return ''
    elif isinstance(ay, unicode):
        return ay
    elif isinstance(ay, bytes):
        return ay.decode('utf-8')
    else:
        # dbus.Array([dbus.Byte]) or any similar sequence type:
        return bytearray(ay).rstrip(bytearray((0,))).decode('utf-8')


def str2unicode(arg):
    """Decode python2 strings (bytes) to unicode."""
    if isinstance(arg, list):
        return [str2unicode(s) for s in arg]
    if isinstance(arg, bytes):
        return arg.decode('utf-8')
    return arg


def exc_message(exc):
    """Get an exception message."""
    message = getattr(exc, 'message', None)
    return str2unicode(message or str(exc))


def format_exc():
    return str2unicode(traceback.format_exc())
