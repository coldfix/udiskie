"""
Udiskie mount utilities.
"""
__all__ = [
    'mount_device', 'unlock_device', 'add_device',
    'mount_all',
    'Mounter']

import logging
import dbus

import udiskie.device


def mount_device(device, filter=None):
    """
    Mount the device if not already mounted.

    Return value indicates whether an action was performed successfully.
    The special value `None` means unknown/unreliable.

    """
    log = logging.getLogger('udiskie.mount.mount_device')
    if not device.is_handleable or not device.is_filesystem:
        log.debug('skipping unhandled device %s' % (device,))
        return False
    if device.is_mounted:
        log.debug('skipping mounted device %s' % (device,))
        return False

    fstype = str(device.id_type)
    options = filter.get_mount_options(device) if filter else []

    S = 'attempting to mount device %s (%s:%s)'
    log.info(S % (device, fstype, options))

    try:
        device.mount(fstype, options)
        log.info('mounted device %s' % (device,))
    except dbus.exceptions.DBusException, dbus_err:
        log.error('failed to mount device %s: %s' % (
                                            device, dbus_err))
        return None

    mount_paths = ', '.join(device.mount_paths)
    return True

def unlock_device(device, prompt):
    """
    Unlock the device if not already unlocked.

    Return value indicates whether an action was performed successfully.
    The special value `None` means unknown/unreliable.

    """
    log = logging.getLogger('udiskie.mount.unlock_device')
    if not device.is_handleable or not device.is_crypto:
        log.debug('skipping unhandled device %s' % (device,))
        return False
    if device.is_unlocked:
        log.debug('skipping unlocked device %s' % (device,))
        return False

    # prompt user for password
    password = prompt and prompt(
            'Enter password for %s:' % (device,),
            'Unlock encrypted device')
    if password is None:
        return False

    # unlock device
    log.info('attempting to unlock device %s' % (device,))
    try:
        device.unlock(password, [])
        holder_dev = udiskie.device.Device(
                device.bus,
                device.luks_cleartext_holder)
        holder_path = holder_dev.device_file
        log.info('unlocked device %s on %s' % (device, holder_path))
    except dbus.exceptions.DBusException, dbus_err:
        log.error('failed to unlock device %s:\n%s'
                                    % (device, dbus_err))
        return None
    return True

def add_device(device, filter=None, prompt=None):
    """Mount or unlock the device depending on its type."""
    log = logging.getLogger('udiskie.mount.add_device')
    if not device.is_handleable:
        log.debug('skipping unhandled device %s' % (device,))
        return False
    if device.is_filesystem:
        return mount_device(device, filter)
    elif device.is_crypto:
        return unlock_device(device, prompt)

def mount_all(bus=None, filter=None, prompt=None):
    """Mount handleable devices that are already present."""
    bus = bus or dbus.SystemBus()
    for device in udiskie.device.get_all_handleable(bus):
        add_device(device, filter, prompt)


class Mounter:
    """
    Mount utility.

    Calls the global functions and remembers bus, filter and prompt.

    """
    def __init__(self, bus, filter=None, prompt=None):
        self.bus = bus or dbus.SystemBus()
        self.filter = filter
        self.prompt = prompt

    def mount_device(self, device, filter=None):
        return mount_device(device, filter=filter or self.filter)

    def unlock_device(self, device, prompt=None):
        return mount_device(device, filter=prompt or self.prompt)

    def add_device(self, device, filter=None, prompt=None):
        return add_device(
                device,
                filter=filter or self.filter, 
                prompt=prompt or self.prompt)

    def mount_all(self, filter=None, prompt=None):
        return mount_all(
                self.bus,
                filter=filter or self.filter,
                prompt=prompt or self.prompt)


