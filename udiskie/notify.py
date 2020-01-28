"""
Notification utility.
"""

import logging

from gi.repository import GLib

from .async_ import run_bg
from .common import exc_message, DaemonBase, format_exc
from .mount import DeviceActions
from .locale import _


__all__ = ['Notify']


class Notify(DaemonBase):

    """
    Notification tool.

    Can be connected to udisks daemon in order to automatically issue
    notifications when system status has changed.

    NOTE: the action buttons in the notifications don't work with all
    notification services.
    """

    EVENTS = ['device_mounted', 'device_unmounted',
              'device_locked', 'device_unlocked',
              'device_added', 'device_removed',
              'job_failed']

    def __init__(self, notify, mounter, timeout=None, aconfig=None):
        """
        Initialize notifier and connect to service.

        :param notify: notification service module (gi.repository.Notify)
        :param mounter: Mounter object
        :param dict timeout: dictionary with timeouts for notifications
        """
        self._notify = notify
        self._mounter = mounter
        self._actions = DeviceActions(mounter)
        self._timeout = timeout or {}
        self._aconfig = aconfig or {}
        self._default = self._timeout.get('timeout', -1)
        self._log = logging.getLogger(__name__)
        self._notifications = []
        self.events = {
            event: getattr(self, event)
            for event in self.EVENTS
            if self._enabled(event)
        }

    # event handlers:
    def device_mounted(self, device):
        """Show mount notification for specified device object."""
        if not self._mounter.is_handleable(device):
            return
        browse_action = ('browse', _('Browse directory'),
                         self._mounter.browse, device)
        terminal_action = ('terminal', _('Open terminal'),
                           self._mounter.terminal, device)
        self._show_notification(
            'device_mounted',
            _('Device mounted'),
            _('{0.ui_label} mounted on {0.mount_paths[0]}', device),
            device.icon_name,
            self._mounter._browser and browse_action,
            self._mounter._terminal and terminal_action)

    def device_unmounted(self, device):
        """Show unmount notification for specified device object."""
        if not self._mounter.is_handleable(device):
            return
        self._show_notification(
            'device_unmounted',
            _('Device unmounted'),
            _('{0.ui_label} unmounted', device),
            device.icon_name)

    def device_locked(self, device):
        """Show lock notification for specified device object."""
        if not self._mounter.is_handleable(device):
            return
        self._show_notification(
            'device_locked',
            _('Device locked'),
            _('{0.device_presentation} locked', device),
            device.icon_name)

    def device_unlocked(self, device):
        """Show unlock notification for specified device object."""
        if not self._mounter.is_handleable(device):
            return
        self._show_notification(
            'device_unlocked',
            _('Device unlocked'),
            _('{0.device_presentation} unlocked', device),
            device.icon_name)

    def device_added(self, device):
        """Show discovery notification for specified device object."""
        if not self._mounter.is_handleable(device):
            return
        if self._has_actions('device_added'):
            # wait for partitions etc to be reported to udiskie, otherwise we
            # can't discover the actions
            GLib.timeout_add(500, self._device_added, device)
        else:
            self._device_added(device)

    def _device_added(self, device):
        device_file = device.device_presentation
        if (device.is_drive or device.is_toplevel) and device_file:
            # On UDisks1: cannot invoke self._actions.detect() for newly added
            # LUKS devices. It should be okay if we had waited for the actions
            # to be added, though.
            if self._has_actions('device_added'):
                node_tree = self._actions.detect(device.object_path)
                flat_actions = self._flatten_node(node_tree)
                actions = [
                    (action.method,
                     action.label.format(action.device.ui_label),
                     action.action)
                    for action in flat_actions
                ]
            else:
                actions = ()
            self._show_notification(
                'device_added',
                _('Device added'),
                _('device appeared on {0.device_presentation}', device),
                device.icon_name,
                *actions)

    def _flatten_node(self, node):
        actions = [action
                   for branch in node.branches
                   for action in self._flatten_node(branch)]
        actions += node.methods
        return actions

    def device_removed(self, device):
        """Show removal notification for specified device object."""
        if not self._mounter.is_handleable(device):
            return
        device_file = device.device_presentation
        if (device.is_drive or device.is_toplevel) and device_file:
            self._show_notification(
                'device_removed',
                _('Device removed'),
                _('device disappeared on {0.device_presentation}', device),
                device.icon_name)

    def job_failed(self, device, action, message):
        """Show 'Job failed' notification with 'Retry' button."""
        if not self._mounter.is_handleable(device):
            return
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
            device.icon_name,
            retry_action)

    def _show_notification(self,
                           event, summary, message, icon,
                           *actions):
        """
        Show a notification.

        :param str event: event name
        :param str summary: notification title
        :param str message: notification body
        :param str icon: icon name
        :param actions: each item is a tuple with parameters for _add_action
        """
        notification = self._notify(summary, message, icon)
        timeout = self._get_timeout(event)
        if timeout != -1:
            notification.set_timeout(int(timeout * 1000))
        for action in actions:
            if action and self._action_enabled(event, action[0]):
                self._add_action(notification, *action)
        try:
            notification.show()
        except GLib.GError as exc:
            # Catch and log the exception. Starting udiskie with notifications
            # enabled while not having a notification service installed is a
            # mistake too easy to be made, but it should not render the rest of
            # udiskie's logic useless by raising an exception before the
            # automount handler gets invoked.
            self._log.error(_("Failed to show notification: {0}", exc_message(exc)))
            self._log.debug(format_exc())

    def _add_action(self, notification, action, label, callback, *args):
        """
        Show an action button button in mount notifications.

        Note, this only works with some libnotify services.
        """
        on_action_click = run_bg(lambda *_: callback(*args))
        try:
            # this is the correct signature for Notify-0.7, the last argument
            # being 'user_data':
            notification.add_action(action, label, on_action_click, None)
        except TypeError:
            # this is the signature for some older version, I don't know what
            # the last argument is for.
            notification.add_action(action, label, on_action_click, None, None)
        # gi.Notify does not store hard references to the notification
        # objects. When a signal is received and the notification does not
        # exist anymore, no handler will be called. Therefore, we need to
        # prevent these notifications from being destroyed by storing
        # references:
        notification.connect('closed', self._notifications.remove)
        self._notifications.append(notification)

    def _enabled(self, event):
        """Check if the notification for an event is enabled."""
        return self._get_timeout(event) not in (None, False)

    def _get_timeout(self, event):
        """Get the timeout for an event from the config or None."""
        return self._timeout.get(event, self._default)

    def _action_enabled(self, event, action):
        """Check if an action for a notification is enabled."""
        event_actions = self._aconfig.get(event)
        if event_actions is None:
            return True
        if event_actions is False:
            return False
        return action in event_actions

    def _has_actions(self, event):
        """Check if a notification type has any enabled actions."""
        event_actions = self._aconfig.get(event)
        return event_actions is None or bool(event_actions)
