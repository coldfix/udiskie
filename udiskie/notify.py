"""
Udiskie notification daemon.
"""
__all__ = ['Notify']

import pynotify
import gio

class Notify(object):
    """
    Notification tool.

    Can be connected to udisks daemon in order to automatically issue
    notifications when system status has changed.

    """
    def __init__(self, name):
        """Initialize notifier."""
        pynotify.init(name)

    # event handlers:
    def device_mounted(self, device):
        try:
            device_file = device.device_file
            mount_path = device.mount_paths[0]
            pynotify.Notification('Device mounted',
                                  '%s mounted on %s' % (device_file, mount_path),
                                  'drive-removable-media').show()
        except gio.Error:
            pass

    def device_unmounted(self, device):
        try:
            device_file = device.device_file
            pynotify.Notification('Device unmounted',
                                  '%s unmounted' % (device_file,),
                                  'drive-removable-media').show()
        except gio.Error:
            pass

    def device_locked(self, device):
        try:
            device_file = device.device_file
            pynotify.Notification('Device locked',
                                  '%s locked' % (device_file,),
                                  'drive-removable-media').show()
        except gio.Error:
            pass

    def device_unlocked(self, device):
        try:
            device_file = device.device_file
            pynotify.Notification('Device unlocked',
                                  '%s unlocked' % (device_file,),
                                  'drive-removable-media').show()
        except gio.Error:
            pass

