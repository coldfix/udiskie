"""
Udisks wrapper utilities.

These act as a convenience abstraction layer on the udisks dbus service.
Requires Udisks 1.0.5 as described here:

    http://udisks.freedesktop.org/docs/1.0.5/

Note that (as this completely wraps the udisks dbus API) replacing this
module will let you support Udisks2 or maybe even other services.

"""
__all__ = ['Device', 'get_all', 'get_all_handleable', 'get_device']

import logging
import os
import dbus

from udiskie.common import Properties as DbusProperties


UDISKS_INTERFACE = 'org.freedesktop.UDisks'
UDISKS_DEVICE_INTERFACE = 'org.freedesktop.UDisks.Device'

UDISKS_OBJECT = 'org.freedesktop.UDisks'
UDISKS_OBJECT_PATH = '/org/freedesktop/UDisks'


class Device:
    """
    Wrapper class for org.freedesktop.UDisks.Device proxy objects.
    """
    def __init__(self, bus, device_path):
        self.log = logging.getLogger('udiskie.device.Device')
        self.bus = bus
        self.device_path = device_path
        device_object = self.bus.get_object(UDISKS_OBJECT, device_path)
        self.property = DbusProperties(device_object, UDISKS_DEVICE_INTERFACE)
        self.method = dbus.Interface(device_object, UDISKS_DEVICE_INTERFACE)

    def __str__(self):
        return self.device_path

    # properties
    @property
    def partition_slave(self):
        """Get the partition slave."""
        return self.property.PartitionSlave

    @property
    def is_partition_table(self):
        """Check if the device is a partition table."""
        return self.property.DeviceIsPartitionTable

    @property
    def is_systeminternal(self):
        """Check if the device is internal."""
        return self.property.DeviceIsSystemInternal

    @property
    def is_handleable(self):
        """
        Should this device be handled by udiskie?

        Currently this just means that the device is removable and holds a
        filesystem or the device is a LUKS encrypted volume.

        """
        return (self.is_filesystem or self.is_crypto) and not self.is_systeminternal

    @property
    def is_mounted(self):
        """Check if the device is mounted."""
        return self.property.DeviceIsMounted

    @property
    def is_unlocked(self):
        """Check if device is already unlocked."""
        return self.is_luks and self.luks_cleartext_holder

    @property
    def mount_paths(self):
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
        return self.property.LuksCleartextSlave

    @property
    def luks_cleartext_holder(self):
        """Get unlocked luks cleartext device."""
        return self.property.LuksHolder

    @property
    def is_luks_cleartext_slave(self):
        """Check whether the luks device is currently in use."""
        if not self.is_luks:
            return False
        for device in get_all(self.bus):
            if (not device.is_filesystem or device.is_mounted) and (
                    device.is_luks_cleartext and
                    device.luks_cleartext_slave == self.device_path):
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
    def mount(self, filesystem, options):
        self.method.FilesystemMount(filesystem, options)

    def unmount(self):
        self.method.FilesystemUnmount([])

    def lock(self, options):
        """Lock Luks device."""
        return self.method.LuksLock(options)

    def unlock(self, password, options):
        """Unlock Luks device."""
        return self.method.LuksUnlock(password, options)


def get_all(bus):
    """Enumerate all device objects currently known to udisks."""
    udisks = bus.get_object(UDISKS_OBJECT, UDISKS_OBJECT_PATH)
    for path in udisks.EnumerateDevices(dbus_interface=UDISKS_INTERFACE):
        yield Device(bus, path)

def get_all_handleable(bus):
    """Enumerate all handleable devices currently known to udisks."""
    for device in get_all(bus):
        if device.is_handleable:
            yield device

def get_device(bus, path):
    """Get a device proxy by device name or any mount path of the device."""
    logger = logging.getLogger('udiskie.device.get_device')
    for device in get_all(bus):
        if os.path.samefile(path, device.device_file):
            return device
        for p in device.mount_paths:
            if os.path.samefile(path, p):
                return device
    logger.warn('Device not found: %s' % path)
    return None

