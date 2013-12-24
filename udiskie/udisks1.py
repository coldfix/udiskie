"""
Udisks wrapper utilities.

These act as a convenience abstraction layer on the udisks dbus service.
Requires Udisks 1.0.5 as described here:

    http://udisks.freedesktop.org/docs/1.0.5/

Note that (as this completely wraps the udisks dbus API) replacing this
module will let you support Udisks2 or maybe even other services.

"""
__all__ = ['Udisks', 'Daemon']

import logging
import os
import sys
from udiskie.common import DBusProxy, Emitter
from inspect import getmembers


UDISKS_INTERFACE = 'org.freedesktop.UDisks'
UDISKS_DEVICE_INTERFACE = 'org.freedesktop.UDisks.Device'

UDISKS_OBJECT = 'org.freedesktop.UDisks'
UDISKS_OBJECT_PATH = '/org/freedesktop/UDisks'


class Device(DBusProxy):
    """
    Online wrapper for org.freedesktop.UDisks.Device dbus API proxy objects.

    Resolves both property access and method calls dynamically to the dbus
    object.

    """
    # construction
    def __init__(self, udisks, proxy):
        """
        Initialize an instance with the given dbus proxy object.

        proxy must be an object acquired by a call to bus.get_object().

        """
        self.log = logging.getLogger('udiskie.udisks.Device')
        super(Device, self).__init__(proxy, UDISKS_DEVICE_INTERFACE)
        self.udisks = udisks

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

    # check if the device is a valid udisks object
    @property
    def is_valid(self):
        try:
            self.property.DeviceFile
            return True
        except self.Exception:
            return False

    # properties
    @property
    def partition_slave(self):
        """Get the partition slave (container)."""
        return self.udisks.create_device(self.property.PartitionSlave) if self.is_partition else None

    @property
    def is_partition(self):
        """Check if the device has a partition slave."""
        return self.property.DeviceIsPartition

    @property
    def is_partition_table(self):
        """Check if the device is a partition table."""
        return self.property.DeviceIsPartitionTable

    @property
    def is_drive(self):
        """Check if the device is a drive."""
        return self.property.DeviceIsDrive

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

    @property
    def is_detachable(self):
        """Check if the drive that owns this device can be detached."""
        return self.property.DriveCanDetach if self.is_drive else None

    @property
    def is_ejectable(self):
        """Check if the drive that owns this device can be ejected."""
        return self.property.DriveIsMediaEjectable if self.is_drive else None

    @property
    def is_systeminternal(self):
        """Check if the device is internal."""
        return self.property.DeviceIsSystemInternal

    @property
    def is_external(self):
        """Check if the device is external."""
        return not self.is_systeminternal

    @property
    def is_mounted(self):
        """Check if the device is mounted."""
        return self.property.DeviceIsMounted

    @property
    def is_unlocked(self):
        """Check if device is already unlocked."""
        return self.luks_cleartext_holder if self.is_luks else None

    @property
    def mount_paths(self):
        """Return list of active mount paths."""
        if not self.is_mounted:
            return []
        raw_paths = self.property.DeviceMountPaths
        return [os.path.normpath(path) for path in raw_paths]

    @property
    def device_file(self):
        """The filesystem path of the device block file."""
        return os.path.normpath(self.property.DeviceFile)

    @property
    def device_presentation(self):
        """The device file path to present to the user."""
        return self.property.DeviceFilePresentation

    @property
    def is_filesystem(self):
        return self.id_usage == 'filesystem'

    @property
    def is_crypto(self):
        return self.id_usage == 'crypto'

    @property
    def is_luks(self):
        return self.property.DeviceIsLuks

    @property
    def is_luks_cleartext(self):
        """Check whether this is a luks cleartext device."""
        return self.property.DeviceIsLuksCleartext

    @property
    def luks_cleartext_slave(self):
        """Get luks crypto device."""
        return self.udisks.create_device(self.property.LuksCleartextSlave) if self.is_luks_cleartext else None

    @property
    def luks_cleartext_holder(self):
        """Get unlocked luks cleartext device."""
        return self.udisks.create_device(self.property.LuksHolder) if self.is_luks else None

    @property
    def is_luks_cleartext_slave(self):
        """Check whether the luks device is currently in use."""
        if not self.is_luks:
            return False
        for device in self.udisks.get_all():
            if (not device.is_filesystem or device.is_mounted) and (
                    device.is_luks_cleartext and
                    device.luks_cleartext_slave == self):
                return True
        return False

    @property
    def has_media(self):
        return self.property.DeviceIsMediaAvailable

    @property
    def id_type(self):
        return self.property.IdType

    @property
    def id_usage(self):
        return self.property.IdUsage

    @property
    def id_uuid(self):
        """Device UUID."""
        return self.property.IdUuid

    # methods
    def mount(self, filesystem=None, options=[]):
        """Mount filesystem."""
        if filesystem is None:
            filesystem = self.id_type
        self.method.FilesystemMount(filesystem, options)

    def unmount(self, options=[]):
        """Unmount filesystem."""
        self.method.FilesystemUnmount(options)

    def lock(self, options=[]):
        """Lock Luks device."""
        return self.method.LuksLock(options)

    def unlock(self, password, options=[]):
        """Unlock Luks device."""
        return self.method.LuksUnlock(password, options)

    def eject(self, options=[]):
        """Eject media from the device."""
        return self.method.DriveEject(options)

    def detach(self, options=[]):
        """Detach the device by e.g. powering down the physical port."""
        return self.method.DriveDetach(options)

def _CachedDeviceProperty(method):
    """Cache object path and return the current known CachedDevice state."""
    key = '_'+method.__name__
    def get(self):
        object_path = getattr(self, key, None)
        return self.udisks.device_states[object_path] if object_path else None
    def set(self, device):
        object_path = getattr(device, 'object_path', None)
        setattr(self, key, object_path)
    return property(get, set, doc=method.__doc__)


class CachedDevice(object):
    """
    Cached device state.

    Properties are cached at creation time. Methods will be invoked
    dynamically via the associated dbus object.

    """
    def __init__(self, device):
        """Cache all properties of the online device."""
        self._device = device
        self._udisks = device.udisks
        def isproperty(obj):
            return isinstance(obj, property)
        for key,val in getmembers(device.__class__, isproperty):
            try:
                setattr(self, key, getattr(device, key))
            except device.Exception:
                setattr(self, key, None)
        self.is_valid = device.is_valid

    def __getattr__(self, key):
        """Resolve unknown properties and methods via the online device."""
        return getattr(self._device, key)

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

    # Overload properties that return Device objects to return CachedDevice
    # instances instead. NOTE: the setters are implemented such that the
    # returned devices will be cached at the time the property is accessed
    # rather than at the time the current object was instanciated.
    # FIXME: should it be different?

    @_CachedDeviceProperty
    def drive(self):
        """Get the partition slave (container)."""
        pass

    @_CachedDeviceProperty
    def partition_slave(self):
        """Get the partition slave (container)."""
        pass

    @_CachedDeviceProperty
    def luks_cleartext_slave(self):
        """Get luks crypto device."""
        pass

    @_CachedDeviceProperty
    def luks_cleartext_holder(self):
        """Get unlocked luks cleartext device."""
        pass


class Udisks(DBusProxy):
    """
    Udisks dbus service wrapper.

    This is a dbus proxy object to the org.freedesktop.UDisks interface of
    the udisks service object.

    """
    # Construction
    def __init__(self, bus, proxy):
        """
        Initialize an instance with the given dbus proxy object.

        proxy must be an object acquired by a call to bus.get_object().

        """
        super(Udisks, self).__init__(proxy, UDISKS_INTERFACE)
        self.bus = bus
        self.device_states = {}
        self.deleted = {}

    @classmethod
    def create(cls, bus):
        """Connect to the udisks service on the specified bus."""
        return cls(bus, bus.get_object(UDISKS_OBJECT, UDISKS_OBJECT_PATH))

    # instantiation of device objects
    def create_device(self, object_path):
        """Create a Device instance from object path."""
        return Device(self, self.bus.get_object(UDISKS_OBJECT, object_path))

    # Methods
    def get_all(self):
        """Enumerate all device objects currently known to udisks."""
        return self.device_states.values()

    def get_device(self, path):
        """
        Get a device proxy by device name or any mount path of the device.

        This searches through all accessible devices and compares device
        path as well as mount pathes.

        """
        logger = logging.getLogger('udiskie.udisks.get_device')
        for device in self.get_all():
            if os.path.samefile(path, device.device_file):
                return device
            for p in device.mount_paths:
                if os.path.samefile(path, p):
                    return device
        logger.warn('Device not found: %s' % path)
        return None

    # internal state keeping
    def sync(self):
        """Cache all device states."""
        for object_path in self.method.EnumerateDevices():
            self._upd_device_state(object_path)

    def _get_device_state(self, object_path, fallback=False):
        dev = self.device_states.get(object_path)
        if not dev and fallback:
            dev = self.deleted.get(object_path)
        return dev

    def _upd_device_state(self, object_path):
        device = self.create_device(object_path)
        cached = CachedDevice(device)
        if cached.is_valid:
            self.device_states[object_path] = cached
        return cached

    def _del_device_state(self, object_path):
        if object_path in self.device_states:
            self.deleted[object_path] = self.device_states.pop(object_path)


#----------------------------------------
# daemonic code:
#----------------------------------------

class Job(object):
    """
    Job information struct for devices.
    """
    __slots__ = ['id', 'percentage']

    def __init__(self, id, percentage):
        self.id = id
        self.percentage = percentage

class Daemon(Emitter):
    """
    Udisks listener daemon.

    Listens to udisks events. When a change occurs this class detects what
    has changed and triggers an appropriate event. Valid events are:

        - device_added    / device_removed
        - device_unlocked / device_locked
        - device_mounted  / device_unmounted
        - media_added     / media_removed
        - device_changed

    A very primitive mechanism that gets along without external
    dependencies is used for event dispatching. The methods `connect` and
    `disconnect` can be used to add or remove event handlers.

    """
    def __init__(self, udisks):
        """
        Initialize object and start listening to udisks events.
        """
        event_names = (stem + suffix
                       for suffix in ('ed', 'ing')
                       for stem in (
                           'device_add',
                           'device_remov',
                           'device_mount',
                           'device_unmount',
                           'media_add',
                           'media_remov',
                           'device_unlock',
                           'device_lock',
                           'device_chang', ))
        super(Daemon, self).__init__(event_names)

        self.log = logging.getLogger('udiskie.daemon.Daemon')
        self.jobs = {}
        self.udisks = udisks

        self.connect(self.on_device_changed, 'device_changed')

        udisks.bus.add_signal_receiver(
            self._device_added,
            signal_name='DeviceAdded',
            bus_name='org.freedesktop.UDisks')
        udisks.bus.add_signal_receiver(
            self._device_removed,
            signal_name='DeviceRemoved',
            bus_name='org.freedesktop.UDisks')
        udisks.bus.add_signal_receiver(
            self._device_changed,
            signal_name='DeviceChanged',
            bus_name='org.freedesktop.UDisks')
        udisks.bus.add_signal_receiver(
            self._device_job_changed,
            signal_name='DeviceJobChanged',
            bus_name='org.freedesktop.UDisks')
        udisks.sync()

    # events
    def on_device_changed(self, old_state, new_state):
        """Detect type of event and trigger appropriate event handlers."""
        if old_state is None:
            self.trigger('device_added', new_state)
            return
        d = {}
        d['media_added'] = new_state.has_media and not old_state.has_media
        d['media_removed'] = old_state.has_media and not new_state.has_media
        for event in d:
            if d[event]:
                self.trigger(event, new_state)

    # udisks event listeners
    def _device_added(self, object_path):
        new_state = self.udisks._upd_device_state(object_path)
        self.trigger('device_added', new_state)

    def _device_removed(self, object_path):
        old_state = self.udisks._get_device_state(object_path)
        self.udisks._del_device_state(object_path)
        self.trigger('device_removed', old_state)

    def _device_changed(self, object_path):
        old_state = self.udisks._get_device_state(object_path, True)
        new_state = self.udisks._upd_device_state(object_path)
        self.trigger('device_changed', old_state, new_state)

    # NOTE: it seems the udisks1 documentation for DeviceJobChanged is
    # fatally incorrect!
    def _device_job_changed(self,
                            object_path,
                            job_in_progress,
                            job_id,
                            job_initiated_by_user,
                            job_is_cancellable,
                            job_percentage):
        """Detect type of event and trigger appropriate event handlers."""
        event_mapping = {
            'FilesystemMount': 'device_mount',
            'FilesystemUnmount': 'device_unmount',
            'LuksUnlock': 'device_unlock',
            'LuksLock': 'device_lock', }
        if not job_in_progress and object_path in self.jobs:
            job_id = self.jobs[object_path].id

        if job_id in event_mapping:
            event_name = event_mapping[job_id]
            dev = self.udisks._get_device_state(object_path, True)
            if job_in_progress:
                self.trigger(event_name + 'ing', dev, job_percentage)
                self.jobs[object_path] = Job(job_id, job_percentage)
            else:
                self.trigger(event_name + 'ed', dev)
                del self.jobs[object_path]

