"""
Udiskie notification daemon.
"""
__all__ = ['Notify']

import pynotify
import gio

class Notify:
    """
    Notification tool.

    Can be connected to udisks daemon in order to automatically issue
    notifications when system status has changed.

    """
    def __init__(self, name):
        """Initialize notifier."""
        pynotify.init(name)

    def connect(self, daemon):
        """Connect to udisks daemon."""
        daemon.connect('device_mounted', self.mount)
        daemon.connect('device_unmounted', self.umount)
        daemon.connect('device_unlocked', self.unlock)
        daemon.connect('device_locked', self.lock)

    def disconnect(self, daemon):
        """Disconnect from udisks daemon."""
        daemon.disconnect('device_mounted', self.mount)
        daemon.disconnect('device_unmounted', self.umount)
        daemon.disconnect('device_unlocked', self.unlock)
        daemon.disconnect('device_locked', self.lock)

    # event handlers:
    def mount(self, device):
        try:
            device_file = device.device_file
            mount_path = device.mount_paths[0]
            pynotify.Notification('Device mounted',
                                  '%s mounted on %s' % (device_file, mount_path),
                                  'drive-removable-media').show()
        except gio.Error:
            pass

    def umount(self, device):
        try:
            device_file = device.device_file
            pynotify.Notification('Device unmounted',
                                  '%s unmounted' % (device_file,),
                                  'drive-removable-media').show()
        except gio.Error:
            pass

    def lock(self, device):
        try:
            device_file = device.device_file
            pynotify.Notification('Device locked',
                                  '%s locked' % (device_file,),
                                  'drive-removable-media').show()
        except gio.Error:
            pass

    def unlock(self, device):
        try:
            device_file = device.device_file
            pynotify.Notification('Device unlocked',
                                  '%s unlocked' % (device_file,),
                                  'drive-removable-media').show()
        except gio.Error:
            pass

