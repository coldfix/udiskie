import logging
import optparse

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
    logger = logging.getLogger('udiskie.umount.cli')
    parser = optparse.OptionParser()
    parser.add_option('-a', '--all', action='store_true',
                      dest='all', default=False,
                      help='all devices')
    parser.add_option('-v', '--verbose', action='store_true',
                      dest='verbose', default=False,
                      help='verbose output')
    (options, args) = parser.parse_args(args)

    log_level = logging.INFO
    if options.verbose:
        log_level = logging.DEBUG
    logging.basicConfig(level=log_level, format='%(message)s')

    if options.all:
        unmount_all()
    else:
        if len(args) == 0:
            logger.warn('No devices provided for unmount')
            return 1

        for path in args:
            unmount(path)
