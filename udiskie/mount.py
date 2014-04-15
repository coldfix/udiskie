"""
Udiskie mount utilities.
"""

import logging
import sys

try:                    # python2
    from itertools import ifilter as filter
except ImportError:     # python3
    pass


__all__ = ['Mounter']


class Mounter(object):

    """
    Mount utility.

    Remembers udisks, prompt and filter instances to use across multiple
    mount operations.
    """

    def __init__(self, filter=None, prompt=None, udisks=None, browser=None):
        """
        Initialize mounter with the given defaults.

        The parameters are not guaranteed to keep their order and should
        always be passed as keyword arguments.

        If udisks is None only the xxx_device methods will work. The
        exception is the force=True branch of remove_device.

        If prompt is None device unlocking will not work.
        """
        self._filter = filter
        self._prompt = prompt
        self._udisks = udisks
        self._browser = browser
        self._logger = logging.getLogger(__name__)
        try:
            self._set_error = self._udisks.set_error
        except AttributeError:
            self._set_error = lambda device, action, message: None

    def browse_device(self, device):
        if not device.is_mounted:
            self._logger.error("not browsing unmounted device: %s" % (device,))
            return False
        if not self._browser:
            self._logger.error("not browsing device: %s, no browser specified" % (device,))
            return False
        self._browser(device.mount_paths[0])
        return True

    # mount/unmount
    def mount_device(self, device):
        """
        Mount the device if not already mounted.

        Return value indicates whether the device is mounted.
        """
        if not self.is_handleable(device) or not device.is_filesystem:
            self._logger.debug('not mounting unhandled device %s' % (device,))
            return False
        if device.is_mounted:
            self._logger.debug('not mounting mounted device %s' % (device,))
            return True
        fstype = str(device.id_type)
        filter = self._filter
        options = ','.join(filter.get_mount_options(device) if filter else [])
        return self.__action(device, 'mount', fstype=fstype, options=options)

    def unmount_device(self, device):
        """
        Unmount a Device.

        Checks to make sure the device is unmountable and then unmounts.
        Return value indicates whether the device is unmounted.
        """
        if not self.is_handleable(device) or not device.is_filesystem:
            self._logger.debug('not unmounting unhandled device %s' % (device,))
            return False
        if not device.is_mounted:
            self._logger.debug('not unmounting unmounted device %s' % (device,))
            return True
        return self.__action(device, 'unmount')

    # unlock/lock (LUKS)
    def unlock_device(self, device):
        """
        Unlock the device if not already unlocked.

        Return value indicates whether the device is unlocked.
        """
        if not self.is_handleable(device) or not device.is_crypto:
            self._logger.debug('not unlocking unhandled device %s' % (device,))
            return False
        if device.is_unlocked:
            self._logger.debug('not unlocking unlocked device %s' % (device,))
            return True
        if not self._prompt:
            self._logger.warn('not unlocking device %s: no prompt available' % (device,))
            return False
        password = self._prompt(device)
        if password is None:
            self._logger.debug('not unlocking device %s: cancelled by user' % (device,))
            return False
        # pass password as non-keyword argument to avoid it being logged
        return self.__action(device, 'unlock', password)

    def lock_device(self, device):
        """
        Lock device.

        Checks to make sure the device is lockable, then locks.
        Return value indicates whether the device is locked.
        """
        if not self.is_handleable(device) or not device.is_crypto:
            self._logger.debug('not locking unhandled device %s' % (device,))
            return False
        if not device.is_unlocked:
            self._logger.debug('not locking locked device %s' % (device,))
            return True
        return self.__action(device, 'lock')

    # add/remove (unlock/lock or mount/unmount)
    def add_device(self, device, recursive=False):
        """Mount or unlock the device depending on its type."""
        if not self.is_handleable(device):
            self._logger.debug('not adding unhandled device %s' % (device,))
            return False
        if device.is_filesystem:
            success = self.mount_device(device)
        elif device.is_crypto:
            success = self.unlock_device(device)
            if success and recursive:
                success = self.add_device(device.luks_cleartext_holder,
                                          recursive=True)
        elif recursive and device.is_partition_table:
            success = True
            for dev in self.get_all_handleable():
                if dev.is_partition and dev.partition_slave == device:
                    success = self.add_device(dev, recursive=True) and success
        else:
            self._logger.debug('not adding unhandled device %s' % (device,))
            success = True
        return success

    def remove_device(self, device, force=False, detach=False, eject=False, lock=False):
        """
        Unmount or lock the device depending on device type.

        If `force` is True recursively unmount/unlock all devices that are
        contained by this device.
        """
        if not self.is_handleable(device):
            self._logger.debug('not removing unhandled device %s' % (device,))
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
            self._logger.debug('not removing unhandled device %s' % (device,))
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
        drive = device.drive
        if not (drive.is_drive and drive.is_ejectable):
            self._logger.debug('drive not ejectable: %s' % drive)
            return False
        if force:
            self.remove_device(drive, force=True)
        return self.__action(device, 'eject')

    def detach_device(self, device, force=False):
        """Detach a device after unmounting all its mounted filesystems."""
        drive = device.root
        if not drive.is_detachable:
            self._logger.debug('drive not detachable: %s' % drive)
            return False
        if force:
            self.remove_device(drive, force=True)
        return self.__action(device, 'detach')

    # mount_all/unmount_all
    def mount_all(self, recursive=False):
        """Mount handleable devices that are already present."""
        success = True
        for device in self.get_all_handleable():
            success = self.add_device(device, recursive=recursive) and success
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
    def mount(self, path, recursive=False):
        """
        Mount or unlock a device.

        The device must match the criteria for a filesystem mountable or
        unlockable by udiskie.
        """
        return self.__path_adapter(self.add_device, path, recursive=recursive)

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
                (not self._filter or not self._filter.is_ignored(device)))

    def get_all_handleable(self):
        """
        Enumerate all handleable devices currently known to udisks.

        NOTE: returns only devices that are still valid. This protects from
        race conditions inside udiskie.
        """
        return filter(self.is_handleable, self._udisks)

    # internals
    def __path_adapter(self, fn, path, **kwargs):
        """Internal method."""
        device = self._udisks.find(path)
        if device:
            self._logger.debug('found device owning "%s": "%s"' % (path, device))
            return fn(device, **kwargs)
        else:
            self._logger.error('no device found owning "%s"' % (path))
            return False

    def __action(self, device, action, *args, **kwargs):
        """
        Internal method: Perform action, log errors and return success.

        All keyword parameters will be logged. For private parameters, such
        as the password for unlock, positional parameters must be used.
        """
        self._logger.debug('{0}ing {1} with {2}'
                            .format(action, device, kwargs))
        try:
            result = getattr(device, action)(*args, **kwargs)
        except device.Exception:
            err = sys.exc_info()[1]
            self._logger.error('failed to {0} {1}: {2}'
                            .format(action, device, err.message))
            self._set_error(device, action, err.message)
            return False
        else:
            self._logger.info('{0}ed {1} => {2}'
                            .format(action, device, result))
            return True
