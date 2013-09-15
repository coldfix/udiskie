"""
Udiskie CLI logic.
"""
__all__ = [
    'load_filter',
    'mount_program_options', 'mount',
    'umount_program_options', 'umount']

import warnings
warnings.filterwarnings("ignore", ".*could not open display.*", Warning)
warnings.filterwarnings("ignore", ".*g_object_unref.*", Warning)

import os
import logging
import dbus

import udiskie.match
import udiskie.mount
import udiskie.prompt
import udiskie.notify
import udiskie.automount
import udiskie.daemon
import udiskie.common


CONFIG_PATH = 'udiskie/filters.conf'

def load_filter(filter_file=None):
    """Load mount option filters."""
    try:
        from xdg.BaseDirectory import xdg_config_home
    except ImportError:
        xdg_config_home = os.path.expanduser('~/.config')
    if not filter_file:
        filter_file = os.path.join(xdg_config_home, CONFIG_PATH)
    return udiskie.match.FilterMatcher((filter_file,))


def mount_program_options():
    """
    Return the mount option parser for the mount command.
    """
    import optparse
    parser = optparse.OptionParser()
    parser.add_option('-a', '--all', action='store_true',
                      dest='all', default=False,
                      help='mount all present devices')
    parser.add_option('-v', '--verbose', action='store_const',
                      dest='log_level', default=logging.INFO,
                      const=logging.DEBUG, help='verbose output')
    parser.add_option('-f', '--filters', action='store',
                      dest='filters', default=None,
                      metavar='FILE', help='filter FILE')
    parser.add_option('-s', '--suppress', action='store_true',
                      dest='suppress_notify', default=False,
                      help='suppress popup notifications')
    parser.add_option('-P', '--password-prompt', action='store',
                      dest='password_prompt', default='zenity',
                      metavar='MODULE', help="replace password prompt")
    return parser


def mount(args, allow_daemon=False):
    """
    Execute the mount/daemon command.
    """
    parser = mount_program_options()
    options, posargs = parser.parse_args(args)
    logging.basicConfig(level=options.log_level, format='%(message)s')
    run_daemon = allow_daemon and not options.all and len(posargs) == 0

    # establish connection to system bus
    if run_daemon:
        from dbus.mainloop.glib import DBusGMainLoop
        DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    # for now: just use the default udisks
    udisks = udiskie.common.get_udisks()

    # create a mounter
    prompt = udiskie.prompt.password(options.password_prompt)
    filter = load_filter(options.filters)
    mounter = udiskie.mount.Mounter(bus=bus, filter=filter, prompt=prompt, udisks=udisks)

    # run udiskie daemon if needed
    if run_daemon:
        daemon = udiskie.daemon.Daemon(bus, udisks=udisks)
    if run_daemon and not options.suppress_notify:
        notify = udiskie.notify.Notify('udiskie.mount')
        daemon.connect(notify)
    if run_daemon:
        automount = udiskie.automount.AutoMounter(mounter)
        daemon.connect(automount)

    # mount all present devices
    if options.all:
        mounter.mount_all()

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

    # run in daemon mode
    elif run_daemon:
        mounter.mount_all()
        try:
            return daemon.run()
        except KeyboardInterrupt:
            pass

    # print command line options
    else:
        parser.print_usage()
        return 1


def umount_program_options():
    """
    Return the command line option parser for the umount command.
    """
    import optparse
    parser = optparse.OptionParser()
    parser.add_option('-a', '--all', action='store_true',
                      dest='all', default=False,
                      help='all devices')
    parser.add_option('-v', '--verbose', action='store_const',
                      dest='log_level', default=logging.INFO,
                      const=logging.DEBUG, help='verbose output')
    parser.add_option('-s', '--suppress', action='store_true',
                      dest='suppress_notify', default=False,
                      help='suppress popup notifications')
    return parser


def umount(args):
    """
    Execute the umount command.
    """
    parser = umount_program_options()
    (options, posargs) = parser.parse_args(args)
    logging.basicConfig(level=options.log_level, format='%(message)s')
    bus = dbus.SystemBus()

    if len(posargs) == 0 and not options.all:
        parser.print_usage()
        return 1

    # for now: use udisks v1 service
    udisks = udiskie.common.get_udisks()

    if options.all:
        unmounted = udiskie.mount.unmount_all(bus=bus, udisks=udisks)
    else:
        unmounted = []
        for path in posargs:
            device = udiskie.mount.unmount(os.path.normpath(path), bus=bus, udisks=udisks)
            if device:
                unmounted.append(device)

    # automatically lock unused luks slaves of unmounted devices
    for device in unmounted:
        udiskie.mount.lock_slave(device, udisks=udisks)

