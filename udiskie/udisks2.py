"""
Udisks wrapper utilities.

These act as a convenience abstraction layer on the udisks dbus service.
Requires Udisks 2.XXX as described here:

    http://udisks.freedesktop.org/docs/XXX

This wraps the dbus API of Udisks2 providing a common interface with the
udisks1 module.

"""
__all__ = ['Udisks']

from udiskie.common import DBusProxy


UDISKS_INTERFACE = 'org.freedesktop.UDisks2'
UDISKS_OBJECT = 'org.freedesktop.UDisks2'
UDISKS_OBJECT_PATH = '/org/freedesktop/UDisks2'


#----------------------------------------
# byte array to string conversion
#----------------------------------------

def tostr(ay):
    """Convert data from dbus queries to strings."""
    if ay is None:
        return ''
    elif isinstance(ay, str):
        return ay
    elif isinstance(ay, bytes):
        return ay.decode('utf-8')
    else: # dbus.Array([dbus.Byte]) or any similar sequence type:
        return b''.join(map(chr, ay)).rstrip(chr(0)).decode('utf-8')

#----------------------------------------
# Internal helper classes
#----------------------------------------

class AttrDictView(object):
    """Provide attribute access view to a dictionary."""
    def __init__(self, data):
        self.__data = data

    def __getattr__(self, key):
        try:
            return self.__data[key]
        except KeyError:
            raise AttributeError

class DeviceInterface(object):
    """Provide attribute access to a single interface on a dbus object."""
    def __init__(self, proxy, data):
        """
        Initialize wrapper.

        :param DBusProxy proxy: for dynamic property/method lookup
        :param dict data: for static property lookup

        """
        self.proxy = proxy
        self.data = data

    @property
    def t(self):
        """
        Access object properties statically via table lookup.

        This access method is to be preferred over the dynamic property
        lookup in most cases as it is immune to a number of race
        conditions.

        """
        return AttrDictView(self.data)

    @property
    def p(self):
        """Access object properties dynamically via dbus."""
        return self.proxy.property

    @property
    def m(self):
        """Access object methods dynamically via dbus."""
        return self.proxy.method

class NoneServer(object):
    """Yield None when asked for any attribute."""
    def __getattr__(self, key):
        return None

class NullInterface(object):
    """Interface not available."""
    def __init__(self, name):
        self.name = name

    def __bool__(self):
        return False

    @property
    def t(self):
        """Access object properties statically via table lookup."""
        return NoneServer()

    @property
    def p(self):
        """Access object properties dynamically via dbus."""
        raise RuntimeError("Interface not available: %s" % self.name)

    @property
    def m(self):
        """Access object methods dynamically via dbus."""
        raise RuntimeError("Interface not available: %s" % self.name)


#----------------------------------------
# Device wrapper
#----------------------------------------

class Device(object):
    """
    Wrapper class for dbus objects representing devices.

    The property read access is provided via static table lookup. The
    methods use

    """
    def __init__(self, udisks, object_path):
        """
        Initialize an instance with the given dbus proxy object.

        proxy must be an object acquired by a call to bus.get_object().

        """
        self.udisks = udisks
        self.object = udisks.bus.get_object(UDISKS_OBJECT, object_path)
        self.object_path = object_path

    def __str__(self):
        """Show as object_path."""
        return self.object_path

    def __eq__(self, other):
        """Comparison by object_path."""
        if isinstance(other, Device):
            return self.object_path == other.object_path
        else:
            return self.object_path == str(other)

    def __ne__(self, other):
        """Comparison by object_path."""
        return not (self == other)

    @property
    class I(object):
        """Lookup device interfaces via attribute access."""
        def __init__(self, device):
            self.obj = device.object
            self.tab = device.udisks.devices.get(device.object_path)

        def __getattr__(self, key):
            """Return a wrapper for the requested interface."""
            key = UDISKS_INTERFACE + '.' + key
            try:
                return DeviceInterface(DBusProxy(self.obj, key),
                                       self.tab[key])
            except:
                return NullInterface(key)

    # availability of interfaces
    @property
    def is_valid(self):
        """Check if any interface is available for this object path."""
        return self.object_path in self.udisks.devices

    @property
    def is_drive(self):
        """Check if the device is a drive."""
        return bool(self.I.Drive)

    @property
    def is_block(self):
        """Check if the device is a block device."""
        return bool(self.I.Block)

    @property
    def is_partition_table(self):
        """Check if the device is a partition table."""
        return bool(self.I.PartitionTable)

    @property
    def is_partition(self):
        """Check if the device has a partition slave."""
        return bool(self.I.Partition)

    @property
    def is_filesystem(self):
        """Check if the device is a filesystem."""
        return bool(self.I.Filesystem)

    @property
    def is_luks(self):
        """Check if the device is a LUKS container."""
        return bool(self.I.Encrypted)

    #----------------------------------------
    # Drive
    #----------------------------------------

    # Drive properties
    @property
    def is_detachable(self):
        """Check if the drive that owns this device can be detached."""
        return bool(self.I.Drive.t.CanPowerOff)

    @property
    def is_ejectable(self):
        """Check if the drive that owns this device can be ejected."""
        return bool(self.I.Drive.t.Ejectable)

    @property
    def has_media(self):
        """Check if there is media available in the drive."""
        return bool(self.I.Drive.t.MediaAvailable)

    # Drive methods
    def eject(self, options=[]):
        """Eject media from the device."""
        return self.I.Drive.m.Eject(options)

    def detach(self, options=[]):
        """Detach the device by e.g. powering down the physical port."""
        return self.I.Drive.m.PowerOff(options)

    #----------------------------------------
    # Block
    #----------------------------------------

    # Block properties
    @property
    def device_file(self):
        """The filesystem path of the device block file."""
        return tostr(self.I.Block.t.Device)

    @property
    def device_presentation(self):
        """The device file path to present to the user."""
        return tostr(self.I.Block.t.PreferredDevice)

    @property
    def device_size(self):
        """The size of the device in bytes."""
        return self.I.Block.t.Size

    @property
    def id_usage(self):
        """Device usage class, for example 'filesystem' or 'crypto'."""
        return tostr(self.I.Block.t.IdUsage)

    @property
    def is_crypto(self):
        return self.id_usage == 'crypto'

    @property
    def id_type(self):
        """"
        Return IdType property.

        This field provides further detail on IdUsage, for example:

        IdUsage     'filesystem'    'crypto'
        IdType      'ext4'          'crypto_LUKS'

        """
        return tostr(self.I.Block.t.IdType)

    @property
    def id_label(self):
        """Label of the device if available."""
        return tostr(self.I.Block.t.IdLabel)

    @property
    def id_uuid(self):
        """Device UUID."""
        return tostr(self.I.Block.t.IdUUID)

    @property
    def luks_cleartext_slave(self):
        """Get wrapper to the LUKS crypto device."""
        return self.udisks.create_device(self.I.Block.t.CryptoBackingDevice)

    @property
    def is_luks_cleartext(self):
        """Check whether this is a luks cleartext device."""
        return bool(self.luks_cleartext_slave)

    @property
    def is_systeminternal(self):
        """Check if the device is internal."""
        return bool(self.I.Block.t.HintSystem)    # FIXME

    @property
    def is_external(self):
        """Check if the device is external."""
        return not self.is_systeminternal

    @property
    def drive(self):
        """Get wrapper to the drive containing this device."""
        if self.is_drive:
            return self
        cleartext = self.luks_cleartext_slave
        if cleartext:
            return cleartext.drive
        if self.is_block:
            return self.udisks.create_device(self.I.Block.t.Drive)
        return None

    #----------------------------------------
    # Partition
    #----------------------------------------

    # Partition properties
    @property
    def partition_slave(self):
        """Get the partition slave (container)."""
        return self.udisks.create_device(self.I.Partition.t.Table)

    #----------------------------------------
    # Filesystem
    #----------------------------------------

    # Filesystem properties
    @property
    def is_mounted(self):
        """Check if the device is mounted."""
        return bool(self.I.Filesystem.t.MountPoints)

    @property
    def mount_paths(self):
        """Return list of active mount paths."""
        return list(self.I.Filesystem.t.MountPoints or ())

    # Filesystem methods
    def mount(self, filesystem=None, options=[]):
        """Mount filesystem."""
        return self.I.Filesystem.m.Mount(filesystem or self.id_type, options)

    def unmount(self, options=[]):
        """Unmount filesystem."""
        return self.I.Filesystem.m.Unmount(options)

    #----------------------------------------
    # Encrypted
    #----------------------------------------

    # Encrypted properties
    @property
    def luks_cleartext_holder(self):
        """Get wrapper to the unlocked luks cleartext device."""
        if not self.is_luks:
            return None
        for device in self.udisks.get_all():
            if device.luks_cleartext_slave == self:
                return device
        return None

    @property
    def is_unlocked(self):
        """Check if device is already unlocked."""
        return bool(self.luks_cleartext_holder)

    @property
    def is_luks_cleartext_slave(self):
        """Check whether the luks device is currently in use."""
        return bool(self.luks_cleartext_holder)     # FIXME

    # Encrypted methods
    def unlock(self, password, options=[]):
        """Unlock Luks device."""
        return self.I.Encrypted.m.Unlock(password, options)

    def lock(self, options=[]):
        """Lock Luks device."""
        return self.I.Encrypted.m.Lock(options)


#----------------------------------------
# udisks service wrapper
#----------------------------------------

class Udisks(DBusProxy):
    """
    Udisks dbus service wrapper.

    This is a dbus proxy object to the org.freedesktop.UDisks interface of
    the udisks service object.

    """
    # Construction
    def __init__(self, bus, proxy):
        """
        Initialize an instance with the given dbus proxy object.

        proxy must be an object acquired by a call to bus.get_object().

        """
        super(Udisks, self).__init__(proxy, 'org.freedesktop.DBus.ObjectManager')
        self.bus = bus
        self.devices = {}

    def listen(self):
        """Listen to state changes to provide automatic synchronization."""
        self.bus.add_signal_receiver(
            self._interfaces_added,
            signal_name='InterfacesAdded',
            dbus_interface='org.freedesktop.DBus.ObjectManager',
            bus_name=UDISKS_OBJECT)
        self.bus.add_signal_receiver(
            self._interfaces_removed,
            signal_name='InterfacesRemoved',
            dbus_interface='org.freedesktop.DBus.ObjectManager',
            bus_name=UDISKS_OBJECT)
        self.bus.add_signal_receiver(
            self._job_completed,
            signal_name='Completed',
            dbus_interface='org.freedesktop.UDisks2.Job',
            bus_name=UDISKS_OBJECT,
            sender_keyword='job_name')
        self.sync()

    def _interfaces_added(self, object_path, interfaces_and_properties):
        """Internal method."""
        self.devices[object_path] = interfaces_and_properties

    def _interfaces_removed(self, object_path, interfaces):
        """Internal method."""
        for interface in interfaces:
            del self.devices[object_path][interface]
        if not self.devices[object_path]:
            del self.devices[object_path]

    def _job_completed(self, success, message, job_name):
        obj = DBusProperties(self.bus.get_object(UDISKS_OBJECT, job_name),
                             'org.freedesktop.UDisks2.Job')


    def sync(self):
        """Synchronize state."""
        self.devices = self.method.GetManagedObjects()

    @classmethod
    def create(cls, bus):
        """Connect to the udisks service on the specified bus."""
        udisks = cls(bus, bus.get_object(UDISKS_OBJECT, UDISKS_OBJECT_PATH))
        udisks.sync()
        return udisks

    @classmethod
    def daemon(cls, bus):
        """Connect to the udisks service on the specified bus."""
        udisks = cls(bus, bus.get_object(UDISKS_OBJECT, UDISKS_OBJECT_PATH))
        udisks.listen()
        return udisks

    # instantiation of device objects
    def create_device(self, object_path):
        """Create a Device instance from object path."""
        if object_path in self.devices:
            return Device(self, object_path)
        else:
            return None

    # Methods
    def get_all(self):
        """Enumerate all device objects currently known to udisks."""
        return map(self.create_device, self.devices)

    def get_device(self, path):
        """
        Get a device proxy by device name or any mount path of the device.

        This searches through all accessible devices and compares device
        path as well as mount pathes.

        """
        import os
        samefile = lambda f: f and os.path.samefile(f, path)
        for device in self.get_all():
            if samefile(device.device_file):
                return device
            for p in device.mount_paths:
                if samefile(p):
                    return device
        return None

