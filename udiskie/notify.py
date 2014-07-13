"""
Notification utility.
"""

import logging
import sys

from udiskie.dbus import DBusException
from udiskie.locale import _


__all__ = ['Notify']


class Notify(object):

    """
    Notification tool.

    Can be connected to udisks daemon in order to automatically issue
    notifications when system status has changed.

    NOTE: the action buttons in the notifications don't work with all
    notification services.
    """

    def __init__(self, notify, mounter, timeout=None):
        """
        Initialize notifier and connect to service.

        :param notify: notification service module (pynotify or notify2)
        :param mounter: Mounter object
        :param dict timeout: timeouts
        """
        self._notify = notify
        self._mounter = mounter
        self._timeout = timeout or {}
        self._default = self._timeout.get('timeout', -1)
        self._log = logging.getLogger(__name__)
        self._notifications = []
        # Subscribe all enabled events to the daemon:
        udisks = mounter.udisks
        for event in ['device_mounted', 'device_unmounted',
                      'device_locked', 'device_unlocked',
                      'device_added', 'device_removed',
                      'job_failed']:
            if self._enabled(event):
                udisks.connect(event, getattr(self, event))

    # event handlers:
    def device_mounted(self, device):
        """
        Show 'Device mounted' notification with 'Browse directory' button.

        :param device: device object
        """
        label = device.id_label
        mount_path = device.mount_paths[0]
        browse_action = ('browse', _('Browse directory'),
                         self._mounter.browse, device)
        self._show_notification(
            'device_mounted',
            _('Device mounted'),
            _('{0.id_label} mounted on {0.mount_paths[0]}', device),
            'drive-removable-media',
            self._mounter._browser and browse_action)

    def device_unmounted(self, device):
        """
        Show 'Device unmounted' notification.

        :param device: device object
        """
        label = device.id_label
        self._show_notification(
            'device_unmounted',
            _('Device unmounted'),
            _('{0.id_label} unmounted', device),
            'drive-removable-media')

    def device_locked(self, device):
        """
        Show 'Device locked' notification.

        :param device: device object
        """
        device_file = device.device_presentation
        self._show_notification(
            'device_locked',
            _('Device locked'),
            _('{0.device_presentation} locked', device),
            'drive-removable-media')

    def device_unlocked(self, device):
        """
        Show 'Device unlocked' notification.

        :param device: device object
        """
        device_file = device.device_presentation
        self._show_notification(
            'device_unlocked',
            _('Device unlocked'),
            _('{0.device_presentation} unlocked', device),
            'drive-removable-media')

    def device_added(self, device):
        """
        Show 'Device added' notification.

        :param device: device object
        """
        device_file = device.device_presentation
        if (device.is_drive or device.is_toplevel) and device_file:
            self._show_notification(
                'device_added',
                _('Device added'),
                _('device appeared on {0.device_presentation}', device),
                'drive-removable-media')

    def device_removed(self, device):
        """
        Show 'Device removed' notification.

        :param device: device object
        """
        device_file = device.device_presentation
        if (device.is_drive or device.is_toplevel) and device_file:
            self._show_notification(
                'device_removed',
                _('Device removed'),
                _('device disappeared on {0.device_presentation}', device),
                'drive-removable-media')

    def job_failed(self, device, action, message):
        """
        Show 'Job failed' notification with 'Retry' button.

        :param device: device object
        """
        device_file = device.device_presentation or device.object_path
        if message:
            text = _('failed to {0} {1}:\n{2}', action, device_file, message)
        else:
            text = _('failed to {0} device {1}.', action, device_file)
        try:
            retry = getattr(self._mounter, action)
        except AttributeError:
            retry_action = None
        else:
            retry_action = ('retry', _('Retry'), retry, device)
        self._show_notification(
            'job_failed',
            _('Job failed'), text,
            'drive-removable-media',
            retry_action)

    def _show_notification(self,
                           event, summary, message, icon,
                           action=None):
        """
        Show a notification.

        :param str event: event name
        :param str summary: notification title
        :param str message: notification body
        :param str icon: icon name
        :param dict action: parameters to :meth:`_add_action`
        """
        notification = self._notify(summary, message, icon)
        timeout = self._get_timeout(event)
        if timeout != -1:
            notification.set_timeout(int(timeout * 1000))
        if action:
            self._add_action(notification, *action)
        try:
            notification.show()
        except DBusException:
            # Catch and log the exception. Starting udiskie with notifications
            # enabled while not having a notification service installed is a
            # mistake too easy to be made, but it shoud not render the rest of
            # udiskie's logic useless by raising an exception before the
            # automount handler gets invoked.
            exc = sys.exc_info()[1]
            self._log.error("Failed to show notification: {0}"
                            .format(exc.message))

    def _add_action(self, notification, action, label, callback, *args):
        """
        Show an action button button in mount notifications.

        Note, this only works with some libnotify services.
        """
        def on_action_click(notification, action):
            callback(*args)
        notification.add_action(action, label, on_action_click)
        # pynotify does not store hard references to the notification
        # objects. When a signal is received and the notification does not
        # exist anymore, no handller will be called. Therefore, we need to
        # prevent these notifications from being destroyed by storing
        # references (note, notify2 doesn't need this):
        notification.connect('closed', self._notifications.remove)
        self._notifications.append(notification)

    def _enabled(self, event):
        """
        Check if the notification for an event is enabled.

        :param str event: event name
        :returns: if the event notification is enabled
        :rtype: bool
        """
        return self._get_timeout(event) not in (None, False)

    def _get_timeout(self, event):
        """
        Get the timeout for an event from the config.

        :param str event: event name
        :returns: timeout in seconds
        :rtype: int, float or NoneType
        """
        return self._timeout.get(event, self._default)
