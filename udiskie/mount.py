"""
Udiskie mount utilities.
"""
__all__ = [
    'mount_device', 'unmount_device',
    'unlock_device', 'lock_device',
    'add_device', 'remove_device',
    'mount_all', 'unmount_all',
    'unmount',
    'lock_luks_slave',
    'Mounter']

import logging
import dbus

import udiskie.device


# mount/unmount
def mount_device(device, filter=None):
    """
    Mount the device if not already mounted.

    Return value indicates whether an action was performed successfully.
    The special value `None` means unknown/unreliable.

    """
    log = logging.getLogger('udiskie.mount.mount_device')
    if not device.is_handleable or not device.is_filesystem:
        log.debug('skipping unhandled device %s' % (device,))
        return False
    if device.is_mounted:
        log.debug('skipping mounted device %s' % (device,))
        return False

    fstype = str(device.id_type)
    options = filter.get_mount_options(device) if filter else []

    S = 'attempting to mount device %s (%s:%s)'
    log.info(S % (device, fstype, options))

    try:
        device.mount(fstype, options)
        log.info('mounted device %s' % (device,))
    except dbus.exceptions.DBusException, dbus_err:
        log.error('failed to mount device %s: %s' % (
                                            device, dbus_err))
        return None

    mount_paths = ', '.join(device.mount_paths)
    return True

def unmount_device(device):
    """
    Unmount a Device.

    Checks to make sure the device is unmountable and then unmounts.
    Return value indicates whether an action was performed successfully.
    The special value `None` means unknown/unreliable.

    """
    logger = logging.getLogger('udiskie.mount.unmount_device')
    if not device.is_handleable or not device.is_filesystem:
        logger.debug('skipping unhandled device %s' % (device,))
        return False
    if not device.is_mounted:
        logger.debug('skipping unmounted device %s' % (device,))
        return False
    try:
        device.unmount()
        logger.info('unmounted device %s' % (device,))
    except dbus.exceptions.DBusException, dbus_err:
        logger.error('failed to unmount device %s: %s' % (device,
                                                            dbus_err))
        return None
    return True


# unlock/lock (LUKS)
def unlock_device(device, prompt):
    """
    Unlock the device if not already unlocked.

    Return value indicates whether an action was performed successfully.
    The special value `None` means unknown/unreliable.

    """
    log = logging.getLogger('udiskie.mount.unlock_device')
    if not device.is_handleable or not device.is_crypto:
        log.debug('skipping unhandled device %s' % (device,))
        return False
    if device.is_unlocked:
        log.debug('skipping unlocked device %s' % (device,))
        return False

    # prompt user for password
    password = prompt and prompt(
            'Enter password for %s:' % (device,),
            'Unlock encrypted device')
    if password is None:
        return False

    # unlock device
    log.info('attempting to unlock device %s' % (device,))
    try:
        device.unlock(password, [])
        holder_dev = udiskie.device.Device(
                device.bus,
                device.luks_cleartext_holder)
        holder_path = holder_dev.device_file
        log.info('unlocked device %s on %s' % (device, holder_path))
    except dbus.exceptions.DBusException, dbus_err:
        log.error('failed to unlock device %s:\n%s'
                                    % (device, dbus_err))
        return None
    return True

def lock_device(device):
    """
    Lock device.

    Checks to make sure the device is lockable, then locks.
    Return value indicates whether an action was performed successfully.
    The special value `None` means unknown/unreliable.

    """
    logger = logging.getLogger('udiskie.mount.lock_device')
    if not device.is_handleable or not device.is_crypto:
        logger.debug('skipping unhandled device %s' % (device,))
        return False
    if not device.is_unlocked:
        logger.debug('skipping locked device %s' % (device,))
        return False
    try:
        device.lock([])
        logger.info('locked device %s' % (device,))
    except dbus.exceptions.DBusException, dbus_err:
        logger.error('failed to lock device %s: %s' % (device, dbus_err))
        return None
    return True


# add/remove (unlock/lock or mount/unmount)
def add_device(device, filter=None, prompt=None):
    """Mount or unlock the device depending on its type."""
    log = logging.getLogger('udiskie.mount.add_device')
    if not device.is_handleable:
        log.debug('skipping unhandled device %s' % (device,))
        return False
    if device.is_filesystem:
        return mount_device(device, filter)
    elif device.is_crypto:
        return unlock_device(device, prompt)

def remove_device(device):
    """Unmount or lock the device depending on device type."""
    logger = logging.getLogger('udiskie.mount.remove_device')
    if not device.is_handleable:
        logger.debug('skipping unhandled device %s' % (device,))
        return False
    if device.is_filesystem:
        return unmount_device(device)
    elif device.is_crypto:
        return lock_device(device)

# mount_all/unmount_all
def mount_all(bus=None, filter=None, prompt=None):
    """Mount handleable devices that are already present."""
    bus = bus or dbus.SystemBus()
    for device in udiskie.device.get_all_handleable(bus):
        add_device(device, filter, prompt)

def unmount_all(bus=None):
    """Unmount all filesystems handleable by udiskie."""
    unmounted = []
    bus = bus or dbus.SystemBus()
    for device in udiskie.device.get_all_handleable(bus):
        if unmount_device(device):
            unmounted.append(device)
    return unmounted


# mount a holder/lock a slave
def mount_holder(device, filter=None, prompt=None):
    """
    Mount or unlock the holder device of this unlocked LUKS device.

    Will not mount the holder if the device is not unlocked.
    Return value indicates success

    """
    logger = logging.getLogger('udiskie.mount.lock_slave')
    if not device.is_unlocked:
        logger.debug('skipping locked or non-luks device %s' % (device,))
        return False
    holder_path = device.luks_cleartext_holder
    holder = udiskie.device.Device(device.bus, holder_path)
    return add_device(device, filter=filter, prompt=prompt)

def lock_slave(device):
    """
    Lock the luks slave of this device.

    Will not lock the slave if it is still used by any mounted file system.
    Return value indicates success.

    """
    logger = logging.getLogger('udiskie.mount.lock_slave')
    if not device.is_luks_cleartext:
        logger.debug('skipping non-luks-cleartext device %s' % (device,))
        return False
    slave_path = device.luks_cleartext_slave
    slave = udiskie.device.Device(device.bus, slave_path)
    if slave.is_luks_cleartext_slave:
        return False
    return lock_device(slave)


# mount/unmount by path
def mount(path, bus=None, filter=None, prompt=None):
    """
    Mount or unlock a device.

    The device must match the criteria for a filesystem mountable or
    unlockable by udiskie.

    """
    logger = logging.getLogger('udiskie.mount.unmount')
    bus = bus or dbus.SystemBus()
    device = udiskie.device.get_device(bus, path)
    if device:
        logger.debug('found device owning "%s": "%s"' % (path, device))
        if add_device(device, filter=filter, prompt=prompt):
            return device
    return None

def unmount(path, bus=None):
    """
    Unmount or lock a filesystem

    The filesystem must match the criteria for a filesystem mountable by
    udiskie.  path is either the physical device node (e.g. /dev/sdb1) or the
    mount point (e.g. /media/Foo).

    """
    logger = logging.getLogger('udiskie.mount.unmount')
    bus = bus or dbus.SystemBus()
    device = udiskie.device.get_device(bus, path)
    if device:
        logger.debug('found device owning "%s": "%s"' % (path, device))
        if remove_device(device):
            return device
    return None


# utility class
class Mounter:
    """
    Mount utility.

    Calls the global functions and remembers bus, filter and prompt.

    """
    def __init__(self, bus, filter=None, prompt=None):
        self.bus = bus or dbus.SystemBus()
        self.filter = filter
        self.prompt = prompt

    # mount/unmount
    def mount_device(self, device, filter=None):
        return mount_device(device, filter=filter or self.filter)
    def unmount_device(self, device):
        return unmount_device(device)

    # unlock/lock (LUKS)
    def unlock_device(self, device, prompt=None):
        return mount_device(device, filter=prompt or self.prompt)
    def lock_device(self, device):
        return lock_device(device)

    # add/remove (unlock/lock or mount/unmount)
    def add_device(self, device, filter=None, prompt=None):
        return add_device(
                device,
                filter=filter or self.filter,
                prompt=prompt or self.prompt)
    def remove_device(self, device):
        return remove_device(device)

    # mount_all/unmount_all
    def mount_all(self, filter=None, prompt=None):
        return mount_all(
                self.bus,
                filter=filter or self.filter,
                prompt=prompt or self.prompt)
    def unmount_all(self):
        return unmount_all(self.bus)

    # mount/unmount
    def mount(self, path, filter=None, prompt=None):
        return mount(
                path, bus=self.bus,
                filter=filter or self.filter,
                prompt=prompt or self.prompt)
    def unmount(self, path):
        return unmount(path, bus=self.bus)

    # mount_holder/lock_slave
    def mount_holder(self, device, filter=None, prompt=None):
        return mount_holder(
                device,
                filter=filter or self.filter,
                prompt=prompt or self.prompt)
    def lock_slave(self, device):
        return lock_slave(device)

