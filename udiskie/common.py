"""
Common utilities.
"""

import os.path
import sys
import traceback


__all__ = [
    'wraps',
    'check_call',
    'Emitter',
    'samefile',
    'sameuuid',
    'setdefault',
    'extend',
    'decode_ay',
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


def sameuuid(a, b):
    """Compare two UUIDs."""
    return a and b and a.lower() == b.lower()


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


class ObjDictView(object):

    """Provide dict-like access view to the attributes of an object."""

    def __init__(self, object, valid=None):
        self._object = object
        self._valid = valid

    def __getitem__(self, key):
        if self._valid is None or key in self._valid:
            try:
                return getattr(self._object, key)
            except AttributeError:
                raise KeyError(key)
        raise KeyError("Unknown key: {}".format(key))


class DaemonBase(object):

    active = False

    def activate(self):
        udisks = self._mounter.udisks
        for event, handler in self.events.items():
            udisks.connect(event, handler)
        self.active = True

    def deactivate(self):
        udisks = self._mounter.udisks
        for event, handler in self.events.items():
            udisks.disconnect(event, handler)
        self.active = False


# ----------------------------------------
# byte array to string conversion
# ----------------------------------------

def decode_ay(ay):
    """Convert binary blob from DBus queries to strings."""
    if ay is None:
        return ''
    elif isinstance(ay, str):
        return ay
    elif isinstance(ay, bytes):
        return ay.decode('utf-8')
    else:
        # dbus.Array([dbus.Byte]) or any similar sequence type:
        return bytearray(ay).rstrip(bytearray((0,))).decode('utf-8')


def exc_message(exc):
    """Get an exception message."""
    message = getattr(exc, 'message', None)
    return message or str(exc)


def format_exc(*exc_info):
    """Show exception with traceback."""
    typ, exc, tb = exc_info or sys.exc_info()
    error = traceback.format_exception(typ, exc, tb)
    return "".join(error)
