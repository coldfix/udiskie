"""
Udiskie mount utilities.
"""
__all__ = ['Mounter']

import logging
import os
import dbus

try:
    from xdg.BaseDirectory import xdg_config_home
except ImportError:
    xdg_config_home = os.path.expanduser('~/.config')

import udiskie.device
import udiskie.match

class Mounter:
    CONFIG_PATH = 'udiskie/filters.conf'

    def __init__(self, bus, filter_file=None, prompt=None):
        self.log = logging.getLogger('udiskie.mount.Mounter')
        self.bus = bus
        self.prompt = prompt

        if not filter_file:
            filter_file = os.path.join(xdg_config_home, self.CONFIG_PATH)
        self.filters = udiskie.match.FilterMatcher((filter_file,))

    def mount_device(self, device):
        """
        Mount the device if not already mounted.

        Return value indicates whether an action was performed successfully.
        The special value `None` means unknown/unreliable.

        """
        if not device.is_handleable or not device.is_filesystem:
            self.log.debug('skipping unhandled device %s' % (device,))
            return False
        if device.is_mounted:
            self.log.debug('skipping mounted device %s' % (device,))
            return False

        fstype = str(device.id_type)
        options = self.filters.get_mount_options(device)

        S = 'attempting to mount device %s (%s:%s)'
        self.log.info(S % (device, fstype, options))

        try:
            device.mount(fstype, options)
            self.log.info('mounted device %s' % (device,))
        except dbus.exceptions.DBusException, dbus_err:
            self.log.error('failed to mount device %s: %s' % (
                                                device, dbus_err))
            return None

        mount_paths = ', '.join(device.mount_paths)

        return True

    def unlock_device(self, device):
        """
        Unlock the device if not already unlocked.

        Return value indicates whether an action was performed successfully.
        The special value `None` means unknown/unreliable.

        """
        if not device.is_handleable or not device.is_crypto:
            self.log.debug('skipping unhandled device %s' % (device,))
            return False
        if device.is_unlocked:
            self.log.debug('skipping unlocked device %s' % (device,))
            return False

        # prompt user for password
        password = self.prompt and self.prompt(
                'Enter password for %s:' % (device,),
                'Unlock encrypted device')
        if password is None:
            return False

        # unlock device
        self.log.info('attempting to unlock device %s' % (device,))
        try:
            device.unlock(password, [])
            holder_dev = udiskie.device.Device(
                    self.bus,
                    device.luks_cleartext_holder)
            holder_path = holder_dev.device_file
            self.log.info('unlocked device %s on %s' % (device, holder_path))
        except dbus.exceptions.DBusException, dbus_err:
            self.log.error('failed to unlock device %s:\n%s'
                                        % (device, dbus_err))
            return None
        return True

    def add_device(self, device):
        """Mount or unlock the device depending on its type."""
        if not device.is_handleable:
            self.log.debug('skipping unhandled device %s' % (device,))
            return False
        if device.is_filesystem:
            return self.mount_device(device)
        elif device.is_crypto:
            return self.unlock_device(device)

    def mount_present_devices(self):
        """Mount handleable devices that are already present."""
        for device in udiskie.device.get_all_handleable(self.bus):
            self.add_device(device)


