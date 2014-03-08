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
    def __init__(self, notify, browser=None):
        """
        Initialize notifier.

        A notify service such as pynotify or notify2 should be passed in.

        """
        self._notify = notify
        self._browser = browser
        # pynotify does not store hard references to the notification
        # objects. When a signal is received and the notification does not
        # exist anymore, no handller will be called. Therefore, we need to
        # prevent these notifications from being destroyed by storing
        # references (note, notify2 doesn't need this):
        self._notifications = []

    # event handlers:
    def device_mounted(self, device):
        label = device.id_label
        mount_path = device.mount_paths[0]
        notification = self._notify.Notification(
            'Device mounted',
            '%s mounted on %s' % (label, mount_path),
            'drive-removable-media')
        if self._browser:
            # Show a 'Browse directory' button in mount notifications.
            # Note, this only works with some libnotify services.
            def on_browse(notification, action):
                self._browser(mount_path)
            notification.add_action('browse', "Browse directory", on_browse)
            # Need to store a reference (see above) only if there is a
            # signal connected:
            notification.connect('closed', self._notifications.remove)
            self._notifications.append(notification)
        notification.show()

    def device_unmounted(self, device):
        label = device.id_label
        self._notify.Notification(
            'Device unmounted',
            '%s unmounted' % (label,),
            'drive-removable-media').show()

    def device_locked(self, device):
        device_file = device.device_presentation
        self._notify.Notification(
            'Device locked',
            '%s locked' % (device_file,),
            'drive-removable-media').show()

    def device_unlocked(self, device):
        device_file = device.device_presentation
        self._notify.Notification(
            'Device unlocked',
            '%s unlocked' % (device_file,),
            'drive-removable-media').show()

