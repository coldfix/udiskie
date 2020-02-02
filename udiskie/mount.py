"""
Mount utilities.
"""

from distutils.spawn import find_executable
from collections import namedtuple
from functools import partial
import logging
import os

from .async_ import to_coro, gather, sleep
from .common import wraps, setdefault, exc_message, format_exc
from .config import IgnoreDevice, match_config
from .locale import _


__all__ = ['Mounter']


# TODO: add / remove / XXX_all should make proper use of the asynchronous
# execution.

def _error_boundary(fn):
    @wraps(fn)
    async def wrapper(self, device, *args, **kwargs):
        try:
            return await fn(self, device, *args, **kwargs)
        except Exception as e:
            self._log.error(_('failed to {0} {1}: {2}',
                              fn.__name__, device, exc_message(e)))
            self._log.debug(format_exc())
            return False
    return wrapper


def _is_parent_of(parent, child):
    """Check whether the first device is the parent of the second device."""
    if child.is_partition:
        return child.partition_slave == parent
    if child.is_toplevel:
        return child.drive == parent and child != parent
    return False


class Mounter:

    """
    Mount utility.

    Stores environment variables (filter, prompt, browser, udisks) to use
    across multiple mount operations.

    :ivar udisks: adapter to the udisks service

    NOTE: The optional parameters are not guaranteed to keep their order and
    should always be passed as keyword arguments.
    """

    def __init__(self, udisks, config=None, prompt=None, browser=None,
                 terminal=None, cache=None, cache_hint=False):
        """
        Initialize mounter with the given defaults.

        :param udisks: udisks service object. May be a Sniffer or a Daemon.
        :param list config: list of :class:`DeviceFilter`
        :param callable prompt: retrieve passwords for devices
        :param callable browser: open devices
        :param callable terminal: open devices in terminal

        If prompt is None, device unlocking will not work.
        If browser is None, browse will not work.
        """
        self.udisks = udisks
        self._config = (config or []) + [
            IgnoreDevice({'symlinks': '/dev/mapper/docker-*', 'ignore': True}),
            IgnoreDevice({'symlinks': '/dev/disk/by-id/dm-name-docker-*',
                          'ignore': True}),
            IgnoreDevice({'is_loop': True, 'is_ignored': False,
                          'loop_file': '/*', 'ignore': False}),
            IgnoreDevice({'is_block': False, 'ignore': True}),
            IgnoreDevice({'is_external': False,
                          'is_toplevel': True, 'ignore': True}),
            IgnoreDevice({'is_ignored': True, 'ignore': True})]
        self._prompt = prompt
        self._browser = browser
        self._terminal = terminal
        self._cache = cache
        self._cache_hint = cache_hint
        self._log = logging.getLogger(__name__)

    def _find_device(self, device_or_path):
        """Find device object from path."""
        return self.udisks.find(device_or_path)

    async def _find_device_losetup(self, device_or_path):
        try:
            device = self.udisks.find(device_or_path)
            return device, False
        except FileNotFoundError:
            if not os.path.isfile(device_or_path):
                raise
        device = await self.losetup(device_or_path)
        return device, True

    @_error_boundary
    async def browse(self, device):
        """
        Launch file manager on the mount path of the specified device.

        :param device: device object, block device path or mount path
        :returns: whether the program was successfully launched.
        """
        device = self._find_device(device)
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

    @_error_boundary
    async def terminal(self, device):
        """
        Launch terminal on the mount path of the specified device.

        :param device: device object, block device path or mount path
        :returns: whether the program was successfully launched.
        """
        device = self._find_device(device)
        if not device.is_mounted:
            self._log.error(_("not opening terminal {0}: not mounted", device))
            return False
        if not self._terminal:
            self._log.error(_("not opening terminal {0}: no program", device))
            return False
        self._log.debug(_('opening {0} on {0.mount_paths[0]}', device))
        self._terminal(device.mount_paths[0])
        self._log.info(_('opened {0} on {0.mount_paths[0]}', device))
        return True

    # mount/unmount
    @_error_boundary
    async def mount(self, device):
        """
        Mount the device if not already mounted.

        :param device: device object, block device path or mount path
        :returns: whether the device is mounted.
        """
        device = self._find_device(device)
        if not self.is_handleable(device) or not device.is_filesystem:
            self._log.warn(_('not mounting {0}: unhandled device', device))
            return False
        if device.is_mounted:
            self._log.info(_('not mounting {0}: already mounted', device))
            return True
        options = match_config(self._config, device, 'options', None)
        kwargs = dict(options=options)
        self._log.debug(_('mounting {0} with {1}', device, kwargs))
        self._check_device_before_mount(device)
        mount_path = await device.mount(**kwargs)
        self._log.info(_('mounted {0} on {1}', device, mount_path))
        return True

    def _check_device_before_mount(self, device):
        if device.id_type == 'ntfs' and not find_executable('ntfs-3g'):
            self._log.warn(_(
                "Mounting NTFS device with default driver.\n"
                "Please install 'ntfs-3g' if you experience problems or the "
                "device is readonly."))

    @_error_boundary
    async def unmount(self, device):
        """
        Unmount a Device if mounted.

        :param device: device object, block device path or mount path
        :returns: whether the device is unmounted
        """
        device = self._find_device(device)
        if not self.is_handleable(device) or not device.is_filesystem:
            self._log.warn(_('not unmounting {0}: unhandled device', device))
            return False
        if not device.is_mounted:
            self._log.info(_('not unmounting {0}: not mounted', device))
            return True
        self._log.debug(_('unmounting {0}', device))
        await device.unmount()
        self._log.info(_('unmounted {0}', device))
        return True

    # unlock/lock (LUKS)
    @_error_boundary
    async def unlock(self, device):
        """
        Unlock the device if not already unlocked.

        :param device: device object, block device path or mount path
        :returns: whether the device is unlocked
        """
        device = self._find_device(device)
        if not self.is_handleable(device) or not device.is_crypto:
            self._log.warn(_('not unlocking {0}: unhandled device', device))
            return False
        if device.is_unlocked:
            self._log.info(_('not unlocking {0}: already unlocked', device))
            return True
        if not self._prompt:
            self._log.error(_('not unlocking {0}: no password prompt', device))
            return False
        unlocked = await self._unlock_from_cache(device)
        if unlocked:
            return True
        unlocked = await self._unlock_from_keyfile(device)
        if unlocked:
            return True
        options = dict(allow_keyfile=self.udisks.keyfile_support,
                       allow_cache=self._cache is not None,
                       cache_hint=self._cache_hint)
        password = await self._prompt(device, options)
        # password is either None or udiskie.prompt.PasswordResult:
        if password is None:
            self._log.debug(_('not unlocking {0}: cancelled by user', device))
            return False
        cache_hint = password.cache_hint
        password = password.password
        if isinstance(password, bytes):
            self._log.debug(_('unlocking {0} using keyfile', device))
            await device.unlock_keyfile(password)
        else:
            self._log.debug(_('unlocking {0}', device))
            await device.unlock(password)
        self._update_cache(device, password, cache_hint)
        self._log.info(_('unlocked {0}', device))
        return True

    async def _unlock_from_cache(self, device):
        if not self._cache:
            return False
        try:
            password = self._cache[device]
        except KeyError:
            self._log.debug(_("no cached key for {0}", device))
            return False
        self._log.debug(_('unlocking {0} using cached password', device))
        try:
            await device.unlock_keyfile(password)
        except Exception:
            self._log.debug(_('failed to unlock {0} using cached password', device))
            self._log.debug(format_exc())
            return False
        self._log.info(_('unlocked {0} using cached password', device))
        return True

    async def _unlock_from_keyfile(self, device):
        if not self.udisks.keyfile_support:
            return False
        filename = match_config(self._config, device, 'keyfile', None)
        if filename is None:
            self._log.debug(_('No matching keyfile rule for {}.', device))
            return False
        try:
            with open(filename, 'rb') as f:
                keyfile = f.read()
        except IOError:
            self._log.warn(_('keyfile for {0} not found: {1}', device, filename))
            return False
        self._log.debug(_('unlocking {0} using keyfile {1}', device, filename))
        try:
            await device.unlock_keyfile(keyfile)
        except Exception:
            self._log.debug(_('failed to unlock {0} using keyfile', device))
            self._log.debug(format_exc())
            return False
        self._log.info(_('unlocked {0} using keyfile', device))
        return True

    def _update_cache(self, device, password, cache_hint):
        if not self._cache:
            return
        # TODO: could allow numeric cache_hint (=timeout)…
        if cache_hint or cache_hint is None:
            self._cache[device] = password

    def forget_password(self, device):
        try:
            del self._cache[device]
        except KeyError:
            pass

    @_error_boundary
    async def lock(self, device):
        """
        Lock device if unlocked.

        :param device: device object, block device path or mount path
        :returns: whether the device is locked
        """
        device = self._find_device(device)
        if not self.is_handleable(device) or not device.is_crypto:
            self._log.warn(_('not locking {0}: unhandled device', device))
            return False
        if not device.is_unlocked:
            self._log.info(_('not locking {0}: not unlocked', device))
            return True
        self._log.debug(_('locking {0}', device))
        await device.lock()
        self._log.info(_('locked {0}', device))
        return True

    # add/remove (unlock/lock or mount/unmount)
    @_error_boundary
    async def add(self, device, recursive=None):
        """
        Mount or unlock the device depending on its type.

        :param device: device object, block device path or mount path
        :param bool recursive: recursively mount and unlock child devices
        :returns: whether all attempted operations succeeded
        """
        device, created = await self._find_device_losetup(device)
        if created and recursive is False:
            return device
        if device.is_filesystem:
            success = await self.mount(device)
        elif device.is_crypto:
            success = await self.unlock(device)
            if success and recursive:
                await self.udisks._sync()
                device = self.udisks[device.object_path]
                success = await self.add(
                    device.luks_cleartext_holder,
                    recursive=True)
        elif (recursive
              and device.is_partition_table
              and self.is_handleable(device)):
            tasks = [
                self.add(dev, recursive=True)
                for dev in self.get_all_handleable()
                if dev.is_partition and dev.partition_slave == device
            ]
            results = await gather(*tasks)
            success = all(results)
        else:
            self._log.info(_('not adding {0}: unhandled device', device))
            return False
        return success

    @_error_boundary
    async def auto_add(self, device, recursive=None, automount=True):
        """
        Automatically attempt to mount or unlock a device, but be quiet if the
        device is not supported.

        :param device: device object, block device path or mount path
        :param bool recursive: recursively mount and unlock child devices
        :returns: whether all attempted operations succeeded
        """
        device, created = await self._find_device_losetup(device)
        if created and recursive is False:
            return device
        if device.is_luks_cleartext and self.udisks.version_info >= (2, 7, 0):
            await sleep(1.5)    # temporary workaround for #153, unreliable
        success = True
        if not self.is_automount(device, automount):
            pass
        elif device.is_filesystem:
            if not device.is_mounted:
                success = await self.mount(device)
        elif device.is_crypto:
            if self._prompt and not device.is_unlocked:
                success = await self.unlock(device)
            if success and recursive:
                await self.udisks._sync()
                device = self.udisks[device.object_path]
                success = await self.auto_add(
                    device.luks_cleartext_holder,
                    recursive=True)
        elif recursive and device.is_partition_table:
            tasks = [
                self.auto_add(dev, recursive=True)
                for dev in self.get_all_handleable()
                if dev.is_partition and dev.partition_slave == device
            ]
            results = await gather(*tasks)
            success = all(results)
        else:
            self._log.debug(_('not adding {0}: unhandled device', device))
        return success

    @_error_boundary
    async def remove(self, device, force=False, detach=False, eject=False,
                     lock=False):
        """
        Unmount or lock the device depending on device type.

        :param device: device object, block device path or mount path
        :param bool force: recursively remove all child devices
        :param bool detach: detach the root drive
        :param bool eject: remove media from the root drive
        :param bool lock: lock the associated LUKS cleartext slave
        :returns: whether all attempted operations succeeded
        """
        device = self._find_device(device)
        if device.is_filesystem:
            if device.is_mounted or not device.is_loop or detach is False:
                success = await self.unmount(device)
        elif device.is_crypto:
            if force and device.is_unlocked:
                await self.auto_remove(device.luks_cleartext_holder, force=True)
            success = await self.lock(device)
        elif (force
              and (device.is_partition_table or device.is_drive)
              and self.is_handleable(device)):
            kw = dict(force=True, detach=detach, eject=eject, lock=lock)
            tasks = [
                self.auto_remove(child, **kw)
                for child in self.get_all_handleable()
                if _is_parent_of(device, child)
            ]
            results = await gather(*tasks)
            success = all(results)
        else:
            self._log.info(_('not removing {0}: unhandled device', device))
            success = False
        # if these operations work, everything is fine, we can return True:
        if lock and device.is_luks_cleartext:
            device = device.luks_cleartext_slave
            if self.is_handleable(device):
                success = await self.lock(device)
        if eject:
            success = await self.eject(device)
        if (detach or detach is None) and device.is_loop:
            success = await self.delete(device, remove=False)
        elif detach:
            success = await self.detach(device)
        return success

    @_error_boundary
    async def auto_remove(self, device, force=False, detach=False, eject=False,
                          lock=False):
        """
        Unmount or lock the device depending on device type.

        :param device: device object, block device path or mount path
        :param bool force: recursively remove all child devices
        :param bool detach: detach the root drive
        :param bool eject: remove media from the root drive
        :param bool lock: lock the associated LUKS cleartext slave
        :returns: whether all attempted operations succeeded
        """
        device = self._find_device(device)
        success = True
        if not self.is_handleable(device):
            pass
        elif device.is_filesystem:
            if device.is_mounted:
                success = await self.unmount(device)
        elif device.is_crypto:
            if force and device.is_unlocked:
                await self.auto_remove(device.luks_cleartext_holder, force=True)
            if device.is_unlocked:
                success = await self.lock(device)
        elif force and (device.is_partition_table or device.is_drive):
            kw = dict(force=True, detach=detach, eject=eject, lock=lock)
            tasks = [
                self.auto_remove(child, **kw)
                for child in self.get_all_handleable()
                if _is_parent_of(device, child)
            ]
            results = await gather(*tasks)
            success = all(results)
        else:
            self._log.debug(_('not removing {0}: unhandled device', device))
        # if these operations work, everything is fine, we can return True:
        if lock and device.is_luks_cleartext:
            device = device.luks_cleartext_slave
            success = await self.lock(device)
        if eject and device.has_media:
            success = await self.eject(device)
        if (detach or detach is None) and device.is_loop:
            success = await self.delete(device, remove=False)
        elif detach and device.is_detachable:
            success = await self.detach(device)
        return success

    # eject/detach device
    @_error_boundary
    async def eject(self, device, force=False):
        """
        Eject a device after unmounting all its mounted filesystems.

        :param device: device object, block device path or mount path
        :param bool force: remove child devices before trying to eject
        :returns: whether the operation succeeded
        """
        device = self._find_device(device)
        if not self.is_handleable(device):
            self._log.warn(_('not ejecting {0}: unhandled device'))
            return False
        drive = device.drive
        if not (drive.is_drive and drive.is_ejectable):
            self._log.warn(_('not ejecting {0}: drive not ejectable', drive))
            return False
        if force:
            # Can't autoremove 'device.drive', because that will be filtered
            # due to block=False:
            await self.auto_remove(device.root, force=True)
        self._log.debug(_('ejecting {0}', device))
        await drive.eject()
        self._log.info(_('ejected {0}', device))
        return True

    @_error_boundary
    async def detach(self, device, force=False):
        """
        Detach a device after unmounting all its mounted filesystems.

        :param device: device object, block device path or mount path
        :param bool force: remove child devices before trying to detach
        :returns: whether the operation succeeded
        """
        device = self._find_device(device)
        if not self.is_handleable(device):
            self._log.warn(_('not detaching {0}: unhandled device', device))
            return False
        drive = device.root
        if not drive.is_detachable and not drive.is_loop:
            self._log.warn(_('not detaching {0}: drive not detachable', drive))
            return False
        if force:
            await self.auto_remove(drive, force=True)
        self._log.debug(_('detaching {0}', device))
        if drive.is_detachable:
            await drive.detach()
        else:
            await drive.delete()
        self._log.info(_('detached {0}', device))
        return True

    # mount_all/unmount_all
    async def add_all(self, recursive=False):
        """
        Add all handleable devices that available at start.

        :param bool recursive: recursively mount and unlock child devices
        :returns: whether all attempted operations succeeded
        """
        tasks = [self.auto_add(device, recursive=recursive)
                 for device in self.get_all_handleable_leaves()]
        results = await gather(*tasks)
        success = all(results)
        return success

    async def remove_all(self, detach=False, eject=False, lock=False):
        """
        Remove all filesystems handleable by udiskie.

        :param bool detach: detach the root drive
        :param bool eject: remove media from the root drive
        :param bool lock: lock the associated LUKS cleartext slave
        :returns: whether all attempted operations succeeded
        """
        kw = dict(force=True, detach=detach, eject=eject, lock=lock)
        tasks = [self.auto_remove(device, **kw)
                 for device in self.get_all_handleable_roots()]
        results = await gather(*tasks)
        success = all(results)
        return success

    # loop devices
    async def losetup(self, image, read_only=True, offset=None, size=None,
                      no_part_scan=None):
        """
        Setup a loop device.

        :param str image: path of the image file
        :param bool read_only:
        :param int offset:
        :param int size:
        :param bool no_part_scan:
        :returns: the device object for the loop device
        """
        try:
            device = self.udisks.find(image)
        except FileNotFoundError:
            pass
        else:
            self._log.info(_('not setting up {0}: already up', device))
            return device
        if not os.path.isfile(image):
            self._log.error(_('not setting up {0}: not a file', image))
            return None
        self._log.debug(_('setting up {0}', image))
        fd = os.open(image, os.O_RDONLY)
        device = await self.udisks.loop_setup(fd, {
            'offset': offset,
            'size': size,
            'read-only': read_only,
            'no-part-scan': no_part_scan,
        })
        self._log.info(_('set up {0} as {1}', image,
                         device.device_presentation))
        return device

    @_error_boundary
    async def delete(self, device, remove=True):
        """
        Detach the loop device.

        :param device: device object, block device path or mount path
        :param bool remove: whether to unmount the partition etc.
        :returns: whether the loop device is deleted
        """
        device = self._find_device(device)
        if not self.is_handleable(device) or not device.is_loop:
            self._log.warn(_('not deleting {0}: unhandled device', device))
            return False
        if remove:
            await self.auto_remove(device, force=True)
        self._log.debug(_('deleting {0}', device))
        await device.delete()
        self._log.info(_('deleted {0}', device))
        return True

    # iterate devices
    def is_handleable(self, device):
        # TODO: handle paths in first argument
        """
        Check whether this device should be handled by udiskie.

        :param device: device object, block device path or mount path
        :returns: handleability

        Currently this just means that the device is removable and holds a
        filesystem or the device is a LUKS encrypted volume.
        """
        return not self._ignore_device(device)

    def is_automount(self, device, default=True):
        if not self.is_handleable(device):
            return False
        return match_config(self._config, device, 'automount', default)

    def _ignore_device(self, device):
        return match_config(self._config, device, 'ignore', False)

    def is_addable(self, device, automount=True):
        """Check if device can be added with ``auto_add``."""
        if not self.is_automount(device, automount):
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
        """Check if device can be removed with ``auto_remove``."""
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
        """Get list of all known handleable devices."""
        nodes = self.get_device_tree()
        return [node.device
                for node in sorted(nodes.values(), key=DevNode._sort_key)
                if not node.ignored and node.device]

    def get_all_handleable_roots(self):
        """
        Get list of all handleable devices, return only those that represent
        root nodes within the filtered device tree.
        """
        nodes = self.get_device_tree()
        return [node.device
                for node in sorted(nodes.values(), key=DevNode._sort_key)
                if not node.ignored and node.device
                and (node.root == '/' or nodes[node.root].ignored)]

    def get_all_handleable_leaves(self):
        """
        Get list of all handleable devices, return only those that represent
        leaf nodes within the filtered device tree.
        """
        nodes = self.get_device_tree()
        return [node.device
                for node in sorted(nodes.values(), key=DevNode._sort_key)
                if not node.ignored and node.device
                and all(child.ignored for child in node.children)]

    def get_device_tree(self):
        """Get a tree of all devices."""
        root = DevNode(None, None, [], None)
        device_nodes = {
            dev.object_path: DevNode(dev, dev.parent_object_path, [],
                                     self._ignore_device(dev))
            for dev in self.udisks
        }
        for node in device_nodes.values():
            device_nodes.get(node.root, root).children.append(node)
        device_nodes['/'] = root
        for node in device_nodes.values():
            node.children.sort(key=DevNode._sort_key)

        # use parent as fallback, update top->down:
        def propagate_ignored(node):
            for child in node.children:
                if child.ignored is None:
                    child.ignored = node.ignored
                propagate_ignored(child)
        propagate_ignored(root)
        return device_nodes


class DevNode:

    def __init__(self, device, root, children, ignored):
        self.device = device
        self.root = root
        self.children = children
        self.ignored = ignored

    def _sort_key(self):
        return self.device.device_presentation if self.device else ''


# data structs containing the menu hierarchy:
Device = namedtuple('Device', ['root', 'branches', 'device', 'label', 'methods'])
Action = namedtuple('Action', ['method', 'device', 'label', 'action'])


class DeviceActions:

    _labels = {
        'browse': _('Browse {0}'),
        'terminal': _('Hack on {0}'),
        'mount': _('Mount {0}'),
        'unmount': _('Unmount {0}'),
        'unlock': _('Unlock {0}'),
        'lock': _('Lock {0}'),
        'eject': _('Eject {1}'),
        'detach': _('Unpower {1}'),
        'forget_password': _('Clear password for {0}'),
        'delete': _('Detach {0}'),
    }

    def __init__(self, mounter, actions={}):
        self._mounter = mounter
        self._actions = _actions = actions.copy()
        setdefault(_actions, {
            'browse': mounter.browse,
            'terminal': mounter.terminal,
            'mount': mounter.mount,
            'unmount': mounter.unmount,
            'unlock': mounter.unlock,
            'lock': partial(mounter.remove, force=True),
            'eject': partial(mounter.eject, force=True),
            'detach': partial(mounter.detach, force=True),
            'forget_password': to_coro(mounter.forget_password),
            'delete': mounter.delete,
        })

    def detect(self, root_device='/'):
        """
        Detect all currently known devices.

        :param str root_device: object path of root device to return
        :returns: root node of device hierarchy
        """
        root = Device(None, [], None, "", [])
        device_nodes = dict(map(self._device_node,
                                self._mounter.get_all_handleable()))
        # insert child devices as branches into their roots:
        for node in device_nodes.values():
            device_nodes.get(node.root, root).branches.append(node)
        device_nodes['/'] = root
        for node in device_nodes.values():
            node.branches.sort(key=lambda node: node.label)
        return device_nodes[root_device]

    def _get_device_methods(self, device):
        """Return an iterable over all available methods the device has."""
        if device.is_filesystem:
            if device.is_mounted:
                if self._mounter._browser:
                    yield 'browse'
                if self._mounter._terminal:
                    yield 'terminal'
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
        if device.is_loop:
            yield 'delete'

    def _device_node(self, device):
        """Create an empty menu node for the specified device."""
        label = device.ui_label
        dev_label = device.ui_device_label
        # determine available methods
        methods = [Action(method, device,
                          self._labels[method].format(label, dev_label),
                          partial(self._actions[method], device))
                   for method in self._get_device_methods(device)]
        # find the root device:
        root = device.parent_object_path
        # in this first step leave branches empty
        return device.object_path, Device(root, [], device, dev_label, methods)


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
