import logging
import os
import dbus

DBUS_PROPS_INTERFACE = 'org.freedesktop.DBus.Properties'
UDISKS_INTERFACE = 'org.freedesktop.UDisks'
UDISKS_DEVICE_INTERFACE = 'org.freedesktop.UDisks.Device'

UDISKS_OBJECT = 'org.freedesktop.UDisks'
UDISKS_OBJECT_PATH = '/org/freedesktop/UDisks'

class DbusProperties:
    """
    Dbus property map abstraction.

    Properties of the object can be accessed as attributes.

    """
    def __init__(self, dbus_object, interface):
        """Initialize a proxy object with standard dbus property interface."""
        self.__proxy = dbus.Interface(
                dbus_object,
                dbus_interface=DBUS_PROPS_INTERFACE)
        self.__interface = interface

    def __getattr__(self, property):
        """Retrieve the property via the dbus proxy."""
        return self.__proxy.Get(self.__interface, property)

class Device:
    def __init__(self, bus, device_path):
        self.log = logging.getLogger('udiskie.device.Device')
        self.bus = bus
        self.device_path = device_path
        self.device = self.bus.get_object(UDISKS_OBJECT, device_path)
        self.property = DbusProperties(self.device, UDISKS_DEVICE_INTERFACE)

    def __str__(self):
        return self.device_path

    def partition_slave(self):
        """Get the partition slave."""
        return self.property.PartitionSlave

    def is_partition_table(self):
        """Check if the device is a partition table."""
        return self.property.DeviceIsPartitionTable

    def is_systeminternal(self):
        """Check if the device is internal."""
        return self.property.DeviceIsSystemInternal

    def is_handleable(self):
        """
        Should this device be handled by udiskie?

        Currently this just means that the device is removable and holds a
        filesystem or the device is a LUKS encrypted volume.

        """
        return (self.is_filesystem() or self.is_crypto()) and not self.is_systeminternal()

    def is_mounted(self):
        """Check if the device is mounted."""
        return self.property.DeviceIsMounted

    def is_unlocked(self):
        """Check if device is already unlocked."""
        return self.is_luks() and self.luks_cleartext_holder()

    def mount_paths(self):
        raw_paths = self.property.DeviceMountPaths
        return [os.path.normpath(path) for path in raw_paths]

    def device_file(self):
        return os.path.normpath(self.property.DeviceFile)

    def is_filesystem(self):
        return self.property.IdUsage == 'filesystem'

    def is_crypto(self):
        return self.property.IdUsage == 'crypto'

    def is_luks(self):
        return self.property.DeviceIsLuks

    def is_luks_cleartext(self):
        """Check whether this is a luks cleartext device."""
        return self.property.DeviceIsLuksCleartext

    def luks_cleartext_slave(self):
        """Get luks crypto device."""
        return self.property.LuksCleartextSlave

    def luks_cleartext_holder(self):
        """Get unlocked luks cleartext device."""
        return self.property.LuksHolder

    def is_luks_cleartext_slave(self):
        """Check whether the luks device is currently in use."""
        if not self.is_luks():
            return False
        for device in get_all(self.bus):
            if (not device.is_filesystem() or device.is_mounted()) and (
                    device.is_luks_cleartext() and
                    device.luks_cleartext_slave() == self.device_path):
                return True
        return False

    def has_media(self):
        return self.property.DeviceIsMediaAvailable

    def id_type(self):
        return self.property.IdType

    def id_uuid(self):
        return self.property.IdUuid

    def mount(self, filesystem, options):
        self.device.FilesystemMount(filesystem, options,
                                    dbus_interface=UDISKS_DEVICE_INTERFACE)

    def unmount(self):
        self.device.FilesystemUnmount([], dbus_interface=UDISKS_DEVICE_INTERFACE)

    def lock(self, options):
        """Lock Luks device."""
        return self.device.LuksLock(options,
                                    dbus_interface=UDISKS_DEVICE_INTERFACE)

    def unlock(self, password, options):
        """Unlock Luks device."""
        return self.device.LuksUnlock(password, options,
                               dbus_interface=UDISKS_DEVICE_INTERFACE)



def get_all(bus):
    udisks = bus.get_object(UDISKS_OBJECT, UDISKS_OBJECT_PATH)
    for path in udisks.EnumerateDevices(dbus_interface=UDISKS_INTERFACE):
        yield Device(bus, path)

def get_device(bus, path):
    logger = logging.getLogger('udiskie.device.get_device')
    for device in get_all(bus):
        if os.path.samefile(path, device.device_file()):
            return device
        for p in device.mount_paths():
            if os.path.samefile(path, p):
                return device
    logger.warn('Device not found: %s' % path)
    return None

