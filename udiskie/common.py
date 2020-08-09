"""
Common utilities.
"""

import os.path
import sys
import traceback


__all__ = [
    'wraps',
    'Emitter',
    'samefile',
    'sameuuid',
    'setdefault',
    'extend',
    'cachedproperty',
    'decode_ay',
    'exc_message',
    'format_exc',
]


try:
    from black_magic.decorator import wraps
except ImportError:
    from functools import wraps


class Emitter:

    """Simple event emitter for a known finite set of events."""

    def __init__(self, event_names=(), *args, **kwargs):
        """Initialize with empty lists of event handlers."""
        super().__init__(*args, **kwargs)
        self._event_handlers = {}
        for evt in event_names:
            self._event_handlers[evt] = []

    def trigger(self, event, *args):
        """Trigger event by name."""
        for handler in self._event_handlers[event]:
            handler(*args)

    def connect(self, event, handler):
        """Connect an event handler."""
        self._event_handlers[event].append(handler)

    def disconnect(self, event, handler):
        """Disconnect an event handler."""
        self._event_handlers[event].remove(handler)


def samefile(a: str, b: str) -> bool:
    """Check if two paths represent the same file."""
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.normpath(a) == os.path.normpath(b)


def sameuuid(a: str, b: str) -> bool:
    """Compare two UUIDs."""
    return a and b and a.lower() == b.lower()


def setdefault(self: dict, other: dict):
    """Like .update() but values in self take priority."""
    for k, v in other.items():
        self.setdefault(k, v)


def extend(a: dict, b: dict) -> dict:
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

class AttrDictView:

    """Provide attribute access view to a dictionary."""

    def __init__(self, data):
        self.__data = data

    def __getattr__(self, key):
        try:
            return self.__data[key]
        except KeyError:
            raise AttributeError


class ObjDictView:

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


class DaemonBase:

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


def is_utf8(bs):
    """Check if the given bytes string is utf-8 decodable."""
    try:
        bs.decode('utf-8')
        return True
    except UnicodeDecodeError:
        return False


def exc_message(exc):
    """Get an exception message."""
    message = getattr(exc, 'message', None)
    return message or str(exc)


def format_exc(*exc_info):
    """Show exception with traceback."""
    typ, exc, tb = exc_info or sys.exc_info()
    error = traceback.format_exception(typ, exc, tb)
    return "".join(error)
