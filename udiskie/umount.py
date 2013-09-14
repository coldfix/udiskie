import warnings
warnings.filterwarnings("ignore", ".*could not open display.*", Warning)
warnings.filterwarnings("ignore", ".*g_object_unref.*", Warning)

import logging
import optparse
import os

import dbus

import udiskie.device
import udiskie.notify

def unmount_device(device, notify):
    """
    Unmount a Device.

    Checks to make sure the device is unmountable and then unmounts.
    Return value indicates whether an action was performed successfully.
    The special value `None` means unknown/unreliable.

    """
    logger = logging.getLogger('udiskie.umount.unmount_device')
    if not device.is_handleable() or not device.is_filesystem():
        logger.debug('skipping unhandled device %s' % (device,))
        return False
    if not device.is_mounted():
        logger.debug('skipping unmounted device %s' % (device,))
        return False
    try:
        device.unmount()
        logger.info('unmounted device %s' % (device,))
    except dbus.exceptions.DBusException, dbus_err:
        logger.error('failed to unmount device %s: %s' % (device,
                                                            dbus_err))
        return None
    notify('umount')(device.device_file())
    return True

def lock_device(device, notify):
    """
    Lock device.

    Checks to make sure the device is lockable, then locks.
    Return value indicates whether an action was performed successfully.
    The special value `None` means unknown/unreliable.

    """
    logger = logging.getLogger('udiskie.umount.lock_device')
    if not device.is_handleable() or not device.is_crypto():
        logger.debug('skipping unhandled device %s' % (device,))
        return False
    if not device.is_unlocked():
        logger.debug('skipping locked device %s' % (device,))
        return False
    try:
        device.lock([])
        logger.info('locked device %s' % (device,))
    except dbus.exceptions.DBusException, dbus_err:
        logger.error('failed to lock device %s: %s' % (device, dbus_err))
        return None
    notify('lock')(device.device_file())
    return True

def remove_device(device, notify):
    """Unmount or lock the device depending on device type."""
    logger = logging.getLogger('udiskie.umount.remove_device')
    if not device.is_handleable():
        logger.debug('skipping unhandled device %s' % (device,))
        return False
    if device.is_filesystem():
        return unmount_device(device, notify)
    elif device.is_crypto():
        return lock_device(device, notify)

def lock_slave(device, notify):
    """
    Lock the luks slave of this device.

    Will not lock the slave if it is still used by any mounted file system.
    Return value indicates success.

    """
    logger = logging.getLogger('udiskie.umount.lock_slave')
    if not device.is_luks_cleartext():
        logger.debug('skipping non-luks-cleartext device %s' % (device,))
        return False
    slave_path = device.luks_cleartext_slave()
    slave = udiskie.device.Device(device.bus, slave_path)
    if slave.is_luks_cleartext_slave():
        return False
    return lock_device(slave, notify)


def unmount(path, notify):
    """Unmount or lock a filesystem

    The filesystem must match the criteria for a filesystem mountable by
    udiskie.  path is either the physical device node (e.g. /dev/sdb1) or the
    mount point (e.g. /media/Foo)."""

    logger = logging.getLogger('udiskie.umount.unmount')
    bus = dbus.SystemBus()

    device = udiskie.device.get_device(bus, path)
    if device:
        logger.debug('found device owning "%s": "%s"' % (path, device))
        if remove_device(device, notify):
            return device
    return None


def unmount_all(notify):
    """Unmount all filesystems handleable by udiskie."""

    unmounted = []
    bus = dbus.SystemBus()
    for device in udiskie.device.get_all(bus):
        if unmount_device(device, notify):
            unmounted.append(device)
    return unmounted

def cli(args):
    logger = logging.getLogger('udiskie.umount.cli')
    parser = optparse.OptionParser()
    parser.add_option('-a', '--all', action='store_true',
                      dest='all', default=False,
                      help='all devices')
    parser.add_option('-v', '--verbose', action='store_true',
                      dest='verbose', default=False,
                      help='verbose output')
    parser.add_option('-s', '--suppress', action='store_true',
                      dest='suppress_notify', default=False,
                      help='suppress popup notifications')
    (options, args) = parser.parse_args(args)

    log_level = logging.INFO
    if options.verbose:
        log_level = logging.DEBUG
    logging.basicConfig(level=log_level, format='%(message)s')

    if options.suppress_notify:
        notify = lambda ctx: lambda *args: True
    else:
        notify_ = udiskie.notify.Notify('udiskie.umount')
        notify = lambda ctx: getattr(notify_, ctx)

    if options.all:
        unmounted = unmount_all(notify)
    else:
        if len(args) == 0:
            logger.warn('No devices provided for unmount')
            return 1

        unmounted = []
        for path in args:
            device = unmount(os.path.normpath(path), notify)
            if device:
                unmounted.append(device)

    # automatically lock unused luks slaves of unmounted devices
    for device in unmounted:
        lock_slave(device, notify)

