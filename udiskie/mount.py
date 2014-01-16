"""
Udiskie mount utilities.
"""
__all__ = ['Mounter']

import sys
import logging

try:                    # python2
    from itertools import ifilter as filter
except ImportError:     # python3
    pass



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

        Return value indicates whether the device is mounted.

        """
        log = logging.getLogger('udiskie.mount.mount_device')
        if not self.is_handleable(device) or not device.is_filesystem:
            log.debug('not mounting unhandled device %s' % (device,))
            return False
        if device.is_mounted:
            log.debug('not mounting mounted device %s' % (device,))
            return True
        fstype = str(device.id_type)
        filter = filter or self.filter
        options = ','.join(filter.get_mount_options(device) if filter else [])
        try:
            log.debug('mounting device %s (%s:%s)' % (device, fstype, options))
            mount_path = device.mount(fstype=fstype, options=options)
            log.info('mounted device %s on %s' % (device, mount_path))
            return True
        except device.Exception:
            err = sys.exc_info()[1]
            log.error('failed to mount device %s: %s' % (device, err))
            return False

    def unmount_device(self, device):
        """
        Unmount a Device.

        Checks to make sure the device is unmountable and then unmounts.
        Return value indicates whether the device is unmounted.

        """
        log = logging.getLogger('udiskie.mount.unmount_device')
        if not self.is_handleable(device) or not device.is_filesystem:
            log.debug('not unmounting unhandled device %s' % (device,))
            return False
        if not device.is_mounted:
            log.debug('not unmounting unmounted device %s' % (device,))
            return True
        try:
            log.debug('unmounting device %s' % (device,))
            device.unmount()
            log.info('unmounted device %s' % (device,))
            return True
        except device.Exception:
            err = sys.exc_info()[1]
            log.error('failed to unmount device %s: %s' % (device, err))
            return False

    # unlock/lock (LUKS)
    def unlock_device(self, device, prompt=None):
        """
        Unlock the device if not already unlocked.

        Return value indicates whether the device is unlocked.

        """
        log = logging.getLogger('udiskie.mount.unlock_device')
        if not self.is_handleable(device) or not device.is_crypto:
            log.debug('not unlocking unhandled device %s' % (device,))
            return False
        if device.is_unlocked:
            log.debug('not unlocking unlocked device %s' % (device,))
            return True
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
            try:
                log.debug('unlocking device %s' % (device,))
                mount_path = device.unlock(password).device_file
                log.info('unlocked device %s on %s' % (device, mount_path))
                return True
            except device.Exception:
                err = sys.exc_info()[1]
                log.error('failed to unlock device %s:\n%s' % (device, err))
                message = err.message
        return False

    def lock_device(self, device):
        """
        Lock device.

        Checks to make sure the device is lockable, then locks.
        Return value indicates whether the device is locked.

        """
        log = logging.getLogger('udiskie.mount.lock_device')
        if not self.is_handleable(device) or not device.is_crypto:
            log.debug('not locking unhandled device %s' % (device,))
            return False
        if not device.is_unlocked:
            log.debug('not locking locked device %s' % (device,))
            return True
        try:
            log.debug('locking device %s' % (device,))
            device.lock()
            log.info('locked device %s' % (device,))
            return True
        except device.Exception:
            err = sys.exc_info()[1]
            log.error('failed to lock device %s: %s' % (device, err))
            return False

    # add/remove (unlock/lock or mount/unmount)
    def add_device(self, device, filter=None, prompt=None, recursive=False):
        """Mount or unlock the device depending on its type."""
        log = logging.getLogger('udiskie.mount.add_device')
        if not self.is_handleable(device):
            log.debug('not adding unhandled device %s' % (device,))
            return False
        if device.is_filesystem:
            success = self.mount_device(device, filter)
        elif device.is_crypto:
            success = self.unlock_device(device, prompt)
            if success and recursive:
                success = self.add_device(device.luks_cleartext_holder,
                                          filter=filter, prompt=prompt,
                                          recursive=True)
        elif recursive and device.is_partition_table:
            success = True
            for dev in self.get_all_handleable():
                if dev.is_partition and dev.partition_slave == device:
                    success = self.add_device(dev, filter=filter, prompt=prompt, recursive=True) and success
        else:
            log.debug('not adding unhandled device %s' % (device,))
            success = True
        return success

    def remove_device(self, device, force=False, detach=False, eject=False, lock=False):
        """
        Unmount or lock the device depending on device type.

        If `force` is True recursively unmount/unlock all devices that are
        contained by this device.

        """
        log = logging.getLogger('udiskie.mount.remove_device')
        if not self.is_handleable(device):
            log.debug('not removing unhandled device %s' % (device,))
            return False
        if device.is_filesystem:
            success = self.unmount_device(device)
        elif device.is_crypto:
            if force and device.is_unlocked:
                self.remove_device(device.luks_cleartext_holder, force=True)
            success = self.lock_device(device)
        elif force and (device.is_partition_table or device.is_drive):
            success = True
            for dev in self.get_all_handleable():
                if ((dev.is_partition and dev.partition_slave == device) or
                    (dev.is_toplevel and dev.drive == device and dev != device)):
                    success = self.remove_device(dev, force=True, detach=detach, eject=eject, lock=lock) and success
        else:
            log.debug('not removing unhandled device %s' % (device,))
            success = True
        if lock and device.is_luks_cleartext:
            success = self.lock_device(device.luks_cleartext_slave)
        if eject and device.is_drive and device.is_ejectable:
            success = self.eject_device(device) and success
        if detach and device.is_drive and device.is_detachable:
            success = self.detach_device(device) and success
        return success

    # eject/detach device
    def eject_device(self, device, force=False):
        """Eject a device after unmounting all its mounted filesystems."""
        log = logging.getLogger('udiskie.mount.eject_device')
        drive = device.drive
        if not (drive.is_drive and drive.is_ejectable):
            log.debug('drive not ejectable: %s' % drive)
            return False
        if force:
            self.remove_device(drive, force=True)
        try:
            log.debug('ejecting device %s' % (device,))
            drive.eject()
            log.info('ejected device %s' % (device,))
            return True
        except drive.Exception:
            log.error('failed to eject device %s' % (device,))
            return False

    def detach_device(self, device, force=False):
        """Detach a device after unmounting all its mounted filesystems."""
        log = logging.getLogger('udiskie.mount.detach_device')
        drive = device.root
        if not drive.is_detachable:
            log.debug('drive not detachable: %s' % drive)
            return False
        if force:
            self.remove_device(drive, force=True)
        try:
            log.debug('detaching device %s' % (device,))
            drive.detach()
            log.info('detached device %s' % (device,))
            return True
        except drive.Exception:
            log.error('failed to detach device %s' % (device,))
            return False

    # mount_all/unmount_all
    def mount_all(self, filter=None, prompt=None, recursive=False):
        """Mount handleable devices that are already present."""
        success = True
        for device in self.get_all_handleable():
            success = self.add_device(device, filter, prompt,
                                      recursive=recursive) and success
        return success

    def unmount_all(self, detach=False, eject=False, lock=False):
        """Unmount all filesystems handleable by udiskie."""
        success = True
        for device in self.get_all_handleable():
            success = self.remove_device(device, force=True,
                                         detach=detach, eject=eject,
                                         lock=True) and success
        return success

    def eject_all(self, force=True):
        """Eject all ejectable devices."""
        success = True
        for device in self.get_all_handleable():
            if device.is_drive and device.is_ejectable:
                success = self.eject_device(device, force=force) and success
        return success

    def detach_all(self, force=True):
        """Detach all detachable devices."""
        success = True
        for device in self.get_all_handleable():
            if device.is_drive and device.is_detachable:
                success = self.detach_device(device, force=force) and success
        return success

    # mount/unmount by path
    def mount(self, path, filter=None, prompt=None, recursive=False):
        """
        Mount or unlock a device.

        The device must match the criteria for a filesystem mountable or
        unlockable by udiskie.

        """
        return self.__path_adapter(self.add_device, path,
                                   filter=filter,
                                   prompt=prompt,
                                   recursive=recursive)

    def unmount(self, path, force=False, detach=False, eject=False, lock=False):
        """
        Unmount or lock a filesystem

        The filesystem must match the criteria for a filesystem mountable
        by udiskie.  path is either the physical device node (e.g.
        /dev/sdb1) or the mount point (e.g. /media/Foo).

        """
        return self.__path_adapter(self.remove_device, path,
                                   force=force,
                                   detach=detach, eject=eject,
                                   lock=lock)

    # eject media/detach drive
    def eject(self, path, force=False):
        """
        Eject media from the device.

        If the device has any mounted filesystems, these will be unmounted
        before ejection.

        """
        return self.__path_adapter(self.eject_device, path, force=force)

    def detach(self, path, force=False):
        """
        Eject media from the device.

        If the device has any mounted filesystems, these will be unmounted
        before ejection.

        """
        return self.__path_adapter(self.detach_device, path, force=force)

    # iterate devices
    def is_handleable(self, device):
        """
        Should this device be handled by udiskie?

        Currently this just means that the device is removable and holds a
        filesystem or the device is a LUKS encrypted volume.

        """
        return (device.is_block and
                device.is_external and
                (not self.filter or not self.filter.is_ignored(device)))

    def get_all_handleable(self):
        """
        Enumerate all handleable devices currently known to udisks.

        NOTE: returns only devices that are still valid. This protects from
        race conditions inside udiskie.

        """
        return filter(self.is_handleable, self.udisks)

    # internals
    def __path_adapter(self, fn, path, **kwargs):
        """Internal method."""
        log = logging.getLogger('udiskie.mount.%s' % fn.__name__)
        device = self.udisks.find(path)
        if device:
            log.debug('found device owning "%s": "%s"' % (path, device))
            return fn(device, **kwargs)
        else:
            log.error('no device found owning "%s"' % (path))
            return False

