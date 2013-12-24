"""
Udisks wrapper utilities.

These act as a convenience abstraction layer on the udisks dbus service.
Requires Udisks 2.XXX as described here:

    http://udisks.freedesktop.org/docs/XXX

This wraps the dbus API of Udisks2 providing a common interface with the
udisks1 module.

"""
__all__ = ['Udisks']

from udiskie.common import DBusProxy, Emitter
from copy import copy, deepcopy


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

class OfflineProxy(object):
    """
    Provide offline attribute access to a single interface on a dbus object.

    Object properties are accessed statically via table lookup.

    This access method is to be preferred over the dynamic property lookup
    in many cases as it is immune to a number of race conditions.

    """
    def __init__(self, proxy, data):
        """
        Initialize wrapper.

        :param DBusProxy proxy: for dynamic property/method lookup
        :param dict data: for static property lookup

        """
        self.property = AttrDictView(data)
        self.method = proxy.method

class OfflineInterfaceService(object):
    """
    Provide offline attribute access to multiple interfaces on a dbus object.

    Method access is performed dynamically via the given dbus proxy object.

    """
    def __init__(self, proxy, data):
        """
        Store dbus proxy and static property values.

        :param dbus.proxies.ProxyObject proxy: dbus object for method access
        :param dict data: interface and their properties a{sa{sv}}

        """
        self.proxy = proxy
        self.data = data

    def __getattr__(self, key):
        """Return a wrapper for the requested interface."""
        key = UDISKS_INTERFACE + '.' + key
        try:
            return OfflineProxy(DBusProxy(self.proxy, key),
                                self.data[key])
        except:
            return NullProxy(key)

class NoneServer(object):
    """Yield None when asked for any attribute."""
    def __getattr__(self, key):
        return None

class NullProxy(object):
    """Interface not available."""
    def __init__(self, name):
        self.name = name
        self.property = NoneServer()

    def __bool__(self):
        return False

    @property
    def method(self):
        """Access object methods dynamically via dbus."""
        raise RuntimeError("Interface not available: %s" % self.name)


#----------------------------------------
# Device wrapper
#----------------------------------------

class Device(object):
    """
    Wrapper class for dbus API objects representing devices.

    Properties can be resolved dynamically through dbus or via table lookup
    by providing an appropriate interface_service in the constructor. See
    ``OfflineInterfaceService``.

    This class is intended to be used only internally.

    """
    def __init__(self, udisks, object_path, interface_service):
        """
        Initialize an instance with the given dbus proxy object.

        :param Udisks udisks: used to create other Device instances
        :param str object_path: object path of the device
        :param InterfaceService interface_service: used to access dbus API

        """
        self.udisks = udisks
        self.object_path = object_path
        self.I = interface_service

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

    # availability of interfaces
    @property
    def is_valid(self):
        """Check if any interface is available for this object path."""
        return bool(self.I)

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
        return bool(self.I.Drive.property.CanPowerOff)

    @property
    def is_ejectable(self):
        """Check if the drive that owns this device can be ejected."""
        return bool(self.I.Drive.property.Ejectable)

    @property
    def has_media(self):
        """Check if there is media available in the drive."""
        return bool(self.I.Drive.property.MediaAvailable)

    # Drive methods
    def eject(self, options=[]):
        """Eject media from the device."""
        return self.I.Drive.method.Eject(options)

    def detach(self, options=[]):
        """Detach the device by e.g. powering down the physical port."""
        return self.I.Drive.method.PowerOff(options)

    #----------------------------------------
    # Block
    #----------------------------------------

    # Block properties
    @property
    def device_file(self):
        """The filesystem path of the device block file."""
        return tostr(self.I.Block.property.Device)

    @property
    def device_presentation(self):
        """The device file path to present to the user."""
        return tostr(self.I.Block.property.PreferredDevice)

    @property
    def device_size(self):
        """The size of the device in bytes."""
        return self.I.Block.property.Size

    @property
    def id_usage(self):
        """Device usage class, for example 'filesystem' or 'crypto'."""
        return tostr(self.I.Block.property.IdUsage)

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
        return tostr(self.I.Block.property.IdType)

    @property
    def id_label(self):
        """Label of the device if available."""
        return tostr(self.I.Block.property.IdLabel)

    @property
    def id_uuid(self):
        """Device UUID."""
        return tostr(self.I.Block.property.IdUUID)

    @property
    def luks_cleartext_slave(self):
        """Get wrapper to the LUKS crypto device."""
        return self.udisks.create_device(self.I.Block.property.CryptoBackingDevice)

    @property
    def is_luks_cleartext(self):
        """Check whether this is a luks cleartext device."""
        return bool(self.luks_cleartext_slave)

    @property
    def is_systeminternal(self):
        """Check if the device is internal."""
        return bool(self.I.Block.property.HintSystem)    # FIXME

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
            return self.udisks.create_device(self.I.Block.property.Drive)
        return None

    #----------------------------------------
    # Partition
    #----------------------------------------

    # Partition properties
    @property
    def partition_slave(self):
        """Get the partition slave (container)."""
        return self.udisks.create_device(self.I.Partition.property.Table)

    #----------------------------------------
    # Filesystem
    #----------------------------------------

    # Filesystem properties
    @property
    def is_mounted(self):
        """Check if the device is mounted."""
        return bool(self.I.Filesystem.property.MountPoints)

    @property
    def mount_paths(self):
        """Return list of active mount paths."""
        return list(map(tostr, self.I.Filesystem.property.MountPoints or ()))

    # Filesystem methods
    def mount(self, filesystem=None, options=[]):
        """Mount filesystem."""
        return self.I.Filesystem.method.Mount(filesystem or self.id_type, options)

    def unmount(self, options=[]):
        """Unmount filesystem."""
        return self.I.Filesystem.method.Unmount(options)

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
        return self.I.Encrypted.method.Unlock(password, options)

    def lock(self, options=[]):
        """Lock Luks device."""
        return self.I.Encrypted.method.Lock(options)


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

        NOTE: This does not call sync() automatically at the moment. The
        reason for this is that the Daemon requires sync() to be called
        after it has registered its event handlers.

        """
        super(Udisks, self).__init__(proxy, 'org.freedesktop.DBus.ObjectManager')
        self.bus = bus
        self.devices = {}

    def sync(self):
        """Synchronize state."""
        self.devices = self.method.GetManagedObjects()

    @classmethod
    def create(cls, bus):
        """Connect to the udisks service on the specified bus."""
        return cls(bus, bus.get_object(UDISKS_OBJECT, UDISKS_OBJECT_PATH))

    # instantiation of device objects
    def create_device(self, object_path):
        """Create a Device instance from object path."""
        if object_path in self.devices:
            interface_service = OfflineInterfaceService(
                self.bus.get_object(UDISKS_OBJECT, object_path),
                self.devices.get(object_path))
            return Device(self, object_path, interface_service)
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

class Daemon(Emitter):
    """
    Listen to state changes to provide automatic synchronization.

    """
    def __init__(self, udisks):
        """Initialize object and start listening to udisks events."""
        event_names = (stem + suffix
                       for suffix in ('ed',)
                       for stem in (
                           'device_add',
                           'device_remov',
                           'device_mount',
                           'device_unmount',
                           'media_add',
                           'media_remov',
                           'device_unlock',
                           'device_lock',
                           'device_chang', ))
        super(Daemon, self).__init__(event_names)

        self.udisks = udisks
        self.bus = udisks.bus

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
            self._properties_changed,
            signal_name='PropertiesChanged',
            dbus_interface='org.freedesktop.DBus.Properties',
            bus_name=UDISKS_OBJECT,
            path_keyword='object_path')
        self.bus.add_signal_receiver(
            self._job_completed,
            signal_name='Completed',
            dbus_interface='org.freedesktop.UDisks2.Job',
            bus_name=UDISKS_OBJECT,
            path_keyword='job_name')
        udisks.sync()

    @property
    def devices(self):
        return self.udisks.devices

    def _detect_toggle(self, property_name, old, new, add_name, del_name):
        old_valid = old and bool(getattr(old, property_name))
        new_valid = new and bool(getattr(new, property_name))
        if new_valid and not old_valid:
            self.trigger(add_name, new)
        elif old_valid and not new_valid:
            self.trigger(del_name, new)

    def _detect_media_and_mount(self, old_device_state, new_device_state, *interfaces):
        if 'org.freedesktop.UDisks2.Filesystem' in interfaces:
            self._detect_toggle('mount_paths',
                                old_device_state, new_device_state,
                                'device_mounted', 'device_unmounted')
        if 'org.freedesktop.UDisks2.Drive' in interfaces:
            self._detect_toggle('has_media',
                                old_device_state, new_device_state,
                                'media_inserted', 'media_removed')

    def _interfaces_added(self, object_path, interfaces_and_properties):
        """Internal method."""
        old_device_state = self.udisks.create_device(object_path)
        added = object_path not in self.devices
        # TODO: are all interfaces passed or only the new ones?
        self.devices[object_path] = interfaces_and_properties
        new_device_state = self.udisks.create_device(object_path)
        self._detect_media_and_mount(old_device_state, new_device_state,
                                     *interfaces_and_properties.keys())
        if added:
            udevice = self.udisks.create_device(object_path)
            self.trigger('device_added', udevice)
            ciphertext_device = udevice.luks_cleartext_slave
            if ciphertext_device:
                # TODO: add cleartext_holder(==udevice) to event signature?
                self.trigger('device_unlocked', ciphertext_device)

    def _interfaces_removed(self, object_path, interfaces):
        """Internal method."""
        old_device_state = self.udisks.create_device(object_path)
        # copy data in order not to invalidate old_device_state
        self.devices[object_path] = copy(self.devices[object_path])
        for interface in interfaces:
            del self.devices[object_path][interface]
        new_device_state = self.udisks.create_device(object_path)
        self._detect_media_and_mount(old_device_state, new_device_state,
                                     *interfaces)
        if not self.devices[object_path]:
            del self.devices[object_path]
            # FIXME: the event handler signature is inconsistent with the
            # corresponding signal in the udisks1 module. Here we pass the
            # old state of the device which makes it a lot easier to
            # implement a useful response.
            self.trigger('device_removed', old_device_state)
            ciphertext_device = old_device_state.luks_cleartext_slave
            if ciphertext_device and not ciphertext_device.is_unlocked:
                self.trigger('device_locked', ciphertext_device)

    def _properties_changed(self,
                            interface_name,
                            changed_properties,
                            invalidated_properties,
                            object_path):
        """
        Internal method.

        Called when a DBusProperty of any managed object changes.

        """
        try:
            # copy data in order to avoid conflicts with old_device_state
            data = deepcopy(self.devices[object_path])
        except KeyError:
            # for objects that are not managed by the UDisks daemon
            return

        old_device_state = self.udisks.create_device(object_path)
        # update device state:
        for property_name in invalidated_properties:
            del data[interface_name][property_name]
        for key,value in changed_properties.items():
            data[interface_name][key] = value
        self.devices[object_path] = data
        new_device_state = self.udisks.create_device(object_path)
        self._detect_media_and_mount(old_device_state, new_device_state,
                                     interface_name)
        # FIXME: how to wait for the task to finish before triggering the
        # signal?

    def _job_completed(self, success, message, job_name):
        """
        Internal method.

        Called when a job of a long running task completes.

        """
        # FIXME: the event is triggered twice (the first time in
        # _properties_changed)
        event_mapping = {
            'filesystem-mount': 'device_mount',
            'filesystem-unmount': 'device_unmount',
            'encrypted-unlock': 'device_unlock',
            'encrypted-lock': 'device_lock' }
        job = DBusProperties(self.bus.get_object(UDISKS_OBJECT, job_name),
                             'org.freedesktop.UDisks2.Job')
        job_id = job.Operation
        event_name = event_mapping[job_id]
        for object_path in job.Objects:
            dev = self.udisks.create_device(object_path)
            self.trigger(event_name + 'ed', dev)
