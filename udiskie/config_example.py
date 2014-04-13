"""
This is an example configuration file.
"""
from collections import defaultdict

from udiskie.config import *


config = Config(
    # set fallbacks for program options:
    udisks_version=1,                           # set UDisks version
    password_prompt='zenity',                   # set the password program
    tray='TrayIcon',                            # default tray class
    automount=False,                            # disable automounting
    suppress_notify=True,                       # show notifications
    file_manager='xdg-open',                    # set file manager

    # add mount options for specific devices, note that just the first
    # matching filter will be used
    mount_option_filter = FilterMatcher(
        OptionFilter('id_uuid', 'abcd-ef00', ['ro', 'noexec']),
        OptionFilter('id_uuid', 'abcd-ef01', ['__ignore__']),
        # lesser filters (id_type) shoud be sorted below more specific
        # filters (id_uuid), order matters:
        OptionFilter('id_type', 'vfat', ['nosync']),
    ),

    # set timeouts for notifications:
    notification_timeouts = defaultdict(
        # number > 0    timeout in seconds 
        # -1            use libnotify default
        # False, None   disable notification
        lambda: 5,                              # fallback value
        device_mounted=3,                       # filesystem is mounted
        device_unmounted=3,                     # filesystem is unmounted
        device_added=False,                     # drive appeared
        device_removed=False,                   # drive disappeared
        device_unlocked=-1,                     # LUKS partition is unlocked
        device_locked=1.5,                      # LUKS partition is locked
    )
)
