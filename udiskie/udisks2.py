"""
UDisks2 wrapper utilities.

These act as a convenience abstraction layer on the UDisks2 DBus service.
Requires UDisks2 2.1.1 as described here:

    http://udisks.freedesktop.org/docs/latest

This wraps the DBus API of Udisks2.
"""

from copy import copy, deepcopy
import logging

from gi.repository import GLib

import udiskie.dbus as dbus
from .common import Emitter, AttrDictView, decode_ay, samefile, sameuuid
from .locale import _

__all__ = ['Daemon']


def object_kind(object_path):
    """
    Parse the kind of object from an UDisks2 object path.

    Example:
        /org/freedesktop/UDisks2/block_devices/sdb1 => device
        /org/freedesktop/UDisks2/drives/WDC_WD...   => drive
        /org/freedesktop/UDisks2/jobs/5             => job
    """
    try:
        return {
            'block_devices': 'device',
            'drives': 'drive',
            'jobs': 'job',
        }.get(object_path.split('/')[4])
    except IndexError:
        return None


def filter_opt(opt):
    """Remove ``None`` values from a dictionary."""
    return {k: GLib.Variant(*v) for k, v in opt.items() if v[1] is not None}


Interface = {
    'Manager':          'org.freedesktop.UDisks2.Manager',
    'Drive':            'org.freedesktop.UDisks2.Drive',
    'DriveAta':         'org.freedesktop.UDisks2.Drive.Ata',
    'MDRaid':           'org.freedesktop.UDisks2.MDRaid',
    'Block':            'org.freedesktop.UDisks2.Block',
    'Partition':        'org.freedesktop.UDisks2.Partition',
    'PartitionTable':   'org.freedesktop.UDisks2.PartitionTable',
    'Filesystem':       'org.freedesktop.UDisks2.Filesystem',
    'Swapspace':        'org.freedesktop.UDisks2.Swapspace',
    'Encrypted':        'org.freedesktop.UDisks2.Encrypted',
    'Loop':             'org.freedesktop.UDisks2.Loop',
    'Job':              'org.freedesktop.UDisks2.Job',
    'ObjectManager':    'org.freedesktop.DBus.ObjectManager',
    'Properties':       'org.freedesktop.DBus.Properties',
}


# ----------------------------------------
# Internal helper classes
# ----------------------------------------

class MethodHub:

    """Provide MethodsProxies for queried interfaces of a DBus object."""

    def __init__(self, object_proxy):
        """Initialize from (ObjectProxy)."""
        self._object_proxy = object_proxy

    def __getattr__(self, key):
        """Return a MethodsProxy for the requested interface."""
        return dbus.MethodsProxy(self._object_proxy, Interface[key])


class PropertyHub:

    """Provide attribute accessors for queried interfaces of a DBus object."""

    def __init__(self, interfaces_and_properties):
        """Initialize from (dict)."""
        self._interfaces_and_properties = interfaces_and_properties

    def __getattr__(self, key):
        """Return an AttrDictView for properties on the requested interface."""
        interface = Interface[key]
        try:
            return AttrDictView(self._interfaces_and_properties[interface])
        except KeyError:
            return PropertiesNotAvailable()


class PropertiesNotAvailable:

    """Null class for properties of an unavailable interface."""

    def __bool__(self):
        return False

    def __getattr__(self, key):
        """Return None when asked for any attribute."""
        return None


# ----------------------------------------
# Device wrapper
# ----------------------------------------

class Device:

    """
    Proxy class for UDisks2 devices.

    Properties are read from the cached values retrieved by the Daemon class.
    Methods are executed asynchronously, and hence return Asyncs instead of
    returning the result directly.
    """

    def __init__(self, daemon, object_path, property_hub, method_hub):
        """Initialize from (Daemon, str, PropertyHub, MethodHub)."""
        self._daemon = daemon
        self.object_path = object_path
        self._P = property_hub
        self._M = method_hub

    def __str__(self):
        """Show as object_path."""
        return self.object_path

    def __eq__(self, other):
        """Comparison by object_path."""
        return self.object_path == str(other)

    def __ne__(self, other):
        """Comparison by object_path."""
        return not (self == other)

    # availability of interfaces
    @property
    def is_drive(self):
        """Check if the device is a drive."""
        return bool(self._P.Drive)

    @property
    def is_block(self):
        """Check if the device is a block device."""
        return bool(self._P.Block)

    @property
    def is_partition_table(self):
        """Check if the device is a partition table."""
        return bool(self._P.PartitionTable)

    @property
    def is_partition(self):
        """Check if the device has a partition slave."""
        # Sometimes udisks2 empties the Partition interface before removing
        # the device. In this case, we want to report .is_partition=False, so
        # properties like .partition_slave will not be used.
        return bool(self._P.Partition and self.partition_slave)

    @property
    def is_filesystem(self):
        """Check if the device is a filesystem."""
        return bool(self._P.Filesystem)

    @property
    def is_luks(self):
        """Check if the device is a LUKS container."""
        return bool(self._P.Encrypted)

    @property
    def is_loop(self):
        """Check if the device is a loop device."""
        return bool(self._P.Loop)

    # ----------------------------------------
    # Drive
    # ----------------------------------------

    # Drive properties
    @property
    def is_toplevel(self):
        """Check if the device is not a child device."""
        return not self.is_partition and not self.is_luks_cleartext

    @property
    def parent(self):
        """Return the device of which this one is a child."""
        return self.partition_slave or self.luks_cleartext_slave

    @property
    def _assocdrive(self):
        """
        Return associated drive if this is a top level block device.

        This method is used internally to unify the behaviour of top level
        devices in udisks1 and udisks2.
        """
        # NOTE: always fallback to `self` because udisks2 doesn't report
        # CryptoBackingDevice nor Drive for logical volumes:
        return self.is_toplevel and not self.is_loop and self.drive or self

    @property
    def is_detachable(self):
        """Check if the drive that owns this device can be detached."""
        return bool(self._assocdrive._P.Drive.CanPowerOff)

    @property
    def is_ejectable(self):
        """Check if the drive that owns this device can be ejected."""
        return bool(self._assocdrive._P.Drive.Ejectable)

    @property
    def has_media(self):
        """Check if there is media available in the drive."""
        return bool(self._assocdrive._P.Drive.MediaAvailable)

    @property
    def drive_vendor(self):
        """Return drive vendor."""
        return self._assocdrive._P.Drive.Vendor

    @property
    def drive_model(self):
        """Return drive model."""
        return self._assocdrive._P.Drive.Model

    # Drive methods
    def eject(self, auth_no_user_interaction=None):
        """Eject media from the device."""
        return self._assocdrive._M.Drive.Eject(
            '(a{sv})',
            filter_opt({
                'auth.no_user_interaction': ('b', auth_no_user_interaction),
            })
        )

    def detach(self, auth_no_user_interaction=None):
        """Detach the device by e.g. powering down the physical port."""
        return self._assocdrive._M.Drive.PowerOff(
            '(a{sv})',
            filter_opt({
                'auth.no_user_interaction': ('b', auth_no_user_interaction),
            })
        )

    # ----------------------------------------
    # Block
    # ----------------------------------------

    # Block properties
    @property
    def device_file(self):
        """The filesystem path of the device block file."""
        return decode_ay(self._P.Block.Device)

    @property
    def device_presentation(self):
        """The device file path to present to the user."""
        return decode_ay(self._P.Block.PreferredDevice)

    @property
    def device_size(self):
        """The size of the device in bytes."""
        return self._P.Block.Size

    @property
    def id_usage(self):
        """Device usage class, for example 'filesystem' or 'crypto'."""
        return self._P.Block.IdUsage

    @property
    def is_crypto(self):
        """Check if the device is a crypto device."""
        return self.id_usage == 'crypto'

    @property
    def is_ignored(self):
        """Check if the device should be ignored."""
        return self._P.Block.HintIgnore

    @property
    def device_id(self):
        """
        Return a unique and persistent identifier for the device.

        This is the basename (last path component) of the symlink in
        `/dev/disk/by-id/`.
        """
        if self.is_block:
            for filename in self._P.Block.Symlinks:
                parts = decode_ay(filename).split('/')
                if parts[-2] == 'by-id':
                    return parts[-1]
        elif self.is_drive:
            return self._assocdrive._P.Drive.Id
        return ''

    @property
    def id_type(self):
        """"
        Return IdType property.

        This field provides further detail on IdUsage, for example:

        IdUsage     'filesystem'    'crypto'
        IdType      'ext4'          'crypto_LUKS'
        """
        return self._P.Block.IdType

    @property
    def id_label(self):
        """Label of the device if available."""
        return self._P.Block.IdLabel

    @property
    def id_uuid(self):
        """Device UUID."""
        return self._P.Block.IdUUID

    @property
    def luks_cleartext_slave(self):
        """Get wrapper to the LUKS crypto device."""
        return self._daemon[self._P.Block.CryptoBackingDevice]

    @property
    def is_luks_cleartext(self):
        """Check whether this is a luks cleartext device."""
        return bool(self.luks_cleartext_slave)

    @property
    def is_external(self):
        """Check if the device is external."""
        return not self.is_systeminternal

    @property
    def is_systeminternal(self):
        """Check if the device is internal."""
        return bool(self._P.Block.HintSystem)

    @property
    def drive(self):
        """Get wrapper to the drive containing this device."""
        if self.is_drive:
            return self
        elif self.is_block:
            return self._daemon[self._P.Block.Drive]
        else:
            return None

    @property
    def root(self):
        """Get the top level block device in the ancestry of this device."""
        return self if self.is_toplevel else self.parent.root

    @property
    def should_automount(self):
        """Check if the device should be automounted."""
        return bool(self._P.Block.HintAuto)

    @property
    def icon_name(self):
        """Return the recommended device icon name."""
        return self._P.Block.HintIconName or 'drive-removable-media'

    @property
    def symbolic_icon_name(self):
        """Return the recommended device symbolic icon name."""
        return self._P.Block.HintSymbolicIconName or 'drive-removable-media'

    @property
    def symlinks(self):
        """Known symlinks of the block device."""
        if not self._P.Block.Symlinks:
            return []
        return [decode_ay(path) for path in self._P.Block.Symlinks]

    # ----------------------------------------
    # Partition
    # ----------------------------------------

    # Partition properties
    @property
    def partition_slave(self):
        """Get the partition slave (container)."""
        return self._daemon[self._P.Partition.Table]

    @property
    def partition_uuid(self):
        """Get the partition UUID."""
        return self._P.Partition.UUID

    # ----------------------------------------
    # Filesystem
    # ----------------------------------------

    # Filesystem properties
    @property
    def is_mounted(self):
        """Check if the device is mounted."""
        return bool(self._P.Filesystem.MountPoints)

    @property
    def mount_paths(self):
        """Return list of active mount paths."""
        return list(map(decode_ay, self._P.Filesystem.MountPoints or ()))

    # Filesystem methods
    def mount(self,
              fstype=None,
              options=None,
              auth_no_user_interaction=None):
        """Mount filesystem."""
        return self._M.Filesystem.Mount(
            '(a{sv})',
            filter_opt({
                'fstype': ('s', fstype),
                'options': ('s', ','.join(options or [])),
                'auth.no_user_interaction': ('b', auth_no_user_interaction),
            })
        )

    def unmount(self, force=None, auth_no_user_interaction=None):
        """Unmount filesystem."""
        return self._M.Filesystem.Unmount(
            '(a{sv})',
            filter_opt({
                'force': ('b', force),
                'auth.no_user_interaction': ('b', auth_no_user_interaction),
            })
        )

    # ----------------------------------------
    # Encrypted
    # ----------------------------------------

    # Encrypted properties
    @property
    def luks_cleartext_holder(self):
        """Get wrapper to the unlocked luks cleartext device."""
        if not self.is_luks:
            return None
        for device in self._daemon:
            if device.luks_cleartext_slave == self:
                return device
        return None

    @property
    def is_unlocked(self):
        """Check if device is already unlocked."""
        return bool(self.luks_cleartext_holder)

    # Encrypted methods
    def unlock(self, password, auth_no_user_interaction=None):
        """Unlock Luks device."""
        return self._M.Encrypted.Unlock(
            '(sa{sv})',
            password,
            filter_opt({
                'auth.no_user_interaction': ('b', auth_no_user_interaction),
            })
        )

    def unlock_keyfile(self, password, auth_no_user_interaction=None):
        return self._M.Encrypted.Unlock(
            '(sa{sv})', '', filter_opt({
                'keyfile_contents': ('ay', password),
                'auth.no_user_interaction': ('b', auth_no_user_interaction),
            })
        )

    def lock(self, auth_no_user_interaction=None):
        """Lock Luks device."""
        return self._M.Encrypted.Lock(
            '(a{sv})',
            filter_opt({
                'auth.no_user_interaction': ('b', auth_no_user_interaction),
            })
        )

    # ----------------------------------------
    # Loop
    # ----------------------------------------

    @property
    def loop_file(self):
        """Get the file backing the loop device."""
        return decode_ay(self._P.Loop.BackingFile)

    @property
    def setup_by_uid(self):
        """Get the ID of the user who set up the loop device."""
        return self._P.Loop.SetupByUID

    @property
    def autoclear(self):
        """If True the loop device will be deleted after unmounting."""
        return self._P.Loop.Autoclear

    def delete(self, auth_no_user_interaction=None):
        """Delete loop partition."""
        return self._M.Loop.Delete(
            '(a{sv})',
            filter_opt({
                'auth.no_user_interaction': ('b', auth_no_user_interaction),
            })
        )

    def set_autoclear(self, value, auth_no_user_interaction=None):
        """Set autoclear flag for loop partition."""
        return self._M.Loop.SetAutoclear(
            '(ba{sv})',
            value,
            filter_opt({
                'auth.no_user_interaction': ('b', auth_no_user_interaction),
            })
        )

    # ----------------------------------------
    # derived properties
    # ----------------------------------------

    def is_file(self, path):
        """Comparison by mount and device file path."""
        return (samefile(path, self.device_file) or
                samefile(path, self.loop_file) or
                any(samefile(path, mp) for mp in self.mount_paths) or
                sameuuid(path, self.id_uuid) or
                sameuuid(path, self.partition_uuid))

    @property
    def parent_object_path(self):
        return (self._P.Partition.Table
                or self._P.Block.CryptoBackingDevice
                or '/')

    @property
    def mount_path(self):
        """Return any mount path."""
        try:
            return self.mount_paths[0]
        except IndexError:
            return ''

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
    def ui_id_label(self):
        """Label of the unlocked partition or the device itself."""
        return (self.luks_cleartext_holder or self).id_label

    @property
    def ui_id_uuid(self):
        """UUID of the unlocked partition or the device itself."""
        return (self.luks_cleartext_holder or self).id_uuid

    @property
    def ui_device_presentation(self):
        """Path of the crypto backing device or the device itself."""
        return (self.luks_cleartext_slave or self).device_presentation

    @property
    def ui_label(self):
        """UI string identifying the partition if possible."""
        return ': '.join(filter(None, [
            self.ui_device_presentation,
            self.ui_id_label or self.ui_id_uuid or self.drive_label
        ]))

    @property
    def ui_device_label(self):
        """UI string identifying the device (drive) if toplevel."""
        return ': '.join(filter(None, [
            self.ui_device_presentation,
            self.loop_file or
            self.drive_label or self.ui_id_label or self.ui_id_uuid
        ]))

    @property
    def drive_label(self):
        """Return drive label."""
        return ' '.join(filter(None, [
            self.drive_vendor,
            self.drive_model,
        ]))


# ----------------------------------------
# UDisks2 service wrapper
# ----------------------------------------

class Daemon(Emitter):

    """
    Listen to state changes to provide automatic synchronization.

    Listens to UDisks2 events. When a change occurs this class detects what
    has changed and triggers an appropriate event. Valid events are:

        - device_added    / device_removed
        - device_unlocked / device_locked
        - device_mounted  / device_unmounted
        - media_added     / media_removed
        - device_changed  / job_failed
    """

    BusName = 'org.freedesktop.UDisks2'
    ObjectPath = '/org/freedesktop/UDisks2'
    Interface = Interface['ObjectManager']

    def __iter__(self):
        """Iterate over all devices."""
        return (self[path] for path in self.paths()
                if object_kind(path) in ('device', 'drive'))

    def __getitem__(self, object_path):
        return self.get(object_path)

    def find(self, path):
        """
        Get a device proxy by device name or any mount path of the device.

        This searches through all accessible devices and compares device
        path as well as mount paths.
        """
        if isinstance(path, Device):
            return path
        for device in self:
            if device.is_file(path):
                self._log.debug(_('found device owning "{0}": "{1}"',
                                  path, device))
                return device
        raise FileNotFoundError(_('no device found owning "{0}"', path))

    def __init__(self, proxy, version):

        """Initialize object and start listening to UDisks2 events."""

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
        super().__init__(event_names)

        self._log = logging.getLogger(__name__)
        self._log.debug(_('Daemon version: {0}', version))

        self.version = version
        self.version_info = tuple(map(int, version.split('.')))
        self.keyfile_support = self.version_info >= (2, 6, 4)
        self._log.debug(_('Keyfile support: {0}', self.keyfile_support))

        self._proxy = proxy
        self._objects = {}

        proxy.connect('InterfacesAdded', self._interfaces_added)
        proxy.connect('InterfacesRemoved', self._interfaces_removed)

        bus = proxy.object.bus
        bus.connect(Interface['Properties'],
                    'PropertiesChanged',
                    None,
                    self._properties_changed)
        bus.connect(Interface['Job'],
                    'Completed',
                    None,
                    self._job_completed)

    async def _sync(self):
        """Synchronize state."""
        self._objects = await self._proxy.call('GetManagedObjects', '()')

    @classmethod
    async def create(cls):
        service = (cls.BusName, cls.ObjectPath, cls.Interface)
        proxy = await dbus.connect_service(*service)
        version = await cls.get_version()
        daemon = cls(proxy, version)
        await daemon._sync()
        return daemon

    @classmethod
    async def get_version(cls):
        service = (cls.BusName,
                   '/org/freedesktop/UDisks2/Manager',
                   Interface['Properties'])
        manager = await dbus.connect_service(*service)
        version = await dbus.call(manager._proxy, 'Get', '(ss)', (
            Interface['Manager'], 'Version'))
        return version

    async def loop_setup(self, fd, options):
        service = (self.BusName,
                   '/org/freedesktop/UDisks2/Manager',
                   Interface['Manager'])
        manager = await dbus.connect_service(*service)
        object_path = await dbus.call_with_fd_list(
            manager._proxy, 'LoopSetup', '(ha{sv})',
            (0, filter_opt({
                'auth.no_user_interaction': (
                    'b', options.get('auth.no_user_interaction')),
                'offset': ('t', options.get('offset')),
                'size': ('t', options.get('size')),
                'read-only': ('b', options.get('read-only')),
                'no-part-scan': ('b', options.get('no-part-scan')),
            })),
            [fd],
        )
        await self._sync()
        return self[object_path]

    # UDisks2 interface
    def paths(self):
        return self._objects.keys()

    def get(self, object_path, interfaces_and_properties=None):
        """Create a Device instance from object path."""
        # check this before creating the DBus object for more
        # controlled behaviour:
        if not interfaces_and_properties:
            interfaces_and_properties = self._objects.get(object_path)
            if not interfaces_and_properties:
                return None
        property_hub = PropertyHub(interfaces_and_properties)
        method_hub = MethodHub(
            self._proxy.object.bus.get_object(object_path))
        return Device(self, object_path, property_hub, method_hub)

    def trigger(self, event, device, *args):
        self._log.debug(_("+++ {0}: {1}", event, device))
        super().trigger(event, device, *args)

    # add objects / interfaces
    def _interfaces_added(self, object_path, interfaces_and_properties):
        """Internal method."""
        added = object_path not in self._objects
        self._objects.setdefault(object_path, {})
        old_state = copy(self._objects[object_path])
        self._objects[object_path].update(interfaces_and_properties)
        new_state = self._objects[object_path]
        if added:
            kind = object_kind(object_path)
            if kind in ('device', 'drive'):
                self.trigger('device_added', self[object_path])

        if Interface['Block'] in interfaces_and_properties:
            slave = self[object_path].luks_cleartext_slave
            if slave:
                if not self._has_job(slave.object_path, 'device_unlocked'):
                    self.trigger('device_unlocked', slave)

        if not added:
            self.trigger('device_changed',
                         self.get(object_path, old_state),
                         self.get(object_path, new_state))

    # remove objects / interfaces
    def _detect_toggle(self, property_name, old, new, add_name, del_name):
        old_valid = old and bool(getattr(old, property_name))
        new_valid = new and bool(getattr(new, property_name))
        if add_name and new_valid and not old_valid:
            if not self._has_job(old.object_path, add_name):
                self.trigger(add_name, new)
        elif del_name and old_valid and not new_valid:
            if not self._has_job(old.object_path, del_name):
                self.trigger(del_name, new)

    def _has_job(self, device_path, event_name):
        job_interface = Interface['Job']
        for path, interfaces in self._objects.items():
            try:
                job = interfaces[job_interface]
                job_objects = job['Objects']
                job_operation = job['Operation']
                job_action = self._action_by_operation[job_operation]
                job_event = self._event_by_action[job_action]
                if event_name == job_event and device_path in job_objects:
                    return True
            except KeyError:
                pass
        return False

    def _interfaces_removed(self, object_path, interfaces):
        """Internal method."""
        old_state = copy(self._objects[object_path])
        for interface in interfaces:
            del self._objects[object_path][interface]
        new_state = self._objects[object_path]

        if Interface['Drive'] in interfaces:
            self._detect_toggle(
                'has_media',
                self.get(object_path, old_state),
                self.get(object_path, new_state),
                None, 'media_removed')

        if Interface['Block'] in interfaces:
            slave = self.get(object_path, old_state).luks_cleartext_slave
            if slave:
                if not self._has_job(slave.object_path, 'device_locked'):
                    self.trigger('device_locked', slave)

        if self._objects[object_path]:
            self.trigger('device_changed',
                         self.get(object_path, old_state),
                         self.get(object_path, new_state))
        else:
            del self._objects[object_path]
            if object_kind(object_path) in ('device', 'drive'):
                self.trigger(
                    'device_removed',
                    self.get(object_path, old_state))

    # change interface properties
    def _properties_changed(self,
                            object_path,
                            interface_name,
                            changed_properties,
                            invalidated_properties):
        """
        Internal method.

        Called when a DBusProperty of any managed object changes.
        """
        # update device state:
        old_state = deepcopy(self._objects[object_path])
        for property_name in invalidated_properties:
            del self._objects[object_path][interface_name][property_name]
        for key, value in changed_properties.items():
            self._objects[object_path][interface_name][key] = value
        new_state = self._objects[object_path]
        # detect changes and trigger events:
        if interface_name == Interface['Drive']:
            self._detect_toggle(
                'has_media',
                self.get(object_path, old_state),
                self.get(object_path, new_state),
                'media_added', 'media_removed')
        elif interface_name == Interface['Filesystem']:
            self._detect_toggle(
                'is_mounted',
                self.get(object_path, old_state),
                self.get(object_path, new_state),
                'device_mounted', 'device_unmounted')
        self.trigger('device_changed',
                     self.get(object_path, old_state),
                     self.get(object_path, new_state))
        # There is no PropertiesChanged for the crypto device when it is
        # unlocked/locked in UDisks2. Instead, this is handled by the
        # InterfaceAdded/Removed handlers.

    # jobs
    _action_by_operation = {
        'filesystem-mount': 'mount',
        'filesystem-unmount': 'unmount',
        'encrypted-unlock': 'unlock',
        'encrypted-lock': 'lock',
        'power-off-drive': 'detach',
        'eject-media': 'eject',
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

    def _job_completed(self, job_name, success, message):
        """
        Internal method.

        Called when a job of a long running task completes.
        """
        job = self._objects[job_name][Interface['Job']]
        action = self._action_by_operation.get(job['Operation'])
        if not action:
            return
        # We only handle events, which are associated to exactly one object:
        object_path, = job['Objects']
        device = self[object_path]
        if success:
            # It rarely happens, but sometimes UDisks posts the
            # Job.Completed event before PropertiesChanged, so we have to
            # check if the operation has been carried out yet:
            if self._check_action_success[action](device):
                event_name = self._event_by_action[action]
                self.trigger(event_name, device)
        else:
            self.trigger('job_failed', device, action, message)
