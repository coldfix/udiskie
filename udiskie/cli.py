"""
Udiskie CLI logic.
"""
__all__ = [
    # entry points:
    'daemon',
    'mount',
    'umount',
]

import warnings
warnings.filterwarnings("ignore", ".*could not open display.*", Warning)
warnings.filterwarnings("ignore", ".*g_object_unref.*", Warning)

import os, sys
import logging
from functools import partial

CONFIG_PATH = 'udiskie/filters.conf'

#----------------------------------------
# Utility functions
#----------------------------------------
def load_filter(filter_file=None):
    """Load mount option filters."""
    import udiskie.match
    if not filter_file:
        try:
            from xdg.BaseDirectory import xdg_config_home
        except ImportError:
            xdg_config_home = os.path.expanduser('~/.config')
        filter_file = os.path.join(xdg_config_home, CONFIG_PATH)
    return udiskie.match.FilterMatcher.from_config_file(filter_file)

def common_program_options():
    """
    Return a command line option parser for options common to all modes.
    """
    import optparse
    parser = optparse.OptionParser()
    parser.add_option('-v', '--verbose', action='store_const',
                      dest='log_level', default=logging.INFO,
                      const=logging.DEBUG, help='verbose output')
    parser.add_option('-1', '--use-udisks1', action='store_const',
                      dest='udisks_version', default=0,
                      const=1, help='use udisks1 as underlying daemon (default)')
    parser.add_option('-2', '--use-udisks2', action='store_const',
                      dest='udisks_version', default=0,
                      const=2, help='use udisks2 as underlying daemon (experimental)')
    return parser

def mount_program_options():
    """
    Return the mount option parser for the mount command.
    """
    parser = common_program_options()
    parser.add_option('-f', '--filters', action='store',
                      dest='filters', default=None,
                      metavar='FILE', help='filter FILE')
    parser.add_option('-P', '--password-prompt', action='store',
                      dest='password_prompt', default='zenity',
                      metavar='MODULE', help="replace password prompt")
    return parser


def udisks_service_object(clsname, version=0):
    """
    Return UDisks service.

    :param int version: requested udisks
    :param dbus.mainloop.NativeMainLoop mainloop: event loop for system bus
    :return: udisks service wrapper object
    :raises dbus.DBusException: if unable to connect to UDisks dbus service.
    :raises ValueError: if the version is invalid

    If ``version is None``, try to connect to UDisks1 and fall back to
    UDisks2 if not available.

    If ``mainloop is True``, use the default (only) mainloop provided by
    dbus-python.

    """
    def udisks1():
        import udiskie.udisks1
        return getattr(udiskie.udisks1, clsname).create()
    def udisks2():
        import udiskie.udisks2
        return getattr(udiskie.udisks2, clsname).create()
    if version == 0:
        from udiskie.common import DBusException
        try:
            return udisks1()
        except DBusException:
            msg = sys.exc_info()[1].get_dbus_message()
            logging.getLogger().warning(
                ('Failed to connect UDisks1 dbus service: %s.\n' +
                 'Falling back to UDisks2 [experimental].') % (msg,))
            return udisks2()
    elif version == 1:
        return udisks1()
    elif version == 2:
        return udisks2()
    else:
        raise ValueError("UDisks version not supported: %s!" % (version,))


#----------------------------------------
# Entry points
#----------------------------------------
def daemon(args=None, daemon=None):
    """
    Execute udiskie as a daemon.
    """
    import gobject
    import udiskie.automount
    import udiskie.mount
    import udiskie.prompt

    parser = mount_program_options()
    parser.add_option('-s', '--suppress', action='store_true',
                      dest='suppress_notify', default=False,
                      help='suppress popup notifications')
    parser.add_option('-t', '--tray', action='store_true',
                      dest='tray', default=False,
                      help='show tray icon')
    options, posargs = parser.parse_args(args)
    logging.basicConfig(level=options.log_level, format='%(message)s')

    mainloop = gobject.MainLoop()

    # connect udisks
    if daemon is None:
        daemon = udisks_service_object('Daemon', options.udisks_version)

    # create a mounter
    prompt = udiskie.prompt.password(options.password_prompt)
    filter = load_filter(options.filters)
    mounter = udiskie.mount.Mounter(filter=filter, prompt=prompt, udisks=daemon)

    # notifications (optional):
    if not options.suppress_notify:
        import udiskie.notify
        try:
            import notify2 as notify_service
        except ImportError:
            import pynotify as notify_service
        notify_service.init('udiskie.mount')
        notify = udiskie.notify.Notify(notify_service)
        daemon.connect(notify)

    # tray icon (optional):
    if options.tray:
        import udiskie.tray
        create_menu = partial(udiskie.tray.create_menu,
                              udisks=daemon,
                              mounter=mounter,
                              actions={'quit': mainloop.quit})
        statusicon = udiskie.tray.create_statusicon()
        connection = udiskie.tray.connect_statusicon(statusicon, create_menu)

    # automounter
    automount = udiskie.automount.AutoMounter(mounter)
    daemon.connect(automount)

    mounter.mount_all()
    try:
        return mainloop.run()
    except KeyboardInterrupt:
        return 0

def mount(args=None, udisks=None):
    """
    Execute the mount command.
    """
    import udiskie.mount
    import udiskie.prompt

    parser = mount_program_options()
    parser.add_option('-a', '--all', action='store_true',
                      dest='all', default=False,
                      help='mount all present devices')
    parser.add_option('-r', '--recursive', action='store_true',
                      dest='recursive', default=False,
                      help='recursively mount LUKS partitions (if the automount daemon is running, this is not necessary)')
    options, posargs = parser.parse_args(args)
    logging.basicConfig(level=options.log_level, format='%(message)s')

    # connect udisks
    if udisks is None:
        udisks = udisks_service_object('Sniffer', options.udisks_version)

    # create a mounter
    prompt = udiskie.prompt.password(options.password_prompt)
    filter = load_filter(options.filters)
    mounter = udiskie.mount.Mounter(filter=filter, prompt=prompt, udisks=udisks)

    # mount all present devices
    if options.all:
        success = mounter.mount_all(recursive=options.recursive)

    # only mount the desired devices
    elif len(posargs) > 0:
        success = True
        for path in posargs:
            success = success and mounter.mount(path, recursive=options.recursive)

    # print command line options
    else:
        parser.print_usage()
        success = False

    return 0 if success else 1

def umount(args=None, udisks=None):
    """
    Execute the umount command.
    """
    import udiskie.mount

    parser = common_program_options()
    parser.add_option('-a', '--all', action='store_true',
                      dest='all', default=False,
                      help='all devices')
    parser.add_option('-e', '--eject', action='store_true',
                      dest='eject', default=False,
                      help='Eject drive')
    parser.add_option('-d', '--detach', action='store_true',
                      dest='detach', default=False,
                      help='Detach drive')
    (options, posargs) = parser.parse_args(args)
    logging.basicConfig(level=options.log_level, format='%(message)s')

    if udisks is None:
        udisks = udisks_service_object('Sniffer', options.udisks_version)
    mounter = udiskie.mount.Mounter(udisks=udisks)

    if options.all:
        success = mounter.unmount_all(detach=options.detach,
                                      eject=options.eject,
                                      lock=True)
    elif len(posargs) > 0:
        success = True
        for path in posargs:
            success = (success and
                       mounter.unmount(path, detach=options.detach,
                                       eject=options.eject, lock=True))
    else:
        parser.print_usage()
        success = False

    return 0 if success else 1

