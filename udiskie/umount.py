import logging

from udiskie import system_bus
from udiskie.names import UDISKS_OBJECT, UDISKS_DEVICE_INTERFACE
import udiskie.util

def unmount(path):
    """Unmount a filesystem

    The filesystem must match the criteria for a filesystem mountable by
    udiskie.  path is either the physical device node (e.g. /dev/sdb1) or the
    mount point (e.g. /media/Foo)."""
    
    logger = logging.getLogger('udiskie.umount.unmount')
    device_path = udiskie.util.find_device(path)
    if udiskie.util.handleable(device_path) \
       and udiskie.util.mounted(device_path):
        logger.info('Unmounting %s (udisks path: %s)' % (path, device_path))
        device_object = system_bus.get_object(UDISKS_OBJECT, device_path)
        device_object.FilesystemUnmount([],
                                        dbus_interface=UDISKS_DEVICE_INTERFACE)
        logger.info('Finished unmounting %s' % (path,))

def cli(args):
    for path in args[1:]:
        unmount(path)
