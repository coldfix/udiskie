"""
UDisks wrapper utilities.

These act as a convenience abstraction layer on the UDisks DBus service.
Requires UDisks 1.0.5 as described here:

    http://udisks.freedesktop.org/docs/1.0.5/

Note that (as this completely wraps the UDisks DBus API) replacing this
module will let you support UDisks2 or maybe even other services.

Overview: This module exports the classes ``Sniffer`` and ``Daemon``.

``Sniffer`` can be used as an online exporter of the current device states
queried from the UDisks DBus service as requested.

``Daemon`` caches all device states and listens to UDisks events to
guarantee the validity of device objects during operations.

"""
__all__ = ['Sniffer', 'Daemon']

import logging
import os.path
from copy import copy
from inspect import getmembers

from udiskie.common import DBusProxy, Emitter

def samefile(a, b):
    """Check if two pathes represent the same file."""
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.normpath(a) == os.path.normpath(b)

class Device(DBusProxy):
    """
    Online wrapper for org.freedesktop.UDisks.Device DBus API proxy objects.

    Resolves both property access and method calls dynamically to the DBus
    object.

    """
    Interface = 'org.freedesktop.UDisks.Device'

    # construction
    def __init__(self, udisks, proxy):
        """
        Initialize an instance with the given DBus proxy object.

        proxy must be an object acquired by a call to bus.get_object().

        """
        super(Device, self).__init__(proxy, self.Interface)
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

    # check if the device is a valid UDisks object
    @property
    def is_valid(self):
        try:
            self.property.DeviceFile
            return True
        except self.Exception:
            return False

    def __nonzero__(self):      # python2
        return self.is_valid
    __bool__ = __nonzero__      # python3

    def is_file(self, path):
        """Comparison by mount and device file path."""
        return samefile(path, self.device_file) or any(
            samefile(path, mp) for mp in self.mount_paths)

    # properties
    @property
    def partition_slave(self):
        """Get the partition slave (container)."""
        return self.udisks[self.property.PartitionSlave] if self.is_partition else None

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
        return self.udisks[self.property.LuksCleartextSlave] if self.is_luks_cleartext else None

    @property
    def luks_cleartext_holder(self):
        """Get unlocked luks cleartext device."""
        return self.udisks[self.property.LuksHolder] if self.is_luks else None

    @property
    def is_luks_cleartext_slave(self):
        """Check whether the luks device is currently in use."""
        if not self.is_luks:
            return False
        for device in self.udisks:
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
    def id_label(self):
        return self.property.IdLabel

    @property
    def id_uuid(self):
        """Device UUID."""
        return self.property.IdUuid

    # methods
    def mount(self, filesystem=None, options=[]):
        """Mount filesystem."""
        if filesystem is None:
            filesystem = self.id_type
        return self.method.FilesystemMount(filesystem, options)

    def unmount(self, options=[]):
        """Unmount filesystem."""
        return self.method.FilesystemUnmount(options)

    def lock(self, options=[]):
        """Lock Luks device."""
        return self.method.LuksLock(options)

    def unlock(self, password, options=[]):
        """Unlock Luks device."""
        return self.udisks.update(self.method.LuksUnlock(password, options))

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
        return self._daemon[getattr(self, key, None)]
    def set(self, device):
        setattr(self, key, getattr(device, 'object_path', None))
    return property(get, set, doc=method.__doc__)

class CachedDevice(object):
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
        for key,val in getmembers(device.__class__, isproperty):
            try:
                setattr(self, key, getattr(device, key))
            except device.Exception:
                setattr(self, key, None)
        self.is_valid = device.is_valid

    def __getattr__(self, key):
        """Resolve unknown properties and methods via the online device."""
        return getattr(self._device, key)

    def __nonzero__(self):      # python2
        return self.is_valid
    __bool__ = __nonzero__      # python3

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

    def unlock(self, password, options=[]):
        """Unlock Luks device."""
        return CachedDevice(self._device.unlock(password, options))

class UDisks(object):
    """
    Base class for UDisks service wrappers.

    """
    BusName = 'org.freedesktop.UDisks'
    Interface = 'org.freedesktop.UDisks'
    ObjectPath = '/org/freedesktop/UDisks'

    def __iter__(self):
        """Iterate over all devices."""
        return (dev for dev in map(self.get, self.paths()) if dev)

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
        logger = logging.getLogger('udiskie.udisks.find')
        logger.warn('Device not found: %s' % path)
        return None

class Sniffer(DBusProxy, UDisks):
    """
    UDisks DBus service wrapper.

    This is a wrapper for the DBus API of the UDisks service at
    'org.freedesktop.UDisks'. Access to properties and device states is
    completely online, meaning the properties are requested from dbus as
    they are accessed in the python object.

    """
    # Construction
    def __init__(self, bus=None, proxy=None):
        """
        Initialize an instance with the given DBus proxy object.

        :param dbus.Bus bus: connection to system bus
        :param dbus.proxies.ProxyObject proxy: proxy to udisks object

        """
        if proxy is None:
            if bus is None:
                from dbus import SystemBus
                bus = SystemBus()
            proxy = bus.get_object(self.BusName, self.ObjectPath)
        super(Sniffer, self).__init__(proxy, self.Interface)

    def paths(self):
        return self.method.EnumerateDevices()

    def get(self, object_path):
        """Create a Device instance from object path."""
        return Device(self, self._bus.get_object(self.BusName, object_path))

    update = get

class Job(object):
    """Job information struct for devices."""
    def __init__(self, job_id, percentage):
        self.job_id = job_id
        self.percentage = percentage

class Daemon(Emitter, UDisks):
    """
    UDisks listener daemon.

    Listens to UDisks events. When a change occurs this class detects what
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
    def __init__(self, bus=None, proxy=None, sniffer=None):
        """
        Create a Daemon object and start listening to DBus events.

        :param dbus.Bus bus: connection to system bus
        :param dbus.proxies.ProxyObject proxy: proxy

        If the connection is not passed a new one will be created and dbus
        will be configured for the gobject mainloop.

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

        if sniffer is None:
            if bus is None and proxy is None:
                import dbus
                from dbus.mainloop.glib import DBusGMainLoop
                DBusGMainLoop(set_as_default=True)
            sniffer = Sniffer(bus, proxy)

        self._sniffer = sniffer
        self._jobs = {}
        self._devices = {}

        self.connect(self._on_device_changed, 'device_changed')
        self._sniffer._bus.add_signal_receiver(
            self._device_added,
            signal_name='DeviceAdded',
            bus_name=self.BusName)
        self._sniffer._bus.add_signal_receiver(
            self._device_removed,
            signal_name='DeviceRemoved',
            bus_name=self.BusName)
        self._sniffer._bus.add_signal_receiver(
            self._device_changed,
            signal_name='DeviceChanged',
            bus_name=self.BusName)
        self._sniffer._bus.add_signal_receiver(
            self._device_job_changed,
            signal_name='DeviceJobChanged',
            bus_name=self.BusName)
        self._sync()

    # Sniffer overrides
    def paths(self):
        """Iterate over all valid cached devices."""
        return (object_path
                for object_path,device in self._devices.items()
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

    # events
    def _on_device_changed(self, old_state, new_state):
        """Detect type of event and trigger appropriate event handlers."""
        d = {}
        d['media_added'] = new_state.has_media and not old_state.has_media
        d['media_removed'] = old_state.has_media and not new_state.has_media
        for event in d:
            if d[event]:
                self.trigger(event, new_state)

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
        event_mapping = {
            'FilesystemMount': 'device_mount',
            'FilesystemUnmount': 'device_unmount',
            'LuksUnlock': 'device_unlock',
            'LuksLock': 'device_lock', }
        check_success = {
            'FilesystemMount': lambda dev: dev.is_mounted,
            'FilesystemUnmount': lambda dev: not dev or not dev.is_mounted,
            'LuksUnlock': lambda dev: dev.is_unlocked,
            'LuksLock': lambda dev: not dev or not dev.is_unlocked, }
        if not job_in_progress and object_path in self._jobs:
            job_id = self._jobs[object_path].job_id

        if job_id in event_mapping:
            event_name = event_mapping[job_id]
            dev = self[object_path]
            if job_in_progress:
                self.trigger(event_name + 'ing', dev, job_percentage)
                self._jobs[object_path] = Job(job_id, job_percentage)
            elif check_success[job_id](dev):
                self.trigger(event_name + 'ed', dev)
                del self._jobs[object_path]
            else:
                log = logging.getLogger('udiskie.daemon.Daemon')
                log.info('%s operation failed for device: %s' % (job_id, object_path))

    # internal state keeping
    def _sync(self):
        """Cache all device states."""
        self._devices = { dev.object_path: dev for dev in self._sniffer }
        self._devices = {
            object_path: CachedDevice(device)
            for object_path,device in self._devices.items() }

    def _invalidate(self, object_path):
        """Flag the device invalid. This removes it from the iteration."""
        if object_path in self._devices:
            update = copy(self._devices[object_path])
            update.is_valid = False
            self._devices[object_path] = update

