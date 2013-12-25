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

        If udisks is None only the xxx_device methods will work. The
        exception is the force=True branch of remove_device.

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
        if not self.is_handleable(device) or not device.is_filesystem:
            log.debug('skipping unhandled device %s' % (device,))
            return False
        if device.is_mounted:
            log.debug('skipping mounted device %s' % (device,))
            return False

        fstype = str(device.id_type)
        filter = filter or self.filter
        options = ','.join(filter.get_mount_options(device) if filter else [])

        log.debug('attempting to mount device %s (%s:%s)' % (device, fstype, options))
        try:
            device.mount(fstype=fstype, options=options)
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
        if not self.is_handleable(device) or not device.is_filesystem:
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
        if not self.is_handleable(device) or not device.is_crypto:
            log.debug('skipping unhandled device %s' % (device,))
            return False
        if device.is_unlocked:
            log.debug('skipping unlocked device %s' % (device,))
            return False

        # prompt user for password
        message = ''
        for iteration in range(3):
            prompt = prompt or self.prompt
            password = prompt and prompt(
                    '%sEnter password for %s:' % (
                        message,
                        device.device_presentation,),
                    'Unlock encrypted device')
            if password is None:
                return False

            # unlock device
            log.info('attempting to unlock device %s' % (device,))
            try:
                holder_dev = device.unlock(password)
                log.info('unlocked device %s on %s' % (device, holder_dev.device_file))
                return True
            except device.Exception:
                err = sys.exc_info()[1]
                log.error('failed to unlock device %s:\n%s' % (device, err))
                message = err.message

    def lock_device(self, device):
        """
        Lock device.

        Checks to make sure the device is lockable, then locks.
        Return value indicates whether an action was performed successfully.
        The special value `None` means unknown/unreliable.

        """
        logger = logging.getLogger('udiskie.mount.lock_device')
        if not self.is_handleable(device) or not device.is_crypto:
            logger.debug('skipping unhandled device %s' % (device,))
            return False
        if not device.is_unlocked:
            logger.debug('skipping locked device %s' % (device,))
            return False
        try:
            device.lock()
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
        if not self.is_handleable(device):
            log.debug('skipping unhandled device %s' % (device,))
            return False
        if device.is_filesystem:
            return self.mount_device(device, filter)
        elif device.is_crypto:
            return self.unlock_device(device, prompt)

    def remove_device(self, device, force=False):
        """
        Unmount or lock the device depending on device type.

        If `force` is True recursively unmount/unlock all devices that are
        contained by this device.

        """
        logger = logging.getLogger('udiskie.mount.remove_device')
        if device.is_filesystem:
            return self.unmount_device(device)
        elif device.is_crypto:
            if not device.is_unlocked:
                return False
            if force:
                self.remove_device(device.luks_cleartext_holder, force=True)
            return self.lock_device(device)
        elif force and (device.is_partition_table or device.is_drive):
            success = True
            for dev in self.get_all_handleable():
                if (dev.is_partition and dev.partition_slave == device) or (dev.is_toplevel and dev.drive == device) and (dev != device):
                    ret = self.remove_device(dev, force=True)
                    if ret is None:
                        success = None
                    else:
                        success = success and ret
            return success
        else:
            logger.debug('skipping unhandled device %s' % (device,))
            return False

    # eject/detach device
    def eject_device(self, device, force=False):
        """Eject a device after unmounting all its mounted filesystems."""
        logger = logging.getLogger('udiskie.mount.eject_device')
        drive = device.drive
        if not (drive.is_drive and drive.is_ejectable):
            logger.debug('drive not ejectable: %s' % drive)
            return False
        if force:
            self.remove_device(drive, force=True)
        try:
            drive.eject()
            logger.info('ejected device %s' % (device,))
            return True
        except drive.Exception:
            logger.warning('failed to eject device %s' % (device,))
            return False

    def detach_device(self, device, force=False):
        """Detach a device after unmounting all its mounted filesystems."""
        logger = logging.getLogger('udiskie.mount.eject_device')
        drive = device.drive
        if not (drive.is_drive and drive.is_detachable):
            logger.warning('drive not detachable: %s' % drive)
            return False
        if force:
            self.remove_device(drive, force=True)
        try:
            drive.detach()
            logger.info('detached device %s' % (device,))
            return True
        except drive.Exception:
            logger.warning('failed to detach device %s' % (device,))
            return False

    # mount_all/unmount_all
    def mount_all(self, filter=None, prompt=None):
        """Mount handleable devices that are already present."""
        for device in self.get_all_handleable():
            self.add_device(device, filter, prompt)

    def unmount_all(self):
        """Unmount all filesystems handleable by udiskie."""
        unmounted = []
        for device in self.get_all_handleable():
            if self.unmount_device(device):
                unmounted.append(device)
        return unmounted

    def eject_all(self):
        """Eject all ejectable devices."""
        ejected = []
        for device in self.udisks.get_all():
            if (device.is_drive and
                device.is_external and
                device.is_ejectable and
                eject_device(device, force=True)):
                ejected.append(device)
        return ejected

    def detach_all(self):
        """Detach all detachable devices."""
        detached = []
        for device in self.udisks.get_all():
            if (device.is_drive and
                device.is_external and
                device.is_detachable and
                self.detach_device(device, force=True)):
                detached.append(device)
        return detached

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
        if device.in_use:
            return False
        return self.lock_device(device.luks_cleartext_slave)


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

    def unmount(self, path, force=False):
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
            if self.remove_device(device, force=force):
                return device
        return None

    # eject media/detach drive
    def eject(self, path, force=False):
        """
        Eject media from the device.

        If the device has any mounted filesystems, these will be unmounted
        before ejection.

        """
        logger = logging.getLogger('udiskie.mount.eject')
        device = self.udisks.get_device(path)
        if device:
            logger.debug('found device owning "%s": "%s"' % (path, device))
            if self.eject_device(device, force=force):
                return device
        else:
            logger.warning('no found device owning "%s"' % (path))
            return None

    def detach(self, path, force=False):
        """
        Eject media from the device.

        If the device has any mounted filesystems, these will be unmounted
        before ejection.

        """
        logger = logging.getLogger('udiskie.mount.detach')
        device = self.udisks.get_device(path)
        if device:
            logger.debug('found device owning "%s": "%s"' % (path, device))
            if self.detach_device(device, force=force):
                return device
        else:
            logger.warning('no found device owning "%s"' % (path))
            return None

    def is_handleable(self, device):
        """
        Should this device be handled by udiskie?

        Currently this just means that the device is removable and holds a
        filesystem or the device is a LUKS encrypted volume.

        """
        # FIXME: what about drives
        return (device.is_block and
                device.is_external and
                (not self.filter or not self.filter.is_ignored(device)))

    def get_all_handleable(self):
        """
        Enumerate all handleable devices currently known to udisks.

        NOTE: returns only devices that are still valid. This protects from
        race conditions inside udiskie.

        """
        return filter(self.is_handleable, self.udisks.get_all())

