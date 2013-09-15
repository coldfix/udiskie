"""
Udiskie mount utilities.
"""
__all__ = ['Mounter', 'option_parser', 'cli']

import warnings
warnings.filterwarnings("ignore", ".*could not open display.*", Warning)
warnings.filterwarnings("ignore", ".*g_object_unref.*", Warning)

import logging
import os
import dbus

try:
    from xdg.BaseDirectory import xdg_config_home
except ImportError:
    xdg_config_home = os.path.expanduser('~/.config')

import udiskie.device
import udiskie.match
import udiskie.prompt
import udiskie.notify
import udiskie.automount
import udiskie.daemon

class Mounter:
    CONFIG_PATH = 'udiskie/filters.conf'

    def __init__(self, bus, filter_file=None, prompt=None):
        self.log = logging.getLogger('udiskie.mount.Mounter')
        self.bus = bus
        self.prompt = prompt

        if not filter_file:
            filter_file = os.path.join(xdg_config_home, self.CONFIG_PATH)
        self.filters = udiskie.match.FilterMatcher((filter_file,))

    def mount_device(self, device):
        """
        Mount the device if not already mounted.

        Return value indicates whether an action was performed successfully.
        The special value `None` means unknown/unreliable.

        """
        if not device.is_handleable or not device.is_filesystem:
            self.log.debug('skipping unhandled device %s' % (device,))
            return False
        if device.is_mounted:
            self.log.debug('skipping mounted device %s' % (device,))
            return False

        fstype = str(device.id_type)
        options = self.filters.get_mount_options(device)

        S = 'attempting to mount device %s (%s:%s)'
        self.log.info(S % (device, fstype, options))

        try:
            device.mount(fstype, options)
            self.log.info('mounted device %s' % (device,))
        except dbus.exceptions.DBusException, dbus_err:
            self.log.error('failed to mount device %s: %s' % (
                                                device, dbus_err))
            return None

        mount_paths = ', '.join(device.mount_paths)

        return True

    def unlock_device(self, device):
        """
        Unlock the device if not already unlocked.

        Return value indicates whether an action was performed successfully.
        The special value `None` means unknown/unreliable.

        """
        if not device.is_handleable or not device.is_crypto:
            self.log.debug('skipping unhandled device %s' % (device,))
            return False
        if device.is_unlocked:
            self.log.debug('skipping unlocked device %s' % (device,))
            return False

        # prompt user for password
        password = self.prompt and self.prompt(
                'Enter password for %s:' % (device,),
                'Unlock encrypted device')
        if password is None:
            return False

        # unlock device
        self.log.info('attempting to unlock device %s' % (device,))
        try:
            device.unlock(password, [])
            holder_dev = udiskie.device.Device(
                    self.bus,
                    device.luks_cleartext_holder)
            holder_path = holder_dev.device_file
            self.log.info('unlocked device %s on %s' % (device, holder_path))
        except dbus.exceptions.DBusException, dbus_err:
            self.log.error('failed to unlock device %s:\n%s'
                                        % (device, dbus_err))
            return None
        return True

    def add_device(self, device):
        """Mount or unlock the device depending on its type."""
        if not device.is_handleable:
            self.log.debug('skipping unhandled device %s' % (device,))
            return False
        if device.is_filesystem:
            return self.mount_device(device)
        elif device.is_crypto:
            return self.unlock_device(device)

    def mount_present_devices(self):
        """Mount handleable devices that are already present."""
        for device in udiskie.device.get_all_handleable(self.bus):
            self.add_device(device)


def option_parser():
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

def cli(args, allow_daemon=False):
    parser = option_parser()
    options, posargs = parser.parse_args(args)
    logging.basicConfig(level=options.log_level, format='%(message)s')
    run_daemon = allow_daemon and not options.all and len(posargs) == 0

    # establish connection to system bus
    if run_daemon:
        from dbus.mainloop.glib import DBusGMainLoop
        DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    # create a mounter
    prompt = udiskie.prompt.password(options.password_prompt)
    mounter = Mounter(bus=bus, filter_file=options.filters, prompt=prompt)

    # run udiskie daemon if needed
    if run_daemon:
        daemon = udiskie.daemon.Daemon(bus)
    if run_daemon and not options.suppress_notify:
        notify = udiskie.notify.Notify('udiskie.mount')
        notify.connect(daemon)
    if run_daemon:
        automount = udiskie.automount.AutoMounter(mounter)
        automount.connect(daemon)

    # mount all present devices
    if options.all:
        mounter.mount_present_devices()

    # only mount the desired devices
    elif len(posargs) > 0:
        for path in posargs:
            device = udiskie.device.get_device(mounter.bus, path)
            if device:
                mounter.add_device(device)

    # run in daemon mode
    elif run_daemon:
        mounter.mount_present_devices()
        return daemon.run()

    # print command line options
    else:
        parser.print_usage()

