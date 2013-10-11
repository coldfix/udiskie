"""
Udisks wrapper utilities.

These act as a convenience abstraction layer on the udisks dbus service.
Requires Udisks 1.0.5 as described here:

    http://udisks.freedesktop.org/docs/1.0.5/

Note that (as this completely wraps the udisks dbus API) replacing this
module will let you support Udisks2 or maybe even other services.

"""
__all__ = ['Device', 'Udisks']

import logging
import os
from udiskie.common import DBusProxy


UDISKS_INTERFACE = 'org.freedesktop.UDisks'
UDISKS_DEVICE_INTERFACE = 'org.freedesktop.UDisks.Device'

UDISKS_OBJECT = 'org.freedesktop.UDisks'
UDISKS_OBJECT_PATH = '/org/freedesktop/UDisks'


class Device(DBusProxy):
    """
    Wrapper class for org.freedesktop.UDisks.Device proxy objects.
    """
    # construction
    def __init__(self, bus, proxy):
        self.log = logging.getLogger('udiskie.udisks.Device')
        super(Device, self).__init__(proxy, UDISKS_DEVICE_INTERFACE)
        self.bus = bus

    @classmethod
    def create(cls, bus, object_path):
        return cls(bus, bus.get_object(UDISKS_OBJECT, object_path))

    # string representation
    def __str__(self):
        return self.object_path

    def __eq__(self, other):
        if isinstance(other, Device):
            return self.object_path == other.object_path
        else:
            return self.object_path == str(other)

    def __ne__(self, other):
        return not (self == other)

    # properties
    @property
    def partition_slave(self):
        """Get the partition slave (container)."""
        return self.property.PartitionSlave if self.is_partition else None

    @property
    def is_partition(self):
        """Check if the device has a partition slave."""
        return self.property.DeviceIsPartition

    @property
    def is_partition_table(self):
        """Check if the device is a partition table."""
        return self.property.DeviceIsPartitionTable

    @property
    def is_drive(self):
        """Check if the device is a drive."""
        return self.property.DeviceIsDrive

    @property
    def drive(self):
        """
        Get the drive that owns this device.

        The returned Device object is not guaranteed to be a drive.

        """
        if self.is_partition:
            return self.create(self.bus, self.partition_slave).drive
        elif self.is_luks_cleartext:
            return self.create(self.bus, self.luks_cleartext_slave).drive
        else:
            return self

    @property
    def is_detachable(self):
        """Check if the drive that owns this device can be detached."""
        return self.property.DriveCanDetach if self.is_drive else None

    @property
    def is_ejectable(self):
        """Check if the drive that owns this device can be ejected."""
        return self.property.DriveIsMediaEjectable if self.is_drive else None

    @property
    def is_systeminternal(self):
        """Check if the device is internal."""
        return self.property.DeviceIsSystemInternal

    @property
    def is_external(self):
        """Check if the device is external."""
        return not self.is_systeminternal

    @property
    def is_handleable(self):
        """
        Should this device be handled by udiskie?

        Currently this just means that the device is removable and holds a
        filesystem or the device is a LUKS encrypted volume.

        """
        return (self.is_filesystem or self.is_crypto) and self.is_external

    @property
    def is_mounted(self):
        """Check if the device is mounted."""
        return self.property.DeviceIsMounted

    @property
    def is_unlocked(self):
        """Check if device is already unlocked."""
        return self.luks_cleartext_holder if self.is_luks else None

    @property
    def mount_paths(self):
        if not self.is_mounted:
            return []
        raw_paths = self.property.DeviceMountPaths
        return [os.path.normpath(path) for path in raw_paths]

    @property
    def device_file(self):
        return os.path.normpath(self.property.DeviceFile)

    @property
    def is_filesystem(self):
        return self.id_usage == 'filesystem'

    @property
    def is_crypto(self):
        return self.id_usage == 'crypto'

    @property
    def is_luks(self):
        return self.property.DeviceIsLuks

    @property
    def is_luks_cleartext(self):
        """Check whether this is a luks cleartext device."""
        return self.property.DeviceIsLuksCleartext

    @property
    def luks_cleartext_slave(self):
        """Get luks crypto device."""
        return self.property.LuksCleartextSlave if self.is_luks_cleartext else None

    @property
    def luks_cleartext_holder(self):
        """Get unlocked luks cleartext device."""
        return self.property.LuksHolder if self.is_luks else None

    @property
    def is_luks_cleartext_slave(self):
        """Check whether the luks device is currently in use."""
        if not self.is_luks:
            return False
        for device in Udisks.create(self.bus).get_all():
            if (not device.is_filesystem or device.is_mounted) and (
                    device.is_luks_cleartext and
                    device.luks_cleartext_slave == self.object_path):
                return True
        return False

    @property
    def has_media(self):
        return self.property.DeviceIsMediaAvailable

    @property
    def id_type(self):
        return self.property.IdType

    @property
    def id_usage(self):
        return self.property.IdUsage

    @property
    def id_uuid(self):
        return self.property.IdUuid

    # methods
    def mount(self, filesystem=None, options=[]):
        if filesystem is None:
            filesystem = self.id_type
        self.method.FilesystemMount(filesystem, options)

    def unmount(self, options=[]):
        self.method.FilesystemUnmount(options)

    def lock(self, options=[]):
        """Lock Luks device."""
        return self.method.LuksLock(options)

    def unlock(self, password, options=[]):
        """Unlock Luks device."""
        return self.method.LuksUnlock(password, options)

    def eject(self, options=[]):
        """Eject media from the device."""
        return self.method.DriveEject(options)

    def detach(self, options=[]):
        """Detach the device by e.g. powering down the physical port."""
        return self.method.DriveDetach(options)


class Udisks(DBusProxy):
    """
    """
    # Construction
    def __init__(self, bus, proxy):
        super(Udisks, self).__init__(proxy, UDISKS_INTERFACE)
        self.bus = bus

    @classmethod
    def create(cls, bus):
        return cls(bus, bus.get_object(UDISKS_OBJECT, UDISKS_OBJECT_PATH))

    # instantiation of device objects
    def create_device(self, object_path):
        """Create a Device instance from object path."""
        return Device.create(self.bus, object_path)

    # Methods
    def get_all(self):
        """Enumerate all device objects currently known to udisks."""
        for path in self.method.EnumerateDevices():
            yield self.create_device(path)

    def get_all_handleable(self):
        """Enumerate all handleable devices currently known to udisks."""
        for device in self.get_all():
            if device.is_handleable:
                yield device

    def get_device(self, path):
        """
        Get a device proxy by device name or any mount path of the device.

        This searches through all accessible devices and compares device
        path as well as mount pathes.

        """
        logger = logging.getLogger('udiskie.udisks.get_device')
        for device in self.get_all():
            if os.path.samefile(path, device.device_file):
                return device
            for p in device.mount_paths:
                if os.path.samefile(path, p):
                    return device
        logger.warn('Device not found: %s' % path)
        return None

