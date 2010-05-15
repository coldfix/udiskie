import logging

import dbus

import udiskie.device

def unmount(path):
    """Unmount a filesystem

    The filesystem must match the criteria for a filesystem mountable by
    udiskie.  path is either the physical device node (e.g. /dev/sdb1) or the
    mount point (e.g. /media/Foo)."""

    bus = dbus.SystemBus()
    logger = logging.getLogger('udiskie.umount.unmount')
    for device in udiskie.device.get_all(bus):
        if path in device.mount_paths() or path == device.device_file():
            logger.debug('Found device owning "%s": "%s"' % (path, device))
            if device.is_handleable() and device.is_mounted():
                logger.info('Unmounting %s (device: %s)' % (path, device))
                device.unmount()
                logger.info('Finished unmounting %s' % (path,))
            else:
                logger.info('Skipping unhandled device %s' % (device_path,))

def cli(args):
    logging.basicConfig(level=logging.DEBUG)
    for path in args[1:]:
        unmount(path)
