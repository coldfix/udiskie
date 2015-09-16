"""
UDisks wrapper utilities.

These act as a convenience abstraction layer on the UDisks DBus service.
Requires UDisks 1.0.5 as described here:

    http://udisks.freedesktop.org/docs/1.0.5/

This wraps the DBus API of Udisks2 providing a common interface with the
udisks2 module.

Overview: This module exports the classes ``Sniffer`` and ``Daemon``.

:class:`Sniffer` can be used as an online exporter of the current device
states queried from the UDisks DBus service as requested.

:class:`Daemon` caches all device states and listens to UDisks events to
guarantee the accessibilityy of device properties in between operations.
"""

from copy import copy
from inspect import getmembers
import logging
import os.path

from udiskie.common import Emitter, samefile
from udiskie.compat import filter
from udiskie.dbus import DBusService, DBusException
from udiskie.locale import _


__all__ = ['Sniffer', 'Daemon']


def filter_opt(opt):
    """Remove ``None`` values from a dictionary."""
    return [k for k, v in opt.items() if v]


class DeviceBase(object):

    """Helper base class for devices."""

    Interface = 'org.freedesktop.UDisks.Device'

    Exception = DBusException

    # string representation
    def __str__(self):
        """Display as object path."""
        return self.object_path

    def __eq__(self, other):
        """Comparison by object path."""
        return self.object_path == str(other)

    def __ne__(self, other):
        """Comparison by object path."""
        return not (self == other)

    def __nonzero__(self):      # python2
        """Check device validity."""
        return self.is_valid
    __bool__ = __nonzero__      # python3

    def is_file(self, path):
        """Comparison by mount and device file path."""
        return samefile(path, self.device_file) or any(
            samefile(path, mp) for mp in self.mount_paths)


class OnlineDevice(DeviceBase):

    """
    Online wrapper for org.freedesktop.UDisks.Device DBus API proxy objects.

    Resolves both property access and method calls dynamically to the DBus
    object.

    This is the main class used to retrieve (and then possibly cache) device
    properties from the DBus backend.
    """

    # construction
    def __init__(self, udisks, object):
        """
        Initialize an instance with the given DBus proxy object.

        :param DBusObject object:
        """
        self._proxy = object.get_interface(self.Interface)
        self.object_path = object.object_path
        self.udisks = udisks

    # availability of interfaces
    @property
    def is_valid(self):
        """Check if there is a valid DBus object for this object path."""
        try:
            self._proxy.property.DeviceFile
            return True
        except self.Exception:
            return False

    @property
    def is_drive(self):
        """Check if the device is a drive."""
        return self._proxy.property.DeviceIsDrive

    @property
    def is_block(self):
        """Check if the device is a block device."""
        return True

    @property
    def is_partition_table(self):
        """Check if the device is a partition table."""
        return self._proxy.property.DeviceIsPartitionTable

    @property
    def is_partition(self):
        """Check if the device has a partition slave."""
        return self._proxy.property.DeviceIsPartition

    @property
    def is_filesystem(self):
        """Check if the device is a filesystem."""
        return self.id_usage == 'filesystem'

    @property
    def is_luks(self):
        """Check if the device is a LUKS container."""
        return self._proxy.property.DeviceIsLuks

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
        return self._proxy.property.DriveCanDetach

    @property
    def is_ejectable(self):
        """Check if the drive that owns this device can be ejected."""
        if not self.is_drive:
            return None
        return self._proxy.property.DriveIsMediaEjectable

    @property
    def has_media(self):
        """Check if there is media available in the drive."""
        return self._proxy.property.DeviceIsMediaAvailable

    # Drive methods
    def eject(self, unmount=False):
        """Eject media from the device."""
        return self._proxy.method.DriveEject(
            '(as)',
            filter_opt({'unmount': unmount}))

    def detach(self):
        """Detach the device by e.g. powering down the physical port."""
        return self._proxy.method.DriveDetach('(as)', [])

    # ----------------------------------------
    # Block
    # ----------------------------------------

    # Block properties
    @property
    def device_file(self):
        """The filesystem path of the device block file."""
        return os.path.normpath(self._proxy.property.DeviceFile)

    @property
    def device_presentation(self):
        """The device file path to present to the user."""
        return self._proxy.property.DeviceFilePresentation

    # TODO: device_size missing

    @property
    def id_usage(self):
        """Device usage class, for example 'filesystem' or 'crypto'."""
        return self._proxy.property.IdUsage

    @property
    def is_crypto(self):
        """Check if the device is a crypto device."""
        return self.id_usage == 'crypto'

    @property
    def is_ignored(self):
        """Check if the device should be ignored."""
        return self._proxy.property.DevicePresentationHide

    @property
    def device_id(self):
        """
        Return a unique and persistent identifier for the device.

        This is the basename (last path component) of the symlink in
        `/dev/disk/by-id/`.
        """
        for filename in self._proxy.property.DeviceFileById:
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
        return self._proxy.property.IdType

    @property
    def id_label(self):
        """Label of the device if available."""
        return self._proxy.property.IdLabel

    @property
    def id_uuid(self):
        """Device UUID."""
        return self._proxy.property.IdUuid

    @property
    def luks_cleartext_slave(self):
        """Get luks crypto device."""
        if not self.is_luks_cleartext:
            return None
        return self.udisks[self._proxy.property.LuksCleartextSlave]

    @property
    def is_luks_cleartext(self):
        """Check whether this is a luks cleartext device."""
        return self._proxy.property.DeviceIsLuksCleartext

    @property
    def is_external(self):
        """Check if the device is external."""
        return not self.is_systeminternal

    @property
    def is_systeminternal(self):
        """Check if the device is internal."""
        return self._proxy.property.DeviceIsSystemInternal

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
        return self._proxy.property.DeviceAutomountHint != 'never'

    @property
    def icon_name(self):
        """Return the recommended device icon name."""
        return self._proxy.property.DevicePresentationIconName or 'drive-removable-media'

    symbolic_icon_name = icon_name

    # ----------------------------------------
    # Partition
    # ----------------------------------------

    # Partition properties
    @property
    def partition_slave(self):
        """Get the partition slave (container)."""
        if not self.is_partition:
            return None
        return self.udisks[self._proxy.property.PartitionSlave]

    # ----------------------------------------
    # Filesystem
    # ----------------------------------------

    # Filesystem properties
    @property
    def is_mounted(self):
        """Check if the device is mounted."""
        return self._proxy.property.DeviceIsMounted

    @property
    def mount_paths(self):
        """Return list of active mount paths."""
        if not self.is_mounted:
            return []
        raw_paths = self._proxy.property.DeviceMountPaths
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
        return self._proxy.method.FilesystemMount(
            '(sas)',
            fstype or self.id_type,
            options)

    def unmount(self, force=False):
        """Unmount filesystem."""
        return self._proxy.method.FilesystemUnmount(
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
        return self.udisks[self._proxy.property.LuksHolder]

    @property
    def is_unlocked(self):
        """Check if device is already unlocked."""
        if not self.is_luks:
            return None
        return self.luks_cleartext_holder

    # Encrypted methods
    def unlock(self, password):
        """Unlock Luks device."""
        return self.udisks.update(
            self._proxy.method.LuksUnlock(
                '(sas)',
                password,
                []))

    def lock(self):
        """Lock Luks device."""
        return self._proxy.method.LuksLock('(as)', [])

    # ----------------------------------------
    # derived properties
    # ----------------------------------------

    @property
    def in_use(self):
        """Check whether this device is in use, i.e. mounted or unlocked."""
        if self.is_mounted or self.is_unlocked:
            return True
        if self.is_partition_table:
            for device in self.udisks:
                if device.partition_slave == self and device.in_use:
                    return True
        return False


def _CachedDeviceProperty(method):
    """Cache object path and return the current known CachedDevice state."""
    key = '_' + method.__name__
    def get(self):
        return self._daemon[getattr(self, key, None)]
    def set(self, device):
        setattr(self, key, getattr(device, 'object_path', None))
    return property(get, set, doc=method.__doc__)


class CachedDevice(DeviceBase):

    """
    Cached device state.

    Properties are cached at creation time. Methods will be invoked
    dynamically via the associated DBus object.
    """

    def __init__(self, device):
        """Cache all properties of the online device."""
        self._device = device
        self._daemon = device.udisks
        def isproperty(obj):
            return isinstance(obj, property)
        for key, val in getmembers(device.__class__, isproperty):
            try:
                setattr(self, key, getattr(device, key))
            except device.Exception:
                setattr(self, key, None)
        self.is_valid = device.is_valid

    def __getattr__(self, key):
        """Resolve unknown properties and methods via the online device."""
        if key.startswith('_'):
            raise AttributeError(key)
        return getattr(self._device, key)

    # Overload properties that return Device objects to return CachedDevice
    # instances instead. NOTE: the setters are implemented such that the
    # returned devices will be cached at the time the property is accessed
    # rather than at the time the current object was instanciated.
    # FIXME: should it be different?

    @_CachedDeviceProperty
    def luks_cleartext_slave(self):
        """Get luks crypto device."""
        pass

    @_CachedDeviceProperty
    def drive(self):
        """Get the drive."""
        pass

    @_CachedDeviceProperty
    def partition_slave(self):
        """Get the partition slave (container)."""
        pass

    @_CachedDeviceProperty
    def luks_cleartext_holder(self):
        """Get unlocked luks cleartext device."""
        pass

    def unlock(self, password, options=[]):
        """Unlock Luks device."""
        return CachedDevice(self._device.unlock(password))


class UDisks(DBusService):

    """
    Base class for UDisks service wrappers.
    """

    BusName = 'org.freedesktop.UDisks'
    Interface = 'org.freedesktop.UDisks'
    ObjectPath = '/org/freedesktop/UDisks'

    def __iter__(self):
        """Iterate over all devices."""
        return filter(None, map(self.get, self.paths()))

    def __getitem__(self, object_path):
        return self.get(object_path)

    def find(self, path):
        """
        Get a device proxy by device name or any mount path of the device.

        This searches through all accessible devices and compares device
        path as well as mount pathes.
        """
        for device in self:
            if device.is_file(path):
                return device
        logger = logging.getLogger(__name__)
        logger.warn(_('Device not found: {0}', path))
        return None


class Sniffer(UDisks):

    """
    UDisks DBus service wrapper.

    This is a wrapper for the DBus API of the UDisks service at
    'org.freedesktop.UDisks'. Access to properties and device states is
    completely online, meaning the properties are requested from dbus as
    they are accessed in the python object.
    """

    # Construction
    def __init__(self, proxy=None):
        """
        Initialize an instance with the given DBus proxy object.

        :param common.DBusProxy proxy: proxy to udisks object
        """
        self._proxy = proxy or self.connect_service()
        # Make sure the proxy object is loaded and usable:
        self._proxy.property.DaemonVersion

    def paths(self):
        return self._proxy.method.EnumerateDevices()

    def get(self, object_path):
        """Create a Device instance from object path."""
        return OnlineDevice(
            self,
            self._proxy.object.bus.get_object(object_path))
    update = get


class Daemon(Emitter, UDisks):

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

    def __init__(self, proxy=None):
        """
        Create a Daemon object and start listening to DBus events.

        :param common.DBusProxy proxy: proxy to the dbus service object

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

        proxy = proxy or self.connect_service()
        sniffer = Sniffer(proxy)

        self._sniffer = sniffer
        self._jobs = {}
        self._devices = {}
        self._errors = {'mount': {}, 'unmount': {},
                        'unlock': {}, 'lock': {},
                        'eject': {}, 'detach': {}}

        self.connect('device_changed', self._on_device_changed)
        proxy.connect('DeviceAdded', self._device_added)
        proxy.connect('DeviceRemoved', self._device_removed)
        proxy.connect('DeviceChanged', self._device_changed)
        proxy.connect('DeviceJobChanged', self._device_job_changed)
        self._sync()

    # Sniffer overrides
    def paths(self):
        """Iterate over all valid cached devices."""
        return (object_path
                for object_path, device in self._devices.items()
                if device)

    def get(self, object_path):
        """Return the current cached state of the device."""
        return self._devices.get(object_path)

    def update(self, object_path):
        device = self._sniffer.get(object_path)
        cached = CachedDevice(device)
        if cached or object_path not in self._devices:
            self._devices[object_path] = cached
        else:
            self._invalidate(object_path)
        return cached

    # special methods
    def set_error(self, device, action, message):
        self._errors[action][device.object_path] = message

    # events
    def _on_device_changed(self, old_state, new_state):
        """Detect type of event and trigger appropriate event handlers."""
        self._detect_toggle('has_media', old_state, new_state,
                            'media_added', 'media_removed')
        self._detect_toggle('is_mounted', old_state, new_state,
                            'device_mounted', 'device_unmounted')
        self._detect_toggle('is_unlocked', old_state, new_state,
                            'device_unlocked', 'device_locked')

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
        action_name = self._event_mapping.get(cached_job)
        if add_name and new_valid and not old_valid:
            if add_name != action_name:
                self.trigger(add_name, new)
        elif del_name and old_valid and not new_valid:
            if del_name != action_name:
                self.trigger(del_name, new)

    # UDisks event listeners
    def _device_added(self, object_path):
        """Internal method."""
        new_state = self.update(object_path)
        self.trigger('device_added', new_state)

    def _device_removed(self, object_path):
        """Internal method."""
        old_state = self[object_path]
        self._invalidate(object_path)
        self.trigger('device_removed', old_state)

    def _device_changed(self, object_path):
        """Internal method."""
        old_state = self[object_path]
        new_state = self.update(object_path)
        self.trigger('device_changed', old_state, new_state)

    # NOTE: it seems the UDisks1 documentation for DeviceJobChanged is
    # fatally incorrect!
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
                action = self._action_mapping[job_id]
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
            device = self[object_path]
            if self._check_success[action](device):
                event = self._event_mapping[action]
                self.trigger(event, device)
            else:
                # get and delete message, if available:
                message = self._errors[action].pop(object_path, "")
                self.trigger('job_failed', device, action, message)
                log = logging.getLogger(__name__)
                log.info(_('{0} operation failed for device: {1}',
                           job_id, object_path))

    # used internally by _device_job_changed:
    _action_mapping = {
        'FilesystemMount': 'mount',
        'FilesystemUnmount': 'unmount',
        'LuksUnlock': 'unlock',
        'LuksLock': 'lock',
        'DriveDetach': 'detach',
        'DriveEject': 'eject',
    }

    _event_mapping = {
        'mount': 'device_mounted',
        'unmount': 'device_unmounted',
        'unlock': 'device_unlocked',
        'lock': 'device_locked',
        'eject': 'media_removed',
        'detach': 'device_removed',
    }

    _check_success = {
        'mount': lambda dev: dev.is_mounted,
        'unmount': lambda dev: not dev or not dev.is_mounted,
        'unlock': lambda dev: dev.is_unlocked,
        'lock': lambda dev: not dev or not dev.is_unlocked,
        'detach': lambda dev: not dev,
        'eject': lambda dev: not dev or not dev.has_media,
    }

    # internal state keeping
    def _sync(self):
        """Cache all device states."""
        online_devices = {dev.object_path: dev for dev in self._sniffer}
        self._devices = {
            object_path: CachedDevice(device)
            for object_path, device in online_devices.items()
        }

    def _invalidate(self, object_path):
        """Flag the device invalid. This removes it from the iteration."""
        if object_path in self._devices:
            update = copy(self._devices[object_path])
            update.is_valid = False
            self._devices[object_path] = update
