import logging
import os

DBUS_PROPS_INTERFACE = 'org.freedesktop.DBus.Properties'
UDISKS_INTERFACE = 'org.freedesktop.UDisks'
UDISKS_DEVICE_INTERFACE = 'org.freedesktop.UDisks.Device'

UDISKS_OBJECT = 'org.freedesktop.UDisks'
UDISKS_OBJECT_PATH = '/org/freedesktop/UDisks'

class Device:
    def __init__(self, bus, device_path):
        self.log = logging.getLogger('udiskie.device.Device')
        self.bus = bus
        self.device_path = device_path
        self.device = self.bus.get_object(UDISKS_OBJECT, device_path)

    def __str__(self):
        return self.device_path

    def _get_property(self, property):
        return self.device.Get(UDISKS_DEVICE_INTERFACE, property,
                               dbus_interface=DBUS_PROPS_INTERFACE)

    def partition_slave(self):
        return self._get_property('PartitionSlave')

    def is_partition_table(self):
        return self._get_property('DeviceIsPartitionTable')

    def is_systeminternal(self):
        return self._get_property('DeviceIsSystemInternal')

    def is_handleable(self):
        """Should this device be handled by udiskie?

        Currently this just means that the device is removable and holds a
        filesystem."""

        if self.is_filesystem() and not self.is_systeminternal():
            return True
        else:
            return False

    def is_mounted(self):
        return self._get_property('DeviceIsMounted')

    def is_unlocked(self):
        """
        Check if device is already unlocked.

        It seems that the property 'DeviceIsLuks' shows whether the device
        is known to luks. This is an indication that it is already unlocked.

        """
        return self.is_luks()

    def mount_paths(self):
        raw_paths = self._get_property('DeviceMountPaths')
        return [os.path.normpath(path) for path in raw_paths]

    def device_file(self):
        return os.path.normpath(self._get_property('DeviceFile'))

    def is_filesystem(self):
        return self._get_property('IdUsage') == 'filesystem'

    def is_crypto(self):
        return self._get_property('IdUsage') == 'crypto'

    def is_luks(self):
        return self._get_property('DeviceIsLuks')

    def is_luks_cleartext(self):
        return self._get_property('DeviceIsLuksCleartext')

    def luks_cleartext_slave(self):
        return self._get_property('LuksCleartextSlave')

    def is_luks_cleartext_slave(self, ignore = []):
        if not self.is_luks():
            return False
        for device in get_all(self.bus):
            if device.is_mounted() and \
                    device.is_luks_cleartext() and \
                    device.luks_cleartext_slave() == self.device_path:
                return True
        return False

    def has_media(self):
        return self._get_property('DeviceIsMediaAvailable')

    def id_type(self):
        return self._get_property('IdType')

    def id_uuid(self):
        return self._get_property('IdUuid')

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
