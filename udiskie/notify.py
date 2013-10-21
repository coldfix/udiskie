"""
Udiskie notification daemon.
"""
__all__ = ['Notify']

class Notify(object):
    """
    Notification tool.

    Can be connected to udisks daemon in order to automatically issue
    notifications when system status has changed.

    """
    def __init__(self, notify):
        """
        Initialize notifier.

        A notify service such as pynotify or notify2 should be passed in.

        """
        self.notify = notify

    # event handlers:
    def device_mounted(self, device):
        device_file = device.device_presentation
        mount_path = device.mount_paths[0]
        self.notify.Notification(
            'Device mounted',
            '%s mounted on %s' % (device_file, mount_path),
            'drive-removable-media').show()

    def device_unmounted(self, device):
        device_file = device.device_presentation
        self.notify.Notification(
            'Device unmounted',
            '%s unmounted' % (device_file,),
            'drive-removable-media').show()

    def device_locked(self, device):
        device_file = device.device_presentation
        self.notify.Notification(
            'Device locked',
            '%s locked' % (device_file,),
            'drive-removable-media').show()

    def device_unlocked(self, device):
        device_file = device.device_presentation
        self.notify.Notification(
            'Device unlocked',
            '%s unlocked' % (device_file,),
            'drive-removable-media').show()

