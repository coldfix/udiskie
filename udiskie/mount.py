"""
Mount utilities.
"""

from __future__ import absolute_import
from __future__ import unicode_literals

from collections import namedtuple
from functools import partial
import logging

from .async_ import AsyncList, Coroutine, Return
from .common import wraps, setdefault, exc_message
from .config import IgnoreDevice, FilterMatcher
from .locale import _


__all__ = ['Mounter']


# TODO: add / remove / XXX_all should make proper use of the asynchronous
# execution.


@Coroutine.from_generator_function
def _False():
    yield Return(False)


def _find_device(fn, set_error=False):
    """
    Decorator for Mounter methods taking a Device as their first argument.

    Enables to pass the path name as first argument and does some common error
    handling (logging).
    """
    @wraps(fn)
    def wrapper(self, device_or_path, *args, **kwargs):
        try:
            device = self.udisks.find(device_or_path)
        except ValueError as e:
            self._log.error(exc_message(e))
            return _False()
        return Coroutine(fn(self, device, *args, **kwargs))
    return wrapper


def _sets_async_error(fn):
    @wraps(fn)
    def wrapper(self, device, *args, **kwargs):
        async_ = fn(self, device, *args, **kwargs)
        async_.errbacks.append(partial(self._error, fn, device))
        return async_
    return wrapper


def _suppress_error(fn):
    """
    Prevent errors in this function from being shown. This is OK, since all
    errors happen in sub-functions in which errors ARE logged.
    """
    @wraps(fn)
    def wrapper(self, device, *args, **kwargs):
        async_ = fn(self, device, *args, **kwargs)
        async_.errbacks.append(lambda *args: True)
        return async_
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
                 browser=None,
                 cache=None):
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
            IgnoreDevice({'symlinks': '/dev/mapper/docker-*', 'ignore': True}),
            IgnoreDevice({'symlinks': '/dev/disk/by-id/dm-name-docker-*', 'ignore': True}),
            IgnoreDevice({'is_block': False, 'ignore': True}),
            IgnoreDevice({'is_external': False, 'ignore': True}),
            IgnoreDevice({'is_ignored': True, 'ignore': True})]
        self._prompt = prompt
        self._browser = browser
        self._cache = cache
        self._log = logging.getLogger(__name__)
        try:
            # propagate error messages to UDisks1 daemon for 'Job failed'
            # notifications.
            self._set_error = self.udisks.set_error
        except AttributeError:
            self._set_error = lambda device, action, message: None

    def _error(self, fn, device, err, fmt):
        message = exc_message(err)
        self._log.error(_('failed to {0} {1}: {2}',
                          fn.__name__, device, message))
        self._set_error(device, fn.__name__, message)
        return True

    @_sets_async_error
    @_find_device
    def browse(self, device):
        """
        Browse device.

        :param device: device object, block device path or mount path
        :returns: success
        :rtype: bool
        """
        if not device.is_mounted:
            self._log.error(_("not browsing {0}: not mounted", device))
            yield Return(False)
        if not self._browser:
            self._log.error(_("not browsing {0}: no program", device))
            yield Return(False)
        self._log.debug(_('opening {0} on {0.mount_paths[0]}', device))
        self._browser(device.mount_paths[0])
        self._log.info(_('opened {0} on {0.mount_paths[0]}', device))
        yield Return(True)

    # mount/unmount
    @_sets_async_error
    @_find_device
    def mount(self, device):
        """
        Mount the device if not already mounted.

        :param device: device object, block device path or mount path
        :returns: whether the device is mounted.
        :rtype: bool
        """
        if not self.is_handleable(device) or not device.is_filesystem:
            self._log.warn(_('not mounting {0}: unhandled device', device))
            yield Return(False)
        if device.is_mounted:
            self._log.info(_('not mounting {0}: already mounted', device))
            yield Return(True)
        fstype = str(device.id_type)
        options = self._mount_options(device)
        kwargs = dict(fstype=fstype, options=options)
        self._log.debug(_('mounting {0} with {1}', device, kwargs))
        mount_path = yield device.mount(**kwargs)
        self._log.info(_('mounted {0} on {1}', device, mount_path))
        yield Return(True)

    @_sets_async_error
    @_find_device
    def unmount(self, device):
        """
        Unmount a Device if mounted.

        :param device: device object, block device path or mount path
        :returns: whether the device is unmounted
        :rtype: bool
        """
        if not self.is_handleable(device) or not device.is_filesystem:
            self._log.warn(_('not unmounting {0}: unhandled device', device))
            yield Return(False)
        if not device.is_mounted:
            self._log.info(_('not unmounting {0}: not mounted', device))
            yield Return(True)
        self._log.debug(_('unmounting {0}', device))
        yield device.unmount()
        self._log.info(_('unmounted {0}', device))
        yield Return(True)

    # unlock/lock (LUKS)
    @_sets_async_error
    @_find_device
    def unlock(self, device):
        """
        Unlock the device if not already unlocked.

        :param device: device object, block device path or mount path
        :returns: whether the device is unlocked
        :rtype: bool
        """
        if not self.is_handleable(device) or not device.is_crypto:
            self._log.warn(_('not unlocking {0}: unhandled device', device))
            yield Return(False)
        if device.is_unlocked:
            self._log.info(_('not unlocking {0}: already unlocked', device))
            yield Return(True)
        if not self._prompt:
            self._log.error(_('not unlocking {0}: no password prompt', device))
            yield Return(False)
        unlocked = yield self._unlock_from_cache(device)
        if unlocked:
            yield Return(True)
        password = yield self._prompt(device)
        if password is None:
            self._log.debug(_('not unlocking {0}: cancelled by user', device))
            yield Return(False)
        self._log.debug(_('unlocking {0}', device))
        yield device.unlock(password)
        self._update_cache(device, password)
        self._log.info(_('unlocked {0}', device))
        yield Return(True)

    @Coroutine.from_generator_function
    def _unlock_from_cache(self, device):
        if not self._cache:
            yield Return(False)
        try:
            password = self._cache[device]
        except KeyError:
            yield Return(False)
        self._log.debug(_('unlocking {0} using cached password', device))
        try:
            yield device.unlock(password)
        except Exception:
            self._log.debug(_('failed to unlock {0} using cached password', device))
            yield Return(False)
        self._log.debug(_('unlocked {0} using cached password', device))
        yield Return(True)

    def _update_cache(self, device, password):
        if not self._cache:
            return
        self._cache[device] = password

    def forget_password(self, device):
        try:
            del self._cache[device]
        except KeyError:
            pass

    @_sets_async_error
    @_find_device
    def lock(self, device):
        """
        Lock device if unlocked.

        :param device: device object, block device path or mount path
        :returns: whether the device is locked
        :rtype: bool
        """
        if not self.is_handleable(device) or not device.is_crypto:
            self._log.warn(_('not locking {0}: unhandled device', device))
            yield Return(False)
        if not device.is_unlocked:
            self._log.info(_('not locking {0}: not unlocked', device))
            yield Return(True)
        self._log.debug(_('locking {0}', device))
        yield device.lock()
        self._log.info(_('locked {0}', device))
        yield Return(True)

    # add/remove (unlock/lock or mount/unmount)
    @_suppress_error
    @_find_device
    def add(self, device, recursive=False):
        """
        Mount or unlock the device depending on its type.

        :param device: device object, block device path or mount path
        :param bool recursive: recursively mount and unlock child devices
        :returns: whether all attempted operations succeeded
        :rtype: bool
        """
        if device.is_filesystem:
            success = yield self.mount(device)
        elif device.is_crypto:
            success = yield self.unlock(device)
            if success and recursive:
                self.udisks._sync()
                device = self.udisks[device.object_path]
                success = yield self.add(
                    device.luks_cleartext_holder,
                    recursive=True)
        elif recursive and device.is_partition_table:
            tasks = []
            for dev in self.get_all_handleable():
                if dev.is_partition and dev.partition_slave == device:
                    tasks.append(self.add(dev, recursive=True))
            results = yield AsyncList(tasks)
            success = all(results)
        else:
            self._log.info(_('not adding {0}: unhandled device', device))
            yield Return(False)
        yield Return(success)

    @_suppress_error
    @_find_device
    def auto_add(self, device, recursive=False):
        """
        Automatically attempt to mount or unlock a device, but be quiet if the
        device is not supported.

        :param device: device object, block device path or mount path
        :param bool recursive: recursively mount and unlock child devices
        :returns: whether all attempted operations succeeded
        :rtype: bool
        """
        success = True
        if not self.is_handleable(device):
            pass
        elif device.is_filesystem:
            if not device.is_mounted:
                success = yield self.mount(device)
        elif device.is_crypto:
            if self._prompt and not device.is_unlocked:
                success = yield self.unlock(device)
            if success and recursive:
                self.udisks._sync()
                device = self.udisks[device.object_path]
                success = yield self.auto_add(
                    device.luks_cleartext_holder,
                    recursive=True)
        elif recursive and device.is_partition_table:
            tasks = []
            for dev in self.get_all_handleable():
                if dev.is_partition and dev.partition_slave == device:
                    tasks.append(self.auto_add(dev, recursive=True))
            results = yield AsyncList(tasks)
            success = all(results)
        else:
            self._log.debug(_('not adding {0}: unhandled device', device))
        yield Return(success)

    @_suppress_error
    @_find_device
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
            success = yield self.unmount(device)
        elif device.is_crypto:
            if force and device.is_unlocked:
                yield self.auto_remove(device.luks_cleartext_holder, force=True)
            success = yield self.lock(device)
        elif force and (device.is_partition_table or device.is_drive):
            tasks = []
            for child in self.get_all_handleable():
                if _is_parent_of(device, child):
                    tasks.append(self.auto_remove(
                        child,
                        force=True,
                        detach=detach,
                        eject=eject,
                        lock=lock))
            results = yield AsyncList(tasks)
            success = all(results)
        else:
            self._log.info(_('not removing {0}: unhandled device', device))
            success = False
        # if these operations work, everything is fine, we can return True:
        if lock and device.is_luks_cleartext:
            device = device.luks_cleartext_slave
            success = yield self.lock(device)
        if eject:
            success = yield self.eject(device)
        if detach:
            success = yield self.detach(device)
        yield Return(success)

    @_suppress_error
    @_find_device
    def auto_remove(self, device, force=False, detach=False, eject=False,
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
        success = True
        if not self.is_handleable(device):
            pass
        elif device.is_filesystem:
            if device.is_mounted:
                success = yield self.unmount(device)
        elif device.is_crypto:
            if force and device.is_unlocked:
                yield self.auto_remove(device.luks_cleartext_holder, force=True)
            if device.is_unlocked:
                success = yield self.lock(device)
        elif force and (device.is_partition_table or device.is_drive):
            tasks = []
            for child in self.get_all_handleable():
                if _is_parent_of(device, child):
                    tasks.append(self.auto_remove(
                        child,
                        force=True,
                        detach=detach,
                        eject=eject,
                        lock=lock))
            results = yield AsyncList(tasks)
            success = all(results)
        else:
            self._log.debug(_('not removing {0}: unhandled device', device))
        # if these operations work, everything is fine, we can return True:
        if lock and device.is_luks_cleartext:
            device = device.luks_cleartext_slave
            success = yield self.lock(device)
        if eject and device.has_media:
            success = yield self.eject(device)
        if detach and device.is_detachable:
            success = yield self.detach(device)
        yield Return(success)

    # eject/detach device
    @_sets_async_error
    @_find_device
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
            yield Return(False)
        drive = device.drive
        if not (drive.is_drive and drive.is_ejectable):
            self._log.warn(_('not ejecting {0}: drive not ejectable', drive))
            yield Return(False)
        if force:
            yield self.auto_remove(drive, force=True)
        self._log.debug(_('ejecting {0}', device))
        yield drive.eject()
        self._log.info(_('ejected {0}', device))
        yield Return(True)

    @_sets_async_error
    @_find_device
    def detach(self, device, force=False):
        """
        Detach a device after unmounting all its mounted filesystems.

        :param device: device object, block device path or mount path
        :param bool force: remove child devices before trying to detach
        :returns: whether the operation succeeded
        :rtype: bool
        """
        if not self.is_handleable(device):
            self._log.warn(_('not detaching {0}: unhandled device', device))
            yield Return(False)
        drive = device.root
        if not drive.is_detachable:
            self._log.warn(_('not detaching {0}: drive not detachable', drive))
            yield Return(False)
        if force:
            yield self.auto_remove(drive, force=True)
        self._log.debug(_('detaching {0}', device))
        yield drive.detach()
        self._log.info(_('detached {0}', device))
        yield Return(True)

    # mount_all/unmount_all
    @Coroutine.from_generator_function
    def add_all(self, recursive=False):
        """
        Add all handleable devices that available at start.

        :param bool recursive: recursively mount and unlock child devices
        :returns: whether all attempted operations succeeded
        :rtype: bool
        """
        tasks = []
        for device in self.udisks:
            tasks.append(self.auto_add(device, recursive=recursive))
        results = yield AsyncList(tasks)
        success = all(results)
        yield Return(success)

    @Coroutine.from_generator_function
    def remove_all(self, detach=False, eject=False, lock=False):
        """
        Remove all filesystems handleable by udiskie.

        :param bool detach: detach the root drive
        :param bool eject: remove media from the root drive
        :param bool lock: lock the associated LUKS cleartext slave
        :returns: whether all attempted operations succeeded
        :rtype: bool
        """
        tasks = []
        remove_args = dict(force=True, detach=detach, eject=eject, lock=lock)
        for device in self.get_all_handleable():
            if device.parent_object_path != '/':
                continue
            tasks.append(self.auto_remove(device, **remove_args))
        results = yield AsyncList(tasks)
        success = all(results)
        yield Return(success)

    # iterate devices
    def is_handleable(self, device):
        # TODO: handle pathes in first argument
        """
        Check whether this device should be handled by udiskie.

        :param device: device object, block device path or mount path
        :returns: handleability
        :rtype: bool

        Currently this just means that the device is removable and holds a
        filesystem or the device is a LUKS encrypted volume.
        """
        return not self._ignore_device(device)

    def is_addable(self, device):
        """
        Check if device can be added with ``auto_add``.
        """
        if not self.is_handleable(device):
            return False
        if device.is_filesystem:
            return not device.is_mounted
        if device.is_crypto:
            return self._prompt and not device.is_unlocked
        if device.is_partition_table:
            return any(self.is_addable(dev)
                       for dev in self.get_all_handleable()
                       if dev.partition_slave == device)
        return False

    def is_removable(self, device):
        """
        Check if device can be removed with ``auto_remove``.
        """
        if not self.is_handleable(device):
            return False
        if device.is_filesystem:
            return device.is_mounted
        if device.is_crypto:
            return device.is_unlocked
        if device.is_partition_table or device.is_drive:
            return any(self.is_removable(dev)
                       for dev in self.get_all_handleable()
                       if _is_parent_of(device, dev))
        return False

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
        'forget_password': _('Clear password for {0}'),
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
            'forget_password': mounter.forget_password,
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
            cache = self._mounter._cache
            if cache and device in cache:
                yield 'forget_password'
        if device.is_ejectable and device.has_media:
            yield 'eject'
        if device.is_detachable:
            yield 'detach'

    def _device_node(self, device):
        """Create an empty menu node for the specified device."""
        label = device.ui_label
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


def prune_empty_node(node, seen):
    """
    Recursively remove empty branches and return whether this makes the node
    itself empty.

    The ``seen`` parameter is used to avoid infinite recursion due to cycles
    (you never know).
    """
    if node.methods:
        return False
    if id(node) in seen:
        return True
    seen = seen | {id(node)}
    for branch in list(node.branches):
        if prune_empty_node(branch, seen):
            node.branches.remove(branch)
        else:
            return False
    return True
