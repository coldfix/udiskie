"""
Udiskie mount utilities.
"""
__all__ = ['Mounter']

import sys
import logging

class Mounter(object):
    """
    Mount utility.

    Remembers udisks, prompt and filter instances to use across multiple
    mount operations.

    """
    def __init__(self, filter=None, prompt=None, udisks=None):
        """
        Initialize mounter with the given defaults.

        The parameters are not guaranteed to keep their order and should
        always be passed as keyword arguments.

        If udisks is None only the xxx_device methods will work.
        If prompt is None device unlocking will not work.

        """
        self.filter = filter
        self.prompt = prompt
        self.udisks = udisks

    # mount/unmount
    def mount_device(self, device, filter=None):
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
        filter = filter or self.filter
        options = filter.get_mount_options(device) if filter else []

        log.info('attempting to mount device %s (%s:%s)' % (device, fstype, options))
        try:
            device.mount(fstype, options)
        except device.Exception:
            err = sys.exc_info()[1]
            log.error('failed to mount device %s: %s' % (device, err))
            return None

        log.info('mounted device %s' % (device,))
        return True

    def unmount_device(self, device):
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
        except device.Exception:
            err = sys.exc_info()[1]
            logger.error('failed to unmount device %s: %s' % (device, err))
            return None
        return True


    # unlock/lock (LUKS)
    def unlock_device(self, device, prompt=None):
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
        prompt = prompt or self.prompt
        password = prompt and prompt(
                'Enter password for %s:' % (device,),
                'Unlock encrypted device')
        if password is None:
            return False

        # unlock device
        log.info('attempting to unlock device %s' % (device,))
        try:
            device.unlock(password, [])
            holder_dev = self.udisks.create_device(
                device.luks_cleartext_holder)
            holder_path = holder_dev.device_file
            log.info('unlocked device %s on %s' % (device, holder_path))
        except self.udisks.Exception:
            err = sys.exc_info()[1]
            log.error('failed to unlock device %s:\n%s' % (device, err))
            return None
        return True

    def lock_device(self, device):
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
        except device.Exception:
            err = sys.exc_info()[1]
            logger.error('failed to lock device %s: %s' % (device, err))
            return None
        return True


    # add/remove (unlock/lock or mount/unmount)
    def add_device(self, device, filter=None, prompt=None):
        """Mount or unlock the device depending on its type."""
        log = logging.getLogger('udiskie.mount.add_device')
        if not device.is_handleable:
            log.debug('skipping unhandled device %s' % (device,))
            return False
        if device.is_filesystem:
            return self.mount_device(device, filter)
        elif device.is_crypto:
            return self.unlock_device(device, prompt)

    def remove_device(self, device):
        """Unmount or lock the device depending on device type."""
        logger = logging.getLogger('udiskie.mount.remove_device')
        if not device.is_handleable:
            logger.debug('skipping unhandled device %s' % (device,))
            return False
        if device.is_filesystem:
            return self.unmount_device(device)
        elif device.is_crypto:
            return self.lock_device(device)

    # mount_all/unmount_all
    def mount_all(self, filter=None, prompt=None):
        """Mount handleable devices that are already present."""
        for device in self.udisks.get_all_handleable():
            self.add_device(device, filter, prompt)

    def unmount_all(self):
        """Unmount all filesystems handleable by udiskie."""
        unmounted = []
        for device in self.udisks.get_all_handleable():
            if self.unmount_device(device):
                unmounted.append(device)
        return unmounted


    # mount a holder/lock a slave
    def mount_holder(self, device, filter=None, prompt=None):
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
        holder = self.udisks.create_device(holder_path)
        return self.add_device(holder, filter=filter, prompt=prompt)

    def lock_slave(self, device):
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
        slave = self.udisks.create_device(slave_path)
        if slave.is_luks_cleartext_slave:
            return False
        return self.lock_device(slave)


    # mount/unmount by path
    def mount(self, path, filter=None, prompt=None):
        """
        Mount or unlock a device.

        The device must match the criteria for a filesystem mountable or
        unlockable by udiskie.

        """
        logger = logging.getLogger('udiskie.mount.unmount')
        device = self.udisks.get_device(path)
        if device:
            logger.debug('found device owning "%s": "%s"' % (path, device))
            if self.add_device(device, filter=filter, prompt=prompt):
                return device
        return None

    def unmount(self, path):
        """
        Unmount or lock a filesystem

        The filesystem must match the criteria for a filesystem mountable by
        udiskie.  path is either the physical device node (e.g. /dev/sdb1) or the
        mount point (e.g. /media/Foo).

        """
        logger = logging.getLogger('udiskie.mount.unmount')
        device = self.udisks.get_device(path)
        if device:
            logger.debug('found device owning "%s": "%s"' % (path, device))
            if self.remove_device(device):
                return device
        return None

