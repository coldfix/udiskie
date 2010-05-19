import logging
import optparse

import dbus
import gobject

import udiskie.device

class AutoMounter:
    def __init__(self, bus=None):
        self.log = logging.getLogger('udiskie.mount.AutoMounter')

        if not bus:
            from dbus.mainloop.glib import DBusGMainLoop
            DBusGMainLoop(set_as_default=True)
            self.bus = dbus.SystemBus()
        else:
            self.bus = bus

        self.bus.add_signal_receiver(self.device_added,
                                     signal_name='DeviceAdded',
                                     bus_name='org.freedesktop.UDisks')

    def _mount_device(self, device):
        if device.is_handleable() and not device.is_mounted():
            filesystem = str(device.id_type())
            options = []
            try:
                device.mount(filesystem, options)
                self.log.info('mounted device %s' % (device,))
            except dbus.exceptions.DBusException, dbus_err:
                self.log.error('failed to mount device %s: %s' % (device,
                                                                  dbus_err))

    def mount_present_devices(self):
        """Mount handleable devices that are already present."""
        for device in udiskie.device.get_all(self.bus):
            self._mount_device(device)

    def device_added(self, device):
        self.log.debug('device added: %s' % (device,))
        self._mount_device(udiskie.device.Device(self.bus, device))


def cli(args):
    parser = optparse.OptionParser()
    parser.add_option('-v', '--verbose', action='store_true',
                      dest='verbose', default=False,
                      help='verbose output')
    (options, args) = parser.parse_args(args)

    log_level = logging.INFO
    if options.verbose:
        log_level = logging.DEBUG
    logging.basicConfig(level=log_level, format='%(message)s')

    mounter = AutoMounter()
    mounter.mount_present_devices()
    return gobject.MainLoop().run()
