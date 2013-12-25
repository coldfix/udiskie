"""
Udisks wrapper utilities.

These act as a convenience abstraction layer on the udisks dbus service.
Requires Udisks 2.XXX as described here:

    http://udisks.freedesktop.org/docs/XXX

This wraps the dbus API of Udisks2 providing a common interface with the
udisks1 module.

"""
__all__ = ['Udisks']

import logging
from udiskie.common import DBusProxy, DBusProperties, Emitter, DBusException
from copy import copy, deepcopy


#----------------------------------------
# udisks object paths and interface names
#----------------------------------------

UDISKS_INTERFACE = 'org.freedesktop.UDisks2'
UDISKS_OBJECT = 'org.freedesktop.UDisks2'
UDISKS_OBJECT_PATH = '/org/freedesktop/UDisks2'

def object_kind(object_path):
    try:
        return {
            'block_devices': 'device',
            'drives': 'drive',
            'jobs': 'job',
        }.get(object_path.split('/')[4])
    except IndexError:
        return None

def filter_opt(opt):
    return {k: v for k,v in opt.items() if v is not None} 

#----------------------------------------
# byte array to string conversion
#----------------------------------------

try:
    unicode
except AttributeError:
    unicode = str

def decode(ay):
    """Convert data from dbus queries to strings."""
    if ay is None:
        return ''
    elif isinstance(ay, unicode):
        return ay
    elif isinstance(ay, bytes):
        return ay.decode('utf-8')
    else: # dbus.Array([dbus.Byte]) or any similar sequence type:
        return b''.join(map(chr, ay)).rstrip(chr(0)).decode('utf-8')

def encode(s):
    """Convert data from dbus queries to strings."""
    if s is None:
        return b''
    elif isinstance(s, unicode):
        return s.encode('utf-8')
    else:
        return s

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
            return NullProxy(key, self.proxy.object_path)

class NoneServer(object):
    """Yield None when asked for any attribute."""
    def __getattr__(self, key):
        return None

class NullProxy(object):
    """Interface not available."""
    def __init__(self, name, object_path):
        self.object_path = object_path
        self.name = name
        self.property = NoneServer()

    def __nonzero__(self):
        return False

    @property
    def method(self):
        """Access object methods dynamically via dbus."""
        raise RuntimeError("Interface '%s' not available for %s" % (self.name, self.object_path))


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
    Exception = DBusException

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
    def is_toplevel(self):
        return not self.is_partition and not self.is_luks_cleartext

    @property
    def _assocdrive(self):
        """
        Return associated drive if this is a top level block device.

        This method is used internally to unify the behaviour of top level
        devices in udisks1 and udisks2.

        """
        return self.drive if self.is_toplevel else self

    @property
    def is_detachable(self):
        """Check if the drive that owns this device can be detached."""
        return bool(self._assocdrive.I.Drive.property.CanPowerOff)

    @property
    def is_ejectable(self):
        """Check if the drive that owns this device can be ejected."""
        return bool(self._assocdrive.I.Drive.property.Ejectable)

    @property
    def has_media(self):
        """Check if there is media available in the drive."""
        return bool(self._assocdrive.I.Drive.property.MediaAvailable)

    # Drive methods
    def eject(self, auth_no_user_interaction=None):
        """Eject media from the device."""
        return self._assocdrive.I.Drive.method.Eject(filter_opt({
            'auth.no_user_interaction': auth_no_user_interaction
        }))

    def detach(self, auth_no_user_interaction=None):
        """Detach the device by e.g. powering down the physical port."""
        return self._assocdrive.I.Drive.method.PowerOff(filter_opt({
            'auth.no_user_interaction': auth_no_user_interaction
        }))

    #----------------------------------------
    # Block
    #----------------------------------------

    # Block properties
    @property
    def device_file(self):
        """The filesystem path of the device block file."""
        return decode(self.I.Block.property.Device)

    @property
    def device_presentation(self):
        """The device file path to present to the user."""
        return decode(self.I.Block.property.PreferredDevice)

    @property
    def device_size(self):
        """The size of the device in bytes."""
        return self.I.Block.property.Size

    @property
    def id_usage(self):
        """Device usage class, for example 'filesystem' or 'crypto'."""
        return decode(self.I.Block.property.IdUsage)

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
        return decode(self.I.Block.property.IdType)

    @property
    def id_label(self):
        """Label of the device if available."""
        return decode(self.I.Block.property.IdLabel)

    @property
    def id_uuid(self):
        """Device UUID."""
        return decode(self.I.Block.property.IdUUID)

    @property
    def luks_cleartext_slave(self):
        """Get wrapper to the LUKS crypto device."""
        return self.udisks.create_device(
            self.I.Block.property.CryptoBackingDevice)

    @property
    def is_luks_cleartext(self):
        """Check whether this is a luks cleartext device."""
        return bool(self.luks_cleartext_slave)

    @property
    def is_external(self):
        """Check if the device is external."""
        # NOTE: udisks2 seems to guess incorrectly in some cases. This
        # leads to HintSystem=True for unlocked devices. In order to show
        # the device anyway, it needs to be recursively checked if any
        # parent device is recognized as external:
        return (not bool(self.I.Block.property.HintSystem) or
                (self.is_luks_cleartext and self.luks_cleartext_slave.is_external) or
                (self.is_partition and self.partition_slave.is_external))

    @property
    def is_systeminternal(self):
        """Check if the device is internal."""
        return not self.is_external

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
        return list(map(decode, self.I.Filesystem.property.MountPoints or ()))

    # Filesystem methods
    def mount(self,
              fstype=None,
              options=None,
              auth_no_user_interaction=None):
        """Mount filesystem."""
        return self.I.Filesystem.method.Mount(filter_opt({
            'fstype': fstype,
            'options': options,
            'auth.no_user_interaction': auth_no_user_interaction
        }))

    def unmount(self, force=None, auth_no_user_interaction=None):
        """Unmount filesystem."""
        return self.I.Filesystem.method.Unmount(filter_opt({
            'force': force,
            'auth.no_user_interaction': auth_no_user_interaction
        }))

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

    # Encrypted methods
    def unlock(self, password, auth_no_user_interaction=None):
        """Unlock Luks device."""
        object_path = self.I.Encrypted.method.Unlock(password, filter_opt({
            'auth.no_user_interaction': auth_no_user_interaction
        }))
        # udisks may not have processed the InterfacesAdded signal yet.
        # Therefore it is necessary to query the interface data directly
        # from the dbus service:
        return self.udisks.create_device(
            object_path,
            self.udisks.method.GetManagedObjects()[object_path])

    def lock(self, auth_no_user_interaction=None):
        """Lock Luks device."""
        return self.I.Encrypted.method.Lock(filter_opt({
            'auth.no_user_interaction': auth_no_user_interaction
        }))

    #----------------------------------------
    # derived properties
    #----------------------------------------

    @property
    def in_use(self):
        """Check whether this device is in use, i.e. mounted or unlocked."""
        if self.is_mounted or self.is_unlocked:
            return True
        if self.is_partition_table:
            for device in self.udisks.get_all():
                if device.partition_slave == self and device.in_use:
                    return True
        return False

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
        self._objects = {}

    def sync(self):
        """Synchronize state."""
        self._objects = self.method.GetManagedObjects()

    @classmethod
    def create(cls, bus):
        """Connect to the udisks service on the specified bus."""
        return cls(bus, bus.get_object(UDISKS_OBJECT, UDISKS_OBJECT_PATH))

    # instantiation of device objects
    def create_device(self, object_path, interfaces_and_properties=None):
        """Create a Device instance from object path."""
        # check this before creating the dbus object for more
        # controlled behaviour:
        if not interfaces_and_properties:
            interfaces_and_properties = self._objects.get(object_path)
            if not interfaces_and_properties:
                return None
        interface_service = OfflineInterfaceService(
            self.bus.get_object(UDISKS_OBJECT, object_path),
            interfaces_and_properties)
        return Device(self, object_path, interface_service)

    # Methods
    def get_all(self):
        """Enumerate all device objects currently known to udisks."""
        return (self.create_device(pth)
                for pth in self._objects
                if object_kind(pth) in ('device', 'drive'))

    def get_device(self, path):
        """
        Get a device proxy by device name or any mount path of the device.

        This searches through all accessible devices and compares device
        path as well as mount pathes.

        """
        import os
        def samefile(a, b):
            try:
                return os.path.samefile(a, b)
            except OSError:
                return os.path.normpath(a) == os.path.normpath(b)
        for device in self.get_all():
            if samefile(device.device_file, path):
                return device
            for p in device.mount_paths:
                if samefile(p, path):
                    return device
        return None

class Daemon(Emitter):
    """
    Listen to state changes to provide automatic synchronization.

    """
    def __init__(self, udisks):
        """Initialize object and start listening to udisks events."""
        event_names = (tuple(stem + suffix
                             for suffix in ('ed','ing')
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
                       + ('object_added',
                          'object_removed'))
        super(Daemon, self).__init__(event_names)

        self.log = logging.getLogger('udiskie.udisks2.Daemon')
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

        self.connect(self._object_added, 'object_added')

    @property
    def _objects(self):
        return self.udisks._objects

    def trigger(self, event, device, *args):
        self.log.debug("+++ %s: %s" % (event, device))
        super(Daemon, self).trigger(event, device, *args)

    def _detect_toggle(self, property_name, old, new, add_name, del_name):
        old_valid = old and bool(getattr(old, property_name))
        new_valid = new and bool(getattr(new, property_name))
        if add_name and new_valid and not old_valid:
            self.trigger(add_name, new)
        elif del_name and old_valid and not new_valid:
            self.trigger(del_name, new)

    # add objects / interfaces
    def _interfaces_added(self, object_path, interfaces_and_properties):
        """Internal method."""
        added = object_path not in self._objects
        self._objects[object_path] = interfaces_and_properties
        if added:
            self.trigger('object_added', object_path)

    def _object_added(self, object_path):
        """Internal event handler."""
        kind = object_kind(object_path)
        if kind in ('device', 'drive'):
            self.trigger('device_added',
                         self.udisks.create_device(object_path))
        elif kind == 'job':
            self._job_changed(object_path, False)

    # remove objects / interfaces
    def _interfaces_removed(self, object_path, interfaces):
        """Internal method."""
        old_state = copy(self._objects[object_path])
        for interface in interfaces:
            del self._objects[object_path][interface]
        new_state = self._objects[object_path]

        if 'org.freedesktop.UDisks2.Drive' in interfaces:
            self._detect_toggle(
                'has_media',
                self.udisks.create_device(object_path, old_state),
                self.udisks.create_device(object_path, new_state),
                None, 'media_removed')

        if not self._objects[object_path]:
            del self._objects[object_path]
            if object_kind(object_path) in ('device', 'drive'):
                self.trigger(
                    'device_removed',
                    self.udisks.create_device(object_path, old_state))

    # change interface properties
    def _properties_changed(self,
                            interface_name,
                            changed_properties,
                            invalidated_properties,
                            object_path):
        """
        Internal method.

        Called when a DBusProperty of any managed object changes.

        """
        # update device state:
        old_state = deepcopy(self._objects[object_path])
        for property_name in invalidated_properties:
            del self._objects[object_path][interface_name][property_name]
        for key,value in changed_properties.items():
            self._objects[object_path][interface_name][key] = value
        new_state = self._objects[object_path]

        if interface_name == 'org.freedesktop.UDisks2.Drive':
            self._detect_toggle(
                'has_media',
                self.udisks.create_device(object_path, old_state),
                self.udisks.create_device(object_path, new_state),
                'media_added', 'media_removed')
        elif interface_name == 'org.freedesktop.UDisks2.Filesystem':
            self._detect_toggle(
                'is_mounted',
                self.udisks.create_device(object_path, old_state),
                self.udisks.create_device(object_path, new_state),
                'device_mounted', None)

    def _job_changed(self, job_name, completed):
        event_mapping = {
            # 'filesystem-mount': 'device_mount',
            'filesystem-unmount': 'device_unmount',
            'encrypted-unlock': 'device_unlock',
            'encrypted-lock': 'device_lock' }
        job = self._objects[job_name]['org.freedesktop.UDisks2.Job']
        event_name = event_mapping.get(job['Operation'])
        if not event_name:
            return
        suffix = 'ed' if completed else 'ing'
        for object_path in job['Objects']:
            device = self.udisks.create_device(object_path)
            self.trigger(event_name + suffix, device)

    def _job_completed(self, success, message, job_name):
        """
        Internal method.

        Called when a job of a long running task completes.

        """
        if success:
            self._job_changed(job_name, True)

