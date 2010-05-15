import logging

import dbus

import udiskie.device

def unmount(path):
    """Unmount a filesystem

    The filesystem must match the criteria for a filesystem mountable by
    udiskie.  path is either the physical device node (e.g. /dev/sdb1) or the
    mount point (e.g. /media/Foo)."""

    logger = logging.getLogger('udiskie.umount.unmount')
    bus = dbus.SystemBus()
    for device in udiskie.device.get_all(bus):
        if path in device.mount_paths() or path == device.device_file():
            logger.debug('Found device owning "%s": "%s"' % (path, device))
            if device.is_handleable() and device.is_mounted():
                logger.debug('Unmounting %s (device: %s)' % (path, device))
                device.unmount()
                logger.info('Unmounted %s' % (path,))
            else:
                logger.info('Skipping unhandled device %s' % (device,))

def unmount_all():
    """Unmount all filesystems handleable by udiskie."""

    logger = logging.getLogger('udiskie.umount.unmount_all')
    bus = dbus.SystemBus()
    for device in udiskie.device.get_all(bus):
        if device.is_handleable() and device.is_mounted():
            logger.debug('Unmounting device: %s' % (device,))
            device.unmount()
            logger.info('Unmounted device: %s' % (device,))
        else:
            logger.debug('Skipping unhandled device %s' % (device,))

def cli(args):
    logging.basicConfig(level=logging.DEBUG)
    unmount_all()
    #for path in args[1:]:
    #    unmount(path)
