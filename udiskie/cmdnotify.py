import subprocess
import logging


class CommandHandler:
    """
    An event handler that issues a command.
    """

    _properties = [
        "device_file",
        "device_id",
        "device_size",
        "drive",
        "drive_label",
        "id_label",
        "id_type",
        "id_usage",
        "id_uuid",
        "mount_path",
        "root",
    ]
    
    def __init__(self, command_format, event):
        """
        Initialize command handler.

        :param command_format: The command format string to run when the
                               particular event occurs.
        :param event: The event type
        """
        self._log = logging.getLogger(__name__)
        self._command_format = command_format
        self._event = event

    def __call__(self, device):
        event_info = dict([(prop_name, getattr(device, prop_name)) for prop_name in self._properties])
        event_info["event"] = self._event
        command = self._command_format.format(**event_info)
        return_code = subprocess.call(command, shell = True)
        if (return_code != 0):
            self._log.warn("Notification command {} with event {} returned {:d}".format(command, self._event, return_code))


class CommandNotify:

    """
    Command notification tool.

    This works similar to Notify, but will issue command instead of showing
    the notifications on the desktop. This can then be used to react to events
    from shell scripts.

    The command can contain modern pythonic format placeholders like:
    {device_file}. The following placeholders are supported:
    event, device_file, device_id, device_size, drive, drive_label, id_label,
    id_type, id_usage, id_uuid, mount_path, root
    """

    def __init__(self, command_format, mounter):
        """
        Initialize notifier and connect to service.

        :param command_format: The command format string to run when an event
                               occurs.
        :param mounter: Mounter object
        """
        udisks = mounter.udisks
        # Subscribe all enabled events to the daemon:
        udisks = mounter.udisks
        for event in ['device_mounted', 'device_unmounted',
                      'device_locked', 'device_unlocked',
                      'device_added', 'device_removed',
                      'job_failed']:
            udisks.connect(event, CommandHandler(command_format, event))

    
