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

import os
import logging

import udiskie.match
import udiskie.mount
import udiskie.prompt
import udiskie.notify
import udiskie.automount
import udiskie.daemon

CONFIG_PATH = 'udiskie/filters.conf'


#----------------------------------------
# Utility functions
#----------------------------------------
def load_filter(filter_file=None):
    """Load mount option filters."""
    if not filter_file:
        try:
            from xdg.BaseDirectory import xdg_config_home
        except ImportError:
            xdg_config_home = os.path.expanduser('~/.config')
        filter_file = os.path.join(xdg_config_home, CONFIG_PATH)
    return udiskie.match.FilterMatcher((filter_file,))

def common_program_options():
    """
    Return a command line option parser for options common to all modes.
    """
    import optparse
    parser = optparse.OptionParser()
    parser.add_option('-v', '--verbose', action='store_const',
                      dest='log_level', default=logging.INFO,
                      const=logging.DEBUG, help='verbose output')
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

def connect_udisks(bus):
    """
    Return a connection to the first udisks service found available.

    TODO: This should check if the udisks service is accessible and if not
    try to connect to udisks2 service.

    """
    import udiskie.udisks
    return udiskie.udisks.Udisks.create(bus)


#----------------------------------------
# Entry points
#----------------------------------------
def daemon(args=None, udisks=None):
    """
    Execute udiskie as a daemon.
    """
    parser = mount_program_options()
    parser.add_option('-s', '--suppress', action='store_true',
                      dest='suppress_notify', default=False,
                      help='suppress popup notifications')
    options, posargs = parser.parse_args(args)
    logging.basicConfig(level=options.log_level, format='%(message)s')

    # establish connection to system bus
    from dbus.mainloop.glib import DBusGMainLoop
    import gobject
    DBusGMainLoop(set_as_default=True)

    # for now: just use the default udisks
    if udisks is None:
        import dbus
        bus = dbus.SystemBus()
        udisks = connect_udisks(bus)

    # create a mounter
    prompt = udiskie.prompt.password(options.password_prompt)
    filter = load_filter(options.filters)
    mounter = udiskie.mount.Mounter(filter=filter, prompt=prompt, udisks=udisks)

    # run udiskie daemon if needed
    daemon = udiskie.daemon.Daemon(udisks=udisks)
    if not options.suppress_notify:
        try:
            import notify2 as notify_service
        except ImportError:
            import pynotify as notify_service
        notify_service.init('udiskie.mount')
        notify = udiskie.notify.Notify(notify_service)
        daemon.connect(notify)
    automount = udiskie.automount.AutoMounter(mounter)
    daemon.connect(automount)

    mounter.mount_all()
    try:
        return gobject.MainLoop().run()
    except KeyboardInterrupt:
        return 0

def mount(args=None, udisks=None):
    """
    Execute the mount command.
    """
    parser = mount_program_options()
    parser.add_option('-a', '--all', action='store_true',
                      dest='all', default=False,
                      help='mount all present devices')
    options, posargs = parser.parse_args(args)
    logging.basicConfig(level=options.log_level, format='%(message)s')

    # for now: just use the default udisks
    if udisks is None:
        import dbus
        bus = dbus.SystemBus()
        udisks = connect_udisks(bus)

    # create a mounter
    prompt = udiskie.prompt.password(options.password_prompt)
    filter = load_filter(options.filters)
    mounter = udiskie.mount.Mounter(filter=filter, prompt=prompt, udisks=udisks)

    # mount all present devices
    if options.all:
        mounter.mount_all()
        return 0

    # only mount the desired devices
    elif len(posargs) > 0:
        mounted = []
        for path in posargs:
            device = mounter.mount(path)
            if device:
                mounted.append(device)
        # automatically mount luks holders
        for device in mounted:
            mounter.mount_holder(device)
        return 0

    # print command line options
    else:
        parser.print_usage()
        return 1

def umount(args=None, udisks=None):
    """
    Execute the umount command.
    """
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

    if len(posargs) == 0 and not options.all:
        parser.print_usage()
        return 1

    # for now: use udisks v1 service
    if udisks is None:
        import dbus
        bus = dbus.SystemBus()
        udisks = connect_udisks(bus)
    mounter = udiskie.mount.Mounter(udisks=udisks)

    unmounted = []
    if options.all:
        if options.eject or options.detach:
            if options.eject:
                mounter.eject_all()
            if options.detach:
                mounter.detach_all()
        else:
            unmounted = mounter.unmount_all()
    else:
        unmounted = []
        for path in posargs:
            if options.eject or options.detach:
                path = os.path.normpath(path)
                if options.eject:
                    mounter.eject(path)
                if options.detach:
                    mounter.detach(path)
            else:
                device = mounter.unmount(os.path.normpath(path))
                if device:
                    unmounted.append(device)

    # automatically lock unused luks slaves of unmounted devices
    for device in unmounted:
        mounter.lock_slave(device)
    return 0

