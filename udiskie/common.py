"""
Common DBus utilities.
"""

from __future__ import absolute_import
from __future__ import unicode_literals

import os.path
import traceback

from .compat import fix_str_conversions


__all__ = [
    'wraps',
    'check_call',
    'Emitter',
    'samefile',
    'sameuuid',
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


@fix_str_conversions
class NullDevice(object):

    """
    Invalid object.

    Evaluates to False in boolean context, but allows arbitrary attribute
    access by returning another Null.
    """

    object_path = '/'

    def __init__(self, **properties):
        """Initialize an instance with the given DBus proxy object."""
        self.__dict__.update(properties)

    def __bool__(self):
        return False

    __nonzero__ = __bool__

    def __str__(self):
        """Display as object path."""
        return self.object_path

    def __eq__(self, other):
        """Comparison by object path."""
        return self.object_path == str(other)

    def __ne__(self, other):
        """Comparison by object path."""
        return not (self == other)

    def is_file(self, path):
        """Comparison by mount and device file path."""
        return False

    # availability of interfaces
    is_drive = False
    is_block = False
    is_partition_table = False
    is_partition = False
    is_filesystem = False
    is_luks = False
    is_loop = False

    # Drive
    is_toplevel = is_drive
    is_detachable = False
    is_ejectable = False
    has_media = False

    def eject(self, unmount=False):
        raise RuntimeError("Cannot call methods on invalid device!")

    def detach(self):
        raise RuntimeError("Cannot call methods on invalid device!")

    # Block
    device_file = ''
    device_presentation = ''
    device_size = 0
    id_usage = ''
    is_crypto = False
    is_ignored = None
    device_id = ''
    id_type = ''
    id_label = ''
    id_uuid = ''

    @property
    def luks_cleartext_slave(self):
        raise AttributeError('Invalid device has no cleartext slave.')

    is_luks_cleartext = False
    is_external = None
    is_systeminternal = None

    @property
    def drive(self):
        raise AttributeError('Invalid device has no drive.')

    root = drive
    should_automount = False
    icon_name = ''
    symbolic_icon_name = icon_name
    symlinks = []

    # Partition
    @property
    def partition_slave(self):
        raise AttributeError('Invalid device has no partition slave.')

    # Filesystem
    is_mounted = False
    mount_paths = ()

    def mount(self,
              fstype=None,
              options=None,
              auth_no_user_interaction=False):
        raise RuntimeError("Cannot call methods on invalid device!")

    def unmount(self, force=False):
        raise RuntimeError("Cannot call methods on invalid device!")

    # Encrypted
    @property
    def luks_cleartext_holder(self):
        raise AttributeError('Invalid device has no cleartext holder.')

    is_unlocked = None

    def unlock(self, password):
        raise RuntimeError("Cannot call methods on invalid device!")

    def lock(self):
        raise RuntimeError("Cannot call methods on invalid device!")

    # Loop
    loop_file = ''

    # derived properties
    in_use = False
    parent_object_path = '/'
    ui_label = '(invalid device)'


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
