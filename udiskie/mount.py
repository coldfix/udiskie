"""
Mount utilities.
"""

from functools import wraps
import logging
import sys

try:                    # python2
    from itertools import ifilter as filter
except ImportError:     # python3
    pass

try:                    # python2
    basestring
except NameError:       # python3
    basestring = str


__all__ = ['Mounter']


class Mounter(object):

    """
    Mount utility.

    Stores environment variables (filter, prompt, browser, udisks) to use
    across multiple mount operations.

    :ivar udisks: adapter to the udisks service

    NOTE: The optional parameters are not guaranteed to keep their order and
    should always be passed as keyword arguments.
    """

    def __init__(self, udisks, filter=None, prompt=None, browser=None):
        """
        Initialize mounter with the given defaults.

        :param udisks: udisks service object. May be a Sniffer or a Daemon.
        :param FilterMatcher filter: customize mount options and handleability
        :param callable prompt: retrieve passwords for devices
        :param callable browser: open devices

        If prompt is None, device unlocking will not work.
        If browser is None, browse will not work.
        """
        self.udisks = udisks
        self._filter = filter
        self._prompt = prompt
        self._browser = browser
        self._logger = logging.getLogger(__name__)
        try:
            # propagate error messages to UDisks1 daemon for 'Job failed'
            # notifications.
            self._set_error = self.udisks.set_error
        except AttributeError:
            self._set_error = lambda device, action, message: None

    def browse(self, device_or_path):
        """
        Browse device.

        :param device_or_path: device object, block device path or mount path
        :returns: success
        :rtype: bool
        :raises IOError: if the path does not correspond to a device
        """
        device = self._get_device(device_or_path)
        if not device.is_mounted:
            self._logger.error("not browsing unmounted device: %s" % (device,))
            return False
        if not self._browser:
            self._logger.error("not browsing device: %s, no browser specified" % (device,))
            return False
        self._browser(device.mount_paths[0])
        return True

    # mount/unmount
    def mount(self, device_or_path):
        """
        Mount the device if not already mounted.

        :param device_or_path: device object, block device path or mount path
        :returns: whether the device is mounted.
        :rtype: bool
        :raises IOError: if the path does not correspond to a device
        """
        device = self._get_device(device_or_path)
        if not self.is_handleable(device) or not device.is_filesystem:
            self._logger.debug('not mounting unhandled device %s' % (device,))
            return False
        if device.is_mounted:
            self._logger.debug('not mounting mounted device %s' % (device,))
            return True
        fstype = str(device.id_type)
        filter = self._filter
        options = ','.join(filter.get_mount_options(device) if filter else [])
        return self._action(device, 'mount', fstype=fstype, options=options)

    def unmount(self, device_or_path):
        """
        Unmount a Device if mounted.

        :param device_or_path: device object, block device path or mount path
        :returns: whether the device is unmounted
        :rtype: bool
        :raises IOError: if the path does not correspond to a device
        """
        device = self._get_device(device_or_path)
        if not self.is_handleable(device) or not device.is_filesystem:
            self._logger.debug('not unmounting unhandled device %s' % (device,))
            return False
        if not device.is_mounted:
            self._logger.debug('not unmounting unmounted device %s' % (device,))
            return True
        return self._action(device, 'unmount')

    # unlock/lock (LUKS)
    def unlock(self, device_or_path):
        """
        Unlock the device if not already unlocked.

        :param device_or_path: device object, block device path or mount path
        :returns: whether the device is unlocked
        :rtype: bool
        :raises IOError: if the path does not correspond to a device
        """
        device = self._get_device(device_or_path)
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
        return self._action(device, 'unlock', password)

    def lock(self, device_or_path):
        """
        Lock device if unlocked.

        :param device_or_path: device object, block device path or mount path
        :returns: whether the device is locked
        :rtype: bool
        :raises IOError: if the path does not correspond to a device
        """
        device = self._get_device(device_or_path)
        if not self.is_handleable(device) or not device.is_crypto:
            self._logger.debug('not locking unhandled device %s' % (device,))
            return False
        if not device.is_unlocked:
            self._logger.debug('not locking locked device %s' % (device,))
            return True
        return self._action(device, 'lock')

    # add/remove (unlock/lock or mount/unmount)
    def add(self, device_or_path, recursive=False):
        """
        Mount or unlock the device depending on its type.

        :param device_or_path: device object, block device path or mount path
        :param bool recursive: recursively mount and unlock child devices
        :returns: whether all attempted operations succeeded
        :rtype: bool
        :raises IOError: if the path does not correspond to a device
        """
        device = self._get_device(device_or_path)
        if not self.is_handleable(device):
            self._logger.debug('not adding unhandled device %s' % (device,))
            return False
        if device.is_filesystem:
            success = self.mount(device)
        elif device.is_crypto:
            success = self.unlock(device)
            if success and recursive:
                success = self.add(device.luks_cleartext_holder,
                                          recursive=True)
        elif recursive and device.is_partition_table:
            success = True
            for dev in self.get_all_handleable():
                if dev.is_partition and dev.partition_slave == device:
                    success = self.add(dev, recursive=True) and success
        else:
            self._logger.debug('not adding unhandled device %s' % (device,))
            success = True
        return success

    def remove(self, device_or_path, force=False, detach=False, eject=False,
               lock=False):
        """
        Unmount or lock the device depending on device type.

        :param device_or_path: device object, block device path or mount path
        :param bool force: recursively remove all child devices
        :param bool detach: detach the root drive
        :param bool eject: remove media from the root drive
        :param bool lock: lock the associated LUKS cleartext slave
        :returns: whether all attempted operations succeeded
        :rtype: bool
        :raises IOError: if the path does not correspond to a device
        """
        device = self._get_device(device_or_path)
        if not self.is_handleable(device):
            self._logger.debug('not removing unhandled device %s' % (device,))
            return False
        if device.is_filesystem:
            success = self.unmount(device)
        elif device.is_crypto:
            if force and device.is_unlocked:
                self.remove(device.luks_cleartext_holder, force=True)
            success = self.lock(device)
        elif force and (device.is_partition_table or device.is_drive):
            success = True
            for dev in self.get_all_handleable():
                if ((dev.is_partition and dev.partition_slave == device) or
                    (dev.is_toplevel and dev.drive == device and dev != device)):
                    success = self.remove(dev, force=True, detach=detach, eject=eject, lock=lock) and success
        else:
            self._logger.debug('not removing unhandled device %s' % (device,))
            success = True
        if lock and device.is_luks_cleartext:
            success = self.lock(device.luks_cleartext_slave)
        if eject and device.is_drive and device.is_ejectable:
            success = self.eject(device) and success
        if detach and device.is_drive and device.is_detachable:
            success = self.detach(device) and success
        return success

    # eject/detach device
    def eject(self, device_or_path, force=False):
        """
        Eject a device after unmounting all its mounted filesystems.

        :param device_or_path: device object, block device path or mount path
        :param bool force: remove child devices before trying to eject
        :returns: whether the operation succeeded
        :rtype: bool
        :raises IOError: if the path does not correspond to a device
        """
        device = self._get_device(device_or_path)
        drive = device.drive
        if not (drive.is_drive and drive.is_ejectable):
            self._logger.debug('drive not ejectable: %s' % drive)
            return False
        if force:
            self.remove(drive, force=True)
        return self._action(device, 'eject')

    def detach(self, device_or_path, force=False):
        """
        Detach a device after unmounting all its mounted filesystems.

        :param device_or_path: device object, block device path or mount path
        :param bool force: remove child devices before trying to detach
        :returns: whether the operation succeeded
        :rtype: bool
        :raises IOError: if the path does not correspond to a device
        """
        device = self._get_device(device_or_path)
        drive = device.root
        if not drive.is_detachable:
            self._logger.debug('drive not detachable: %s' % drive)
            return False
        if force:
            self.remove(drive, force=True)
        return self._action(device, 'detach')

    # mount_all/unmount_all
    def mount_all(self, recursive=False):
        """
        Mount handleable devices that are already present.

        :param bool recursive: recursively mount and unlock child devices
        :returns: whether all attempted operations succeeded
        :rtype: bool
        """
        success = True
        for device in self.get_all_handleable():
            success = self.add(device, recursive=recursive) and success
        return success

    def unmount_all(self, detach=False, eject=False, lock=False):
        """
        Unmount all filesystems handleable by udiskie.

        :param bool detach: detach the root drive
        :param bool eject: remove media from the root drive
        :param bool lock: lock the associated LUKS cleartext slave
        :returns: whether all attempted operations succeeded
        :rtype: bool
        """
        success = True
        for device in self.get_all_handleable():
            success = self.remove(device, force=True,
                                  detach=detach, eject=eject,
                                  lock=True) and success
        return success

    def eject_all(self, force=True):
        """
        Eject all ejectable devices.

        :param bool force: remove child devices before trying to eject
        :returns: whether all attempted operations succeeded
        :rtype: bool
        """
        success = True
        for device in self.get_all_handleable():
            if device.is_drive and device.is_ejectable:
                success = self.eject(device, force=force) and success
        return success

    def detach_all(self, force=True):
        """
        Detach all detachable devices.

        :param bool force: remove child devices before trying to detach
        :returns: whether all attempted operations succeeded
        :rtype: bool
        """
        success = True
        for device in self.get_all_handleable():
            if device.is_drive and device.is_detachable:
                success = self.detach(device, force=force) and success
        return success

    # iterate devices
    def is_handleable(self, device_or_path):
        """
        Check whether this device should be handled by udiskie.

        :param device_or_path: device object, block device path or mount path
        :returns: handleability
        :rtype: bool

        Currently this just means that the device is removable and holds a
        filesystem or the device is a LUKS encrypted volume.
        """
        device = self._get_device(device_or_path)
        return (device.is_block and
                device.is_external and
                (not self._filter or not self._filter.is_ignored(device)))

    def get_all_handleable(self):
        """
        Enumerate all handleable devices currently known to udisks.

        :returns: handleable devices
        :rtype: iterable

        NOTE: returns only devices that are still valid. This protects from
        race conditions inside udiskie.
        """
        return filter(self.is_handleable, self.udisks)

    # internals
    def _get_device(self, device_or_path):
        """
        Resolve pathes to device object.

        :param device_or_path: device object, block device path or mount path
        :returns: device object
        :rtype: Device
        :raises IOError: if the path does not belong to a block device
        """
        if isinstance(device_or_path, basestring):
            device = self.udisks.find(device_or_path)
            if not device:
                self._logger.error('no device found owning "%s"' % (device_or_path,))
                raise IOError('no device found owning "%s"' % (device_or_path,))
            self._logger.debug('found device owning "%s": "%s"' % (device_or_path, device))
            return device
        else:
            return device_or_path

    def _action(self, device, action, *args, **kwargs):
        """
        Perform action, log errors and return success.

        :param device: operated device
        :param str action: on of mount|unmount|unlock|lock|eject|detach
        :param *args: secure parameters (not to be logged)
        :param **kwargs: unsecure parameters (to be logged)

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
