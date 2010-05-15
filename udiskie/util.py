import logging

from udiskie import system_bus
import udiskie.names as names

def _get_all_devices():
    obj = system_bus.get_object(names.UDISKS_OBJECT,
                                names.UDISKS_OBJECT_PATH)
    return obj.EnumerateDevices(dbus_interface=names.UDISKS_INTERFACE)

def _get_property(device, prop):
    device_obj = system_bus.get_object(names.UDISKS_OBJECT, device)
    return device_obj.Get(names.UDISKS_DEVICE_INTERFACE, prop, dbus_interface=names.DBUS_PROPS_INTERFACE)

def find_device(path):
    logger = logging.getLogger('udiskie.util.find_device')

    found = []

    for device in _get_all_devices():
        logger.debug('examining %s' % (device,))

        mounted_paths = _get_property(device, 'DeviceMountPaths')
        if path in mounted_paths:
            found.append(device)

        # device path
        device_file = _get_property(device, 'DeviceFile')
        if path == device_file:
            found.append(device)

    return found

def handleable(device_path):
    """Check if the device should be handled by udiskie.
    
    Right now this just means that the device is removable."""

    removable = _get_property(device_path, 'DeviceIsRemovable')
    logger = logging.getLogger('udiskie.util.handleable')
    logger.debug('device_path: %s, removable: %s' % (device_path, removable))
    return removable

def mounted(device_path):
    """Check if the device is currently mounted."""

    return _get_property(device_path, 'DeviceIsMounted')
