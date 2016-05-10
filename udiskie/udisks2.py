"""
UDisks2 wrapper utilities.

These act as a convenience abstraction layer on the UDisks2 DBus service.
Requires UDisks2 2.1.1 as described here:

    http://udisks.freedesktop.org/docs/latest

This wraps the DBus API of Udisks2 providing a common interface with the
udisks1 module.
"""

from __future__ import absolute_import
from __future__ import unicode_literals

from copy import copy, deepcopy
import logging

from gi.repository import GLib

from .common import Emitter, samefile, sameuuid, AttrDictView, decode_ay
from .compat import fix_str_conversions
from .dbus import connect_service, MethodsProxy
from .locale import _
from .async_ import Coroutine, Return

__all__ = ['Daemon']


def object_kind(object_path):
    """
    Parse the kind of object from an UDisks2 object path.

    Example: /org/freedesktop/UDisks2/block_devices/sdb1 => device
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

class MethodHub(object):

    """Provide MethodsProxies for queried interfaces of a DBus object."""

    def __init__(self, object_proxy):
        """Initialize from (ObjectProxy)."""
        self._object_proxy = object_proxy

    def __getattr__(self, key):
        """Return a MethodsProxy for the requested interface."""
        return MethodsProxy(self._object_proxy, Interface[key])


class PropertyHub(object):

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


class PropertiesNotAvailable(object):

    """Null class for properties of an unavailable interface."""

    def __nonzero__(self):      # python2
        return False
    __bool__ = __nonzero__      # python3

    def __getattr__(self, key):
        """Return None when asked for any attribute."""
        return None


# ----------------------------------------
# Device wrapper
# ----------------------------------------

@fix_str_conversions
class Device(object):

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
    def _assocdrive(self):
        """
        Return associated drive if this is a top level block device.

        This method is used internally to unify the behaviour of top level
        devices in udisks1 and udisks2.
        """
        return self.drive if self.is_toplevel and not self.is_loop else self

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
        # NOTE: Checking for equality HintSystem==False returns False if the
        # property is resolved to a None value (interface not available).
        if self._P.Block.HintSystem == False:
            return True
        # NOTE: udisks2 seems to guess incorrectly in some cases. This
        # leads to HintSystem=True for unlocked devices. In order to show
        # the device anyway, it needs to be recursively checked if any
        # parent device is recognized as external.
        if self.is_luks_cleartext and self.luks_cleartext_slave.is_external:
            return True
        if self.is_partition and self.partition_slave.is_external:
            return True
        return False

    @property
    def is_systeminternal(self):
        """Check if the device is internal."""
        return not self.is_external

    @property
    def drive(self):
        """Get wrapper to the drive containing this device."""
        if self.is_drive:
            return self
        cleartext = self.luks_cleartext_slave
        if cleartext:
            return cleartext.drive
        if self.is_block:
            return self._daemon[self._P.Block.Drive]
        return None

    @property
    def root(self):
        """
        Get the top level block device in the ancestry of this device.
        """
        drive = self.drive
        for device in self._daemon:
            if device.is_drive:
                continue
            if device.is_toplevel and device.drive == drive:
                return device
        return None

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
        return (self._P.Partition.Table
                or self._P.Block.CryptoBackingDevice
                or '/')

    @property
    def ui_label(self):
        return self.id_label or self.id_uuid or self.device_presentation


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
        super(Daemon, self).__init__(event_names)

        self._proxy = proxy
        self._log = logging.getLogger(__name__)
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

    def _sync(self):
        """Synchronize state."""
        def update_objects(objects):
            self._objects = objects
        update = self._proxy.call('GetManagedObjects', '()')
        update.callbacks.append(update_objects)
        return update

    @classmethod
    @Coroutine.from_generator_function
    def create(cls):
        proxy = yield connect_service(cls)
        daemon = cls(proxy)
        yield daemon._sync()
        yield Return(daemon)

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
        super(Daemon, self).trigger(event, device, *args)

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
