import warnings
warnings.filterwarnings("ignore", ".*could not open display.*", Warning)
warnings.filterwarnings("ignore", ".*g_object_unref.*", Warning)

import logging
import optparse
import os

import dbus
import gobject

try:
    from xdg.BaseDirectory import xdg_config_home
except ImportError:
    xdg_config_home = os.path.expanduser('~/.config')

import udiskie.device
import udiskie.match
import udiskie.notify
import udiskie.prompt

class DeviceState:
    def __init__(self, mounted, has_media):
        self.mounted = mounted
        self.has_media = has_media


class AutoMounter:
    CONFIG_PATH = 'udiskie/filters.conf'

    def __init__(self, bus=None, filter_file=None, notify=None, prompt=None):
        self.log = logging.getLogger('udiskie.mount.AutoMounter')
        self.last_device_state = {}

        if not bus:
            from dbus.mainloop.glib import DBusGMainLoop
            DBusGMainLoop(set_as_default=True)
            self.bus = dbus.SystemBus()
        else:
            self.bus = bus

        if not filter_file:
            filter_file = os.path.join(xdg_config_home, self.CONFIG_PATH)
        self.filters = udiskie.match.FilterMatcher((filter_file,))

        if not notify:
            self.notify = lambda ctx: lambda *args: True
        else:
            self.notify = lambda ctx: getattr(notify, ctx)

        if not prompt:
            self.prompt = lambda text, title: None
        else:
            self.prompt = prompt


        self.bus.add_signal_receiver(self.device_added,
                                     signal_name='DeviceAdded',
                                     bus_name='org.freedesktop.UDisks')
        self.bus.add_signal_receiver(self.device_removed,
                                     signal_name='DeviceRemoved',
                                     bus_name='org.freedesktop.UDisks')
        self.bus.add_signal_receiver(self.device_changed,
                                     signal_name='DeviceChanged',
                                     bus_name='org.freedesktop.UDisks')

    def _mount_device(self, device):
        if device.is_handleable():
            try:
                if device.is_mounted():
                    return
                fstype = str(device.id_type())
                options = self.filters.get_mount_options(device)

                S = 'attempting to mount device %s (%s:%s)'
                self.log.info(S % (device, fstype, options))

                try:
                    device.mount(fstype, options)
                    self.log.info('mounted device %s' % (device,))
                except dbus.exceptions.DBusException, dbus_err:
                    self.log.error('failed to mount device %s: %s' % (
                                                        device, dbus_err))
                    return

                mount_paths = ', '.join(device.mount_paths())
                self.notify('mount')(device.device_file(), mount_paths)
            finally:
                self._store_device_state(device)

        elif device.is_crypto():
            if device.is_unlocked():
                return

            # prompt user for password
            password = self.prompt(
                    'Enter password for %s:' % (device,),
                    'Unlock encrypted device')
            if password is None:
                return

            # unlock device
            self.log.info('attempting to unlock device %s' % (device,))
            try:
                device.unlock(password, [])
                self.log.info('unlocked device %s' % (device,))
            except dbus.exceptions.DBusException, dbus_err:
                self.log.error('failed to unlock device %s:\n%s'
                                            % (device, dbus_err))
                return

            self.notify('unlock')(device.device_file())

    def _store_device_state(self, device):
        state = DeviceState(device.is_mounted(),
                            device.has_media())
        self.last_device_state[device.device_path] = state

    def _remove_device_state(self, device):
        if device.device_path in self.last_device_state:
            del self.last_device_state[device.device_path]

    def _get_device_state(self, device):
        return self.last_device_state.get(device.device_path)

    def mount_present_devices(self):
        """Mount handleable devices that are already present."""
        for device in udiskie.device.get_all(self.bus):
            self._mount_device(device)

    def device_added(self, device):
        self.log.debug('device added: %s' % (device,))
        udiskie_device = udiskie.device.Device(self.bus, device)
        # Since the device just appeared we don't want the old state.
        self._remove_device_state(udiskie_device)
        self._mount_device(udiskie_device)

    def device_removed(self, device):
        self.log.debug('device removed: %s' % (device,))
        self._remove_device_state(udiskie.device.Device(self.bus, device))

    def device_changed(self, device):
        self.log.debug('device changed: %s' % (device,))

        udiskie_device = udiskie.device.Device(self.bus, device)
        last_state = self._get_device_state(udiskie_device)

        if not last_state:
            # First time we saw the device, try to mount it.
            self._mount_device(udiskie_device)
        else:
            media_added = False
            if udiskie_device.has_media() and not last_state.has_media:
                media_added = True

            if media_added and not last_state.mounted:
                # Wasn't mounted before, but it has new media now.
                self._mount_device(udiskie_device)

        self._store_device_state(udiskie_device)


def cli(args):
    parser = optparse.OptionParser()
    parser.add_option('-v', '--verbose', action='store_true',
                      dest='verbose', default=False,
                      help='verbose output')
    parser.add_option('-f', '--filters', action='store',
                      dest='filters', default=None,
                      metavar='FILE', help='filter FILE')
    parser.add_option('-s', '--suppress', action='store_true',
                      dest='suppress_notify', default=False,
                      help='suppress popup notifications')
    parser.add_option('-P', '--password-prompt', action='store',
                      dest='password_prompt', default='zenity',
                      metavar='MODULE', help="replace password prompt")
    (options, args) = parser.parse_args(args)

    log_level = logging.INFO
    if options.verbose:
        log_level = logging.DEBUG
    logging.basicConfig(level=log_level, format='%(message)s')

    if options.suppress_notify:
        notify = None
    else:
        notify = udiskie.notify.Notify('udiskie.mount')

    prompt = udiskie.prompt.password(options.password_prompt)

    mounter = AutoMounter(
            bus=None, filter_file=options.filters,
            notify=notify, prompt=prompt)
    mounter.mount_present_devices()
    return gobject.MainLoop().run()
