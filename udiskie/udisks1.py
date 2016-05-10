"""
UDisks wrapper utilities.

These act as a convenience abstraction layer on the UDisks DBus service.
Requires UDisks 1.0.5 as described here:

    http://udisks.freedesktop.org/docs/1.0.5/

This wraps the DBus API of Udisks2 providing a common interface with the
udisks2 module.

:class:`Daemon` caches all device states and listens to UDisks events to
guarantee the accessibilityy of device properties in between operations.
"""

from __future__ import absolute_import
from __future__ import unicode_literals

from collections import defaultdict
import logging
import os.path

from gi.repository import GLib

from .async_ import AsyncList, Coroutine, Return
from .common import Emitter, samefile, sameuuid, AttrDictView, wraps, NullDevice
from .compat import fix_str_conversions
from .dbus import connect_service, MethodsProxy
from .locale import _


__all__ = [
    'Daemon',
]


def filter_opt(opt):
    """Remove ``None`` values from a dictionary."""
    return [k for k, v in opt.items() if v]


@fix_str_conversions
class Device(object):

    """Helper base class for devices."""

    Interface = 'org.freedesktop.UDisks.Device'

    def __init__(self, daemon, object_path, property_proxy, method_proxy):
        """
        Initialize an instance with the given DBus proxy object.

        :param dbus.ObjectProxy object:
        """
        self._daemon = daemon
        self.object_path = object_path
        self._P = property_proxy
        self._M = method_proxy

    def __str__(self):
        """Display as object path."""
        return self.object_path

    def __eq__(self, other):
        """Comparison by object path."""
        return self.object_path == str(other)

    def __ne__(self, other):
        """Comparison by object path."""
        return not (self == other)

    def is_file(self, path):
        """Comparison by mount and device file path."""
        return (samefile(path, self.device_file) or
                samefile(path, self.loop_file) or
                any(samefile(path, mp) for mp in self.mount_paths) or
                sameuuid(path, self.id_uuid) or
                sameuuid(path, self.partition_uuid))

    # availability of interfaces
    @property
    def is_drive(self):
        """Check if the device is a drive."""
        return self._P.DeviceIsDrive

    @property
    def is_block(self):
        """Check if the device is a block device."""
        return True

    @property
    def is_partition_table(self):
        """Check if the device is a partition table."""
        return self._P.DeviceIsPartitionTable

    @property
    def is_partition(self):
        """Check if the device has a partition slave."""
        return self._P.DeviceIsPartition

    @property
    def is_filesystem(self):
        """Check if the device is a filesystem."""
        return self.id_usage == 'filesystem'

    @property
    def is_luks(self):
        """Check if the device is a LUKS container."""
        return self._P.DeviceIsLuks

    @property
    def is_loop(self):
        """Check if the device is a loop device."""
        return self._P.DeviceIsLinuxLoop

    # ----------------------------------------
    # Drive
    # ----------------------------------------

    # Drive properties
    is_toplevel = is_drive

    @property
    def is_detachable(self):
        """Check if the drive that owns this device can be detached."""
        if not self.is_drive:
            return None
        return self._P.DriveCanDetach

    @property
    def is_ejectable(self):
        """Check if the drive that owns this device can be ejected."""
        if not self.is_drive:
            return None
        return self._P.DriveIsMediaEjectable

    @property
    def has_media(self):
        """Check if there is media available in the drive."""
        return self._P.DeviceIsMediaAvailable

    # Drive methods
    def eject(self, unmount=False):
        """Eject media from the device."""
        return self._M.DriveEject(
            '(as)',
            filter_opt({'unmount': unmount}))

    def detach(self):
        """Detach the device by e.g. powering down the physical port."""
        return self._M.DriveDetach('(as)', [])

    # ----------------------------------------
    # Block
    # ----------------------------------------

    # Block properties
    @property
    def device_file(self):
        """The filesystem path of the device block file."""
        return os.path.normpath(self._P.DeviceFile)

    @property
    def device_presentation(self):
        """The device file path to present to the user."""
        return self._P.DeviceFilePresentation

    # TODO: device_size missing

    @property
    def id_usage(self):
        """Device usage class, for example 'filesystem' or 'crypto'."""
        return self._P.IdUsage

    @property
    def is_crypto(self):
        """Check if the device is a crypto device."""
        return self.id_usage == 'crypto'

    @property
    def is_ignored(self):
        """Check if the device should be ignored."""
        return self._P.DevicePresentationHide

    @property
    def device_id(self):
        """
        Return a unique and persistent identifier for the device.

        This is the basename (last path component) of the symlink in
        `/dev/disk/by-id/`.
        """
        for filename in self._P.DeviceFileById:
            parts = filename.split('/')
            if parts[-2] == 'by-id':
                return parts[-1]
        return ''

    @property
    def id_type(self):
        """"
        Return IdType property.

        This field provides further detail on IdUsage, for example:

        IdUsage     'filesystem'    'crypto'
        IdType      'ext4'          'crypto_LUKS'
        """
        return self._P.IdType

    @property
    def id_label(self):
        """Label of the device if available."""
        return self._P.IdLabel

    @property
    def id_uuid(self):
        """Device UUID."""
        return self._P.IdUuid

    @property
    def luks_cleartext_slave(self):
        """Get luks crypto device."""
        if not self.is_luks_cleartext:
            return None
        return self._daemon[self._P.LuksCleartextSlave]

    @property
    def is_luks_cleartext(self):
        """Check whether this is a luks cleartext device."""
        return self._P.DeviceIsLuksCleartext

    @property
    def is_external(self):
        """Check if the device is external."""
        return not self.is_systeminternal

    @property
    def is_systeminternal(self):
        """Check if the device is internal."""
        return self._P.DeviceIsSystemInternal

    @property
    def drive(self):
        """
        Get the drive containing this device.

        The returned Device object is not guaranteed to be a drive.
        """
        if self.is_partition:
            return self.partition_slave.drive
        elif self.is_luks_cleartext:
            return self.luks_cleartext_slave.drive
        else:
            return self

    root = drive

    @property
    def should_automount(self):
        """Check if the device should be automounted."""
        return self._P.DeviceAutomountHint != 'never'

    @property
    def icon_name(self):
        """Return the recommended device icon name."""
        return self._P.DevicePresentationIconName or 'drive-removable-media'

    symbolic_icon_name = icon_name

    @property
    def symlinks(self):
        """Known symlinks of the block device."""
        return list(filter(None, [
            self._P.DeviceFile,
            self._P.DeviceFilePresentation,
            self._P.DeviceFileById,
            self._P.DeviceFileByPath,
        ]))

    # ----------------------------------------
    # Partition
    # ----------------------------------------

    # Partition properties
    @property
    def partition_slave(self):
        """Get the partition slave (container)."""
        if not self.is_partition:
            return None
        return self._daemon[self._P.PartitionSlave]

    @property
    def partition_uuid(self):
        """Get the partition UUID."""
        return self._P.PartitionUuid

    # ----------------------------------------
    # Filesystem
    # ----------------------------------------

    # Filesystem properties
    @property
    def is_mounted(self):
        """Check if the device is mounted."""
        return self._P.DeviceIsMounted

    @property
    def mount_paths(self):
        """Return list of active mount paths."""
        if not self.is_mounted:
            return []
        raw_paths = self._P.DeviceMountPaths
        return [os.path.normpath(path) for path in raw_paths]

    # Filesystem methods
    def mount(self,
              fstype=None,
              options=None,
              auth_no_user_interaction=False):
        """Mount filesystem."""
        options = (options or []) + filter_opt({
            'auth_no_user_interaction': auth_no_user_interaction
        })
        return self._M.FilesystemMount(
            '(sas)',
            fstype or self.id_type,
            options)

    def unmount(self, force=False):
        """Unmount filesystem."""
        return self._M.FilesystemUnmount(
            '(as)',
            filter_opt({'force': force}))

    # ----------------------------------------
    # Encrypted
    # ----------------------------------------

    # Encrypted properties
    @property
    def luks_cleartext_holder(self):
        """Get unlocked luks cleartext device."""
        if not self.is_luks:
            return None
        return self._daemon[self._P.LuksHolder]

    @property
    def is_unlocked(self):
        """Check if device is already unlocked."""
        if not self.is_luks:
            return None
        return self.luks_cleartext_holder

    # Encrypted methods
    def unlock(self, password):
        """Unlock Luks device."""
        return self._M.LuksUnlock(
            '(sas)',
            password,
            [])

    def lock(self):
        """Lock Luks device."""
        return self._M.LuksLock('(as)', [])

    # ----------------------------------------
    # Loop
    # ----------------------------------------

    @property
    def loop_file(self):
        """Get the file backing the loop device."""
        return self._P.LinuxLoopFilename

    # ----------------------------------------
    # derived properties
    # ----------------------------------------

    @property
    def in_use(self):
        """Check whether this device is in use, i.e. mounted or unlocked."""
        if self.is_mounted or self.is_unlocked:
            return True
        if self.is_partition_table:
            for device in self._daemon:
                if device.partition_slave == self and device.in_use:
                    return True
        return False

    @property
    def parent_object_path(self):
        if self.is_partition:
            return self._P.PartitionSlave
        elif self.is_luks_cleartext:
            return self._P.LuksCleartextSlave
        else:
            return '/'

    @property
    def ui_label(self):
        return self.id_label or self.id_uuid or self.device_presentation


def _keep_async_event_order(func):
    """
    Decorator that ensures that event handlers for a device will be called
    in the order that the events have been generated.
    """
    @wraps(func)
    def wrapper(self, object_path, *args, **kwargs):
        self._event_queue[object_path].push(func, self, object_path, *args, **kwargs)
    return wrapper


class EventQueue(object):

    """
    Execute asynchronous event handlers in the order they are pushed. This is
    necessary because the :class:`Daemon` is stateful; it which assumes that
    event handlers are executed in the order they were generated by udisks.
    """

    def __init__(self):
        self._waiting = []
        self._execing = False

    def push(self, func, *args, **kwargs):
        """Schedule another event handler for execution."""
        self._waiting.append((func, args, kwargs))
        if not self._execing:
            self.pop()

    def pop(self, *_ignored):
        """Start executing the next event handler."""
        if not self._waiting:
            self._execing = False
            return
        self._execing = True
        func, args, kwargs = self._waiting.pop()
        coroutine = Coroutine(func(*args, **kwargs))
        coroutine.errbacks.append(self.pop)
        coroutine.callbacks.append(self.pop)


class Daemon(Emitter):

    """
    UDisks listener daemon.

    Listens to UDisks events. When a change occurs this class detects what
    has changed and triggers an appropriate event. Valid events are:

        - device_added    / device_removed
        - device_unlocked / device_locked
        - device_mounted  / device_unmounted
        - media_added     / media_removed
        - device_changed  / job_failed

    A very primitive mechanism that gets along without external
    dependencies is used for event dispatching. The methods `connect` and
    `disconnect` can be used to add or remove event handlers.
    """

    BusName = 'org.freedesktop.UDisks'
    Interface = 'org.freedesktop.UDisks'
    ObjectPath = '/org/freedesktop/UDisks'

    def __iter__(self):
        """Iterate over all devices."""
        return (self[object_path] for object_path in self.paths())

    def __getitem__(self, object_path):
        return self.get(object_path)

    def find(self, path):
        """
        Get a device proxy by device name or any mount path of the device.

        This searches through all accessible devices and compares device
        path as well as mount pathes.
        """
        if isinstance(path, Device):
            return path
        for device in self:
            if device.is_file(path):
                self._log.debug(_('found device owning "{0}": "{1}"',
                                  path, device))
                return device
        raise ValueError(_('no device found owning "{0}"', path))

    def __init__(self, proxy):
        """
        Create a Daemon object and start listening to DBus events.

        :param dbus.InterfaceProxy proxy: proxy to the dbus service object

        A default proxy will be created if set to ``None``.
        """
        event_names = ['device_added',
                       'device_removed',
                       'device_mounted',
                       'device_unmounted',
                       'media_added',
                       'media_removed',
                       'device_unlocked',
                       'device_locked',
                       'device_changed',
                       'job_failed']
        super(Daemon, self).__init__(event_names)

        self._proxy = proxy
        self._log = logging.getLogger(__name__)

        self._jobs = {}
        self._devices = {}
        self._property_proxy = {}
        self._errors = {'mount': {}, 'unmount': {},
                        'unlock': {}, 'lock': {},
                        'eject': {}, 'detach': {}}

        # DBus events
        self._event_queue = defaultdict(EventQueue)
        proxy.connect('DeviceAdded', self._device_changed)
        proxy.connect('DeviceRemoved', self._device_changed)
        proxy.connect('DeviceChanged', self._device_changed)
        proxy.connect('DeviceJobChanged', self._device_job_changed)

    @classmethod
    @Coroutine.from_generator_function
    def create(cls):
        proxy = yield connect_service(cls)
        udisks = cls(proxy)
        yield udisks._sync()
        yield Return(udisks)

    # Sniffer overrides
    def paths(self):
        """Iterate over all valid cached devices."""
        return (object_path
                for object_path, device in self._devices.items()
                if device)

    def get(self, object_path):
        """Return the current cached state of the device."""
        return self._devices.get(object_path)

    def trigger(self, event, device, *args):
        self._log.debug(_("+++ {0}: {1}", event, device))
        super(Daemon, self).trigger(event, device, *args)

    @Coroutine.from_generator_function
    def update(self, object_path):
        device = yield self._get_updated_device(object_path)
        if device is not None:
            self._devices[object_path] = device
        yield Return(device)

    @Coroutine.from_generator_function
    def _get_updated_device(self, object_path):
        obj = self._proxy.object.bus.get_object(object_path)
        try:
            prop_prox = self._property_proxy[object_path]
        except KeyError:
            prop_prox = yield obj.get_property_interface(Device.Interface)
            self._property_proxy[object_path] = prop_prox

        try:
            properties = yield prop_prox.GetAll()
        except GLib.GError:
            self._invalidate(object_path)
            yield Return(None)
            # TODO: return something useful? (NullDevice)
        else:
            itfc_prox = MethodsProxy(obj, Device.Interface)
            device = Device(self, object_path,
                            AttrDictView(properties), itfc_prox)
            yield Return(device)

    # special methods
    def set_error(self, device, action, message):
        if action in self._errors:
            self._errors[action][device.object_path] = message

    # events
    def _detect_toggle(self, property_name, old, new, add_name, del_name):
        old_valid = old and bool(getattr(old, property_name))
        new_valid = new and bool(getattr(new, property_name))
        # If we were notified about a started job we don't want to trigger
        # an event when the device is changed, but when the job is
        # completed. Otherwise we would show unmount notifications too
        # early (when it's not yet safe to remove the drive).
        # On the other hand, if the unmount operation is not issued via
        # UDisks1, there will be no corresponding job.
        cached_job = self._jobs.get(old.object_path)
        action_name = self._event_by_action.get(cached_job)
        if add_name and new_valid and not old_valid:
            if add_name != action_name:
                self.trigger(add_name, new)
        elif del_name and old_valid and not new_valid:
            if del_name != action_name:
                self.trigger(del_name, old)

    # UDisks event listeners
    @_keep_async_event_order
    def _device_changed(self, object_path):
        """Internal method."""
        old_state = self[object_path]
        new_state = yield self.update(object_path)
        if not old_state:
            if new_state:
                self.trigger('device_added', new_state)
            return
        new_state = new_state or NullDevice(object_path=object_path)
        self._detect_toggle('has_media', old_state, new_state,
                            'media_added', 'media_removed')
        self._detect_toggle('is_mounted', old_state, new_state,
                            'device_mounted', 'device_unmounted')
        self._detect_toggle('is_unlocked', old_state, new_state,
                            'device_unlocked', 'device_locked')
        self.trigger('device_changed', old_state, new_state)
        if not new_state:
            self._invalidate(object_path)
            self.trigger('device_removed', old_state)

    # NOTE: it seems the UDisks1 documentation for DeviceJobChanged is
    # fatally incorrect!
    @_keep_async_event_order
    def _device_job_changed(self,
                            object_path,
                            job_in_progress,
                            job_id,
                            job_initiated_by_user,
                            job_is_cancellable,
                            job_percentage):
        """
        Detect type of event and trigger appropriate event handlers.

        Internal method.
        """
        try:
            if job_id:
                action = self._action_by_operation[job_id]
            else:
                action = self._jobs[object_path]
        except KeyError:
            # this can happen
            # a) at startup, when we only see the completion of a job
            # b) when we get notified about a job, which we don't handle
            return
        # NOTE: The here used heuristic is prone to raise conditions.
        if job_in_progress:
            # Cache the action name for later use:
            self._jobs[object_path] = action
        else:
            del self._jobs[object_path]
            device = yield self._get_updated_device(object_path)
            if self._check_action_success[action](device):
                event = self._event_by_action[action]
                self.trigger(event, device)
            else:
                # get and delete message, if available:
                message = self._errors[action].pop(object_path, "")
                self.trigger('job_failed', device, action, message)
                self._log.info(_('{0} operation failed for device: {1}',
                                 action, object_path))

    # used internally by _device_job_changed:
    _action_by_operation = {
        'FilesystemMount': 'mount',
        'FilesystemUnmount': 'unmount',
        'LuksUnlock': 'unlock',
        'LuksLock': 'lock',
        'DriveDetach': 'detach',
        'DriveEject': 'eject',
    }

    _event_by_action = {
        'mount': 'device_mounted',
        'unmount': 'device_unmounted',
        'unlock': 'device_unlocked',
        'lock': 'device_locked',
        'eject': 'media_removed',
        'detach': 'device_removed',
    }

    _check_action_success = {
        'mount': lambda dev: dev.is_mounted,
        'unmount': lambda dev: not dev or not dev.is_mounted,
        'unlock': lambda dev: dev.is_unlocked,
        'lock': lambda dev: not dev or not dev.is_unlocked,
        'detach': lambda dev: not dev,
        'eject': lambda dev: not dev or not dev.has_media,
    }

    # internal state keeping
    @Coroutine.from_generator_function
    def _sync(self):
        """Cache all device states."""
        object_pathes = yield self._proxy.call('EnumerateDevices', '()')
        yield AsyncList(map(self.update, object_pathes))
        yield Return()

    def _invalidate(self, object_path):
        """Flag the device invalid. This removes it from the iteration."""
        if object_path in self._devices:
            del self._devices[object_path]
            del self._property_proxy[object_path]
