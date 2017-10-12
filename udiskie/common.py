"""
Common DBus utilities.
"""

import os.path


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


class BaseDevice(object):

    def __str__(self):
        """Show as object_path."""
        return self.object_path

    def __eq__(self, other):
        """Comparison by object_path."""
        return self.object_path == str(other)

    def __ne__(self, other):
        """Comparison by object_path."""
        return not (self == other)

    def is_file(self, path):
        """Comparison by mount and device file path."""
        return (samefile(path, self.device_file) or
                samefile(path, self.loop_file) or
                any(samefile(path, mp) for mp in self.mount_paths) or
                sameuuid(path, self.id_uuid) or
                sameuuid(path, self.partition_uuid))

    # ----------------------------------------
    # derived properties
    # ----------------------------------------

    @property
    def mount_path(self):
        """Return any mount path."""
        try:
            return self.mount_paths[0]
        except IndexError:
            return ''

    @property
    def in_use(self):
        """Check whether this device is in use, i.e. mounted or unlocked."""
        if self.is_mounted or self.is_unlocked:
            return True
        if self.is_partition_table:
            for device in self._daemon:
                if device.partition_slave == self and device.in_use:
                    return True
        return False

    @property
    def ui_id_label(self):
        """Label of the unlocked partition or the device itself."""
        return (self.luks_cleartext_holder or self).id_label

    @property
    def ui_id_uuid(self):
        """UUID of the unlocked partition or the device itself."""
        return (self.luks_cleartext_holder or self).id_uuid

    @property
    def ui_device_presentation(self):
        """Path of the crypto backing device or the device itself."""
        return (self.luks_cleartext_slave or self).device_presentation

    @property
    def ui_label(self):
        """UI string identifying the partition if possible."""
        return ': '.join(filter(None, [
            self.ui_device_presentation,
            self.ui_id_label or self.ui_id_uuid or self.drive_label
        ]))

    @property
    def ui_device_label(self):
        """UI string identifying the device (drive) if toplevel."""
        return ': '.join(filter(None, [
            self.ui_device_presentation,
            self.loop_file or
            self.drive_label or self.ui_id_label or self.ui_id_uuid
        ]))

    @property
    def drive_label(self):
        """Return drive label."""
        return ' '.join(filter(None, [
            self.drive_vendor,
            self.drive_model,
        ]))


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
    setup_by_uid = -1
    autoclear = None

    def delete(self, auth_no_user_interaction=None):
        raise RuntimeError("Cannot call methods on invalid device!")

    def set_autoclear(self, value, auth_no_user_interaction=None):
        raise RuntimeError("Cannot call methods on invalid device!")

    loop_support = False

    # derived properties
    mount_path = ''
    in_use = False
    ui_id_label = ''
    ui_id_uuid = ''
    ui_device_presentation = ''
    ui_label = '(invalid device)'
    ui_device_label = ''
    drive_label = ''
    parent_object_path = '/'
    can_add = False
    can_remove = False


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
