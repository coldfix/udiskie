import logging

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

    def is_removable(self):
        return self._get_property('DeviceIsRemovable')

    def is_partition(self):
        return self._get_property('DeviceIsPartition')

    def is_handleable(self):
        """Should this device be handled by udiskie.

        Currently this just means that the device is removable or that the
        device it is part of is removable."""

        if self.is_removable():
            return True
        else:
            if self.is_partition():
                parent = Device(self.bus, self.partition_slave())
                return parent.is_handleable()
            else:
                return False

    def is_mounted(self):
        return self._get_property('DeviceIsMounted')

    def mount_paths(self):
        return self._get_property('DeviceMountPaths')

    def device_file(self):
        return self._get_property('DeviceFile')

    def unmount(self):
        self.device.FilesystemUnmount([], dbus_interface=UDISKS_DEVICE_INTERFACE)


def get_all(bus):
    udisks = bus.get_object(UDISKS_OBJECT, UDISKS_OBJECT_PATH)
    for path in udisks.EnumerateDevices(dbus_interface=UDISKS_INTERFACE):
        yield Device(bus, path)
