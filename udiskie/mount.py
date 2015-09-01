"""
Mount utilities.
"""

from collections import namedtuple
from functools import partial
import logging
import sys

from udiskie.common import wraps, setdefault
from udiskie.compat import filter, basestring
from udiskie.config import IgnoreDevice, FilterMatcher
from udiskie.locale import _


__all__ = ['Mounter']


def _device_method(fn):
    @wraps(fn)
    def wrapper(self, device_or_path, *args, **kwargs):
        if isinstance(device_or_path, basestring):
            device = self.udisks.find(device_or_path)
            if device:
                self._log.debug(_('found device owning "{0}": "{1}"',
                                  device_or_path, device))
            else:
                self._log.error(_('no device found owning "{0}"',
                                  device_or_path))
                return False
        else:
            device = device_or_path
        try:
            return fn(self, device, *args, **kwargs)
        except device.Exception:
            err = sys.exc_info()[1]
            self._log.error(_('failed to {0} {1}: {2}',
                              fn.__name__, device, err.message))
            self._set_error(device, fn.__name__, err.message)
            return False
    return wrapper


def _is_parent_of(parent, child):
    """Check whether the first device is the parent of the second device."""
    if child.is_partition:
        return child.partition_slave == parent
    if child.is_toplevel:
        return child.drive == parent and child != parent
    return False


class Mounter(object):

    """
    Mount utility.

    Stores environment variables (filter, prompt, browser, udisks) to use
    across multiple mount operations.

    :ivar udisks: adapter to the udisks service

    NOTE: The optional parameters are not guaranteed to keep their order and
    should always be passed as keyword arguments.
    """

    def __init__(self, udisks,
                 mount_options=None,
                 ignore_device=None,
                 prompt=None,
                 browser=None):
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
        self._mount_options = mount_options or (lambda device: None)
        self._ignore_device = ignore_device or FilterMatcher([], False)
        self._ignore_device._filters += [
            IgnoreDevice({'is_block': False, 'ignore': True}),
            IgnoreDevice({'is_external': False, 'ignore': True}),
            IgnoreDevice({'is_ignored': True, 'ignore': True})]
        self._prompt = prompt
        self._browser = browser
        self._log = logging.getLogger(__name__)
        try:
            # propagate error messages to UDisks1 daemon for 'Job failed'
            # notifications.
            self._set_error = self.udisks.set_error
        except AttributeError:
            self._set_error = lambda device, action, message: None

    @_device_method
    def browse(self, device):
        """
        Browse device.

        :param device: device object, block device path or mount path
        :returns: success
        :rtype: bool
        """
        if not device.is_mounted:
            self._log.error(_("not browsing {0}: not mounted", device))
            return False
        if not self._browser:
            self._log.error(_("not browsing {0}: no program", device))
            return False
        self._log.debug(_('opening {0} on {0.mount_paths[0]}', device))
        self._browser(device.mount_paths[0])
        self._log.info(_('opened {0} on {0.mount_paths[0]}', device))
        return True

    # mount/unmount
    @_device_method
    def mount(self, device):
        """
        Mount the device if not already mounted.

        :param device: device object, block device path or mount path
        :returns: whether the device is mounted.
        :rtype: bool
        """
        if not self.is_handleable(device) or not device.is_filesystem:
            self._log.warn(_('not mounting {0}: unhandled device', device))
            return False
        if device.is_mounted:
            self._log.info(_('not mounting {0}: already mounted', device))
            return True
        fstype = str(device.id_type)
        options = self._mount_options(device)
        kwargs = dict(fstype=fstype, options=options)
        self._log.debug(_('mounting {0} with {1}', device, kwargs))
        mount_path = device.mount(**kwargs)
        self._log.info(_('mounted {0} on {1}', device, mount_path))
        return True

    @_device_method
    def unmount(self, device):
        """
        Unmount a Device if mounted.

        :param device: device object, block device path or mount path
        :returns: whether the device is unmounted
        :rtype: bool
        """
        if not self.is_handleable(device) or not device.is_filesystem:
            self._log.warn(_('not unmounting {0}: unhandled device', device))
            return False
        if not device.is_mounted:
            self._log.info(_('not unmounting {0}: not mounted', device))
            return True
        self._log.debug(_('unmounting {0}', device))
        device.unmount()
        self._log.info(_('unmounted {0}', device))
        return True

    # unlock/lock (LUKS)
    @_device_method
    def unlock(self, device):
        """
        Unlock the device if not already unlocked.

        :param device: device object, block device path or mount path
        :returns: whether the device is unlocked
        :rtype: bool
        """
        if not self.is_handleable(device) or not device.is_crypto:
            self._log.warn(_('not unlocking {0}: unhandled device', device))
            return False
        if device.is_unlocked:
            self._log.info(_('not unlocking {0}: already unlocked', device))
            return True
        if not self._prompt:
            self._log.error(_('not unlocking {0}: no password prompt', device))
            return False
        password = self._prompt(device)
        if password is None:
            self._log.debug(_('not unlocking {0}: cancelled by user', device))
            return False
        self._log.debug(_('unlocking {0}', device))
        device.unlock(password)
        self._log.info(_('unlocked {0}', device))
        return True

    @_device_method
    def lock(self, device):
        """
        Lock device if unlocked.

        :param device: device object, block device path or mount path
        :returns: whether the device is locked
        :rtype: bool
        """
        if not self.is_handleable(device) or not device.is_crypto:
            self._log.warn(_('not locking {0}: unhandled device', device))
            return False
        if not device.is_unlocked:
            self._log.info(_('not locking {0}: not unlocked', device))
            return True
        self._log.debug(_('locking {0}', device))
        device.lock()
        self._log.info(_('locked {0}', device))
        return True

    # add/remove (unlock/lock or mount/unmount)
    @_device_method
    def add(self, device, recursive=False):
        """
        Mount or unlock the device depending on its type.

        :param device: device object, block device path or mount path
        :param bool recursive: recursively mount and unlock child devices
        :returns: whether all attempted operations succeeded
        :rtype: bool
        """
        if device.is_filesystem:
            success = self.mount(device)
        elif device.is_crypto:
            success = self.unlock(device)
            if success and recursive:
                # TODO: update device
                success = self.add(device.luks_cleartext_holder,
                                   recursive=True)
        elif recursive and device.is_partition_table:
            success = True
            for dev in self.get_all_handleable():
                if dev.is_partition and dev.partition_slave == device:
                    success = self.add(dev, recursive=True) and success
        else:
            self._log.info(_('not adding {0}: unhandled device', device))
            return False
        return success

    @_device_method
    def remove(self, device, force=False, detach=False, eject=False,
               lock=False):
        """
        Unmount or lock the device depending on device type.

        :param device: device object, block device path or mount path
        :param bool force: recursively remove all child devices
        :param bool detach: detach the root drive
        :param bool eject: remove media from the root drive
        :param bool lock: lock the associated LUKS cleartext slave
        :returns: whether all attempted operations succeeded
        :rtype: bool
        """
        if device.is_filesystem:
            success = self.unmount(device)
        elif device.is_crypto:
            if force and device.is_unlocked:
                self.remove(device.luks_cleartext_holder, force=True)
            success = self.lock(device)
        elif force and (device.is_partition_table or device.is_drive):
            success = True
            for child in self.get_all_handleable():
                if _is_parent_of(device, child):
                    success = self.remove(child,
                                          force=True,
                                          detach=detach,
                                          eject=eject,
                                          lock=lock) and success
        else:
            self._log.info(_('not removing {0}: unhandled device', device))
            success = False
        # if these operations work, everything is fine, we can return True:
        if lock and device.is_luks_cleartext:
            device = device.luks_cleartext_slave
            success = self.lock(device)
        if eject:
            success = self.eject(device)
        if detach:
            success = self.detach(device)
        return success

    # eject/detach device
    @_device_method
    def eject(self, device, force=False):
        """
        Eject a device after unmounting all its mounted filesystems.

        :param device: device object, block device path or mount path
        :param bool force: remove child devices before trying to eject
        :returns: whether the operation succeeded
        :rtype: bool
        """
        if not self.is_handleable(device):
            self._log.warn(_('not ejecting {0}: unhandled device'))
            return False
        drive = device.drive
        if not (drive.is_drive and drive.is_ejectable):
            self._log.warn(_('not ejecting {0}: drive not ejectable', drive))
            return False
        if force:
            self.remove(drive, force=True)
        self._log.debug(_('ejecting {0}', device))
        drive.eject()
        self._log.info(_('ejected {0}', device))
        return True

    @_device_method
    def detach(self, device, force=False):
        """
        Detach a device after unmounting all its mounted filesystems.

        :param device: device object, block device path or mount path
        :param bool force: remove child devices before trying to detach
        :returns: whether the operation succeeded
        :rtype: bool
        """
        if not self.is_handleable(device):
            self._log.warn(_('not detaching {0}: unhandled device'))
            return False
        drive = device.root
        if not drive.is_detachable:
            self._log.warn(_('not detaching {0}: drive not detachable', drive))
            return False
        if force:
            self.remove(drive, force=True)
        self._log.debug(_('detaching {0}', device))
        drive.detach()
        self._log.info(_('detached {0}', device))
        return True

    # mount_all/unmount_all
    def add_all(self, recursive=False):
        """
        Add all handleable devices that available at start.

        :param bool recursive: recursively mount and unlock child devices
        :returns: whether all attempted operations succeeded
        :rtype: bool
        """
        success = True
        for device in self.get_all_handleable():
            if (device.is_filesystem
                    or device.is_crypto
                    or (recursive and device.is_partition_table)):
                success = self.add(device, recursive=recursive) and success
        return success

    def remove_all(self, detach=False, eject=False, lock=False):
        """
        Remove all filesystems handleable by udiskie.

        :param bool detach: detach the root drive
        :param bool eject: remove media from the root drive
        :param bool lock: lock the associated LUKS cleartext slave
        :returns: whether all attempted operations succeeded
        :rtype: bool
        """
        success = True
        remove_args = dict(force=True, detach=detach, eject=eject, lock=lock)
        for device in self.get_all_handleable():
            if (device.is_filesystem
                    or device.is_crypto
                    or device.is_partition_table
                    or device.is_drive):
                success = self.remove(device, **remove_args) and success
        return success

    def mount_all(self):
        """
        Mount handleable devices that are already present.

        :returns: whether all attempted operations succeeded
        :rtype: bool
        """
        success = True
        for device in self.get_all_handleable():
            success = self.mount(device) and success
        return success

    def unmount_all(self):
        """
        Unmount all filesystems handleable by udiskie.

        :returns: whether all attempted operations succeeded
        :rtype: bool
        """
        success = True
        for device in self.get_all_handleable():
            success = self.unmount(device) and success
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
    @_device_method
    def is_handleable(self, device):
        """
        Check whether this device should be handled by udiskie.

        :param device: device object, block device path or mount path
        :returns: handleability
        :rtype: bool

        Currently this just means that the device is removable and holds a
        filesystem or the device is a LUKS encrypted volume.
        """
        return not self._ignore_device(device)

    def get_all_handleable(self):
        """
        Enumerate all handleable devices currently known to udisks.

        :returns: handleable devices
        :rtype: iterable

        NOTE: returns only devices that are still valid. This protects from
        race conditions inside udiskie.
        """
        return filter(self.is_handleable, self.udisks)


# data structs containing the menu hierarchy:
Device = namedtuple('Device', ['root', 'branches', 'device', 'label', 'methods'])
Action = namedtuple('Action', ['method', 'device', 'label', 'action'])
Branch = namedtuple('Branch', ['label', 'groups'])


class DeviceActions(object):

    _labels = {
        'browse': _('Browse {0}'),
        'mount': _('Mount {0}'),
        'unmount': _('Unmount {0}'),
        'unlock': _('Unlock {0}'),
        'lock': _('Lock {0}'),
        'eject': _('Eject {0}'),
        'detach': _('Unpower {0}'),
    }

    def __init__(self, mounter, actions={}):
        self._mounter = mounter
        self._actions = _actions = actions.copy()
        setdefault(_actions, {
            'browse': mounter.browse,
            'mount': mounter.mount,
            'unmount': mounter.unmount,
            'unlock': mounter.unlock,
            'lock': partial(mounter.remove, force=True),
            'eject': partial(mounter.eject, force=True),
            'detach': partial(mounter.detach, force=True),
        })

    def detect(self, root_device=''):
        """
        Detect all currently known devices.

        :param str root_device: object path of root device to return
        :returns: root of device hierarchy
        :rtype: Device
        """
        root = Device(None, [], None, "", [])
        device_nodes = dict(map(self._device_node,
                                self._mounter.get_all_handleable()))
        # insert child devices as branches into their roots:
        for object_path, node in device_nodes.items():
            device_nodes.get(node.root, root).branches.append(node)
        if not root_device:
            return root
        return device_nodes[root_device]

    def _get_device_methods(self, device):
        """Return an iterable over all available methods the device has."""
        if device.is_filesystem:
            if device.is_mounted:
                yield 'browse'
                yield 'unmount'
            else:
                yield 'mount'
        elif device.is_crypto:
            if device.is_unlocked:
                yield 'lock'
            else:
                yield 'unlock'
        if device.is_ejectable and device.has_media:
            yield 'eject'
        if device.is_detachable:
            yield 'detach'

    def _device_node(self, device):
        """Create an empty menu node for the specified device."""
        label = device.id_label or device.device_presentation
        # determine available methods
        methods = [Action(method, device,
                          self._labels[method].format(label),
                          partial(self._actions[method], device))
                   for method in self._get_device_methods(device)]
        # find the root device:
        if device.is_partition:
            root = device.partition_slave.object_path
        elif device.is_luks_cleartext:
            root = device.luks_cleartext_slave.object_path
        else:
            root = None
        # in this first step leave branches empty
        return device.object_path, Device(root, [], device, label, methods)
