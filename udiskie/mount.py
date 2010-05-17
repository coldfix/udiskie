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

    def device_added(self, device):
        self.log.debug('device added: %s' % (device,))
        udevice = udiskie.device.Device(self.bus, device)
        if udevice.is_handleable():
            filesystem = str(udevice.id_type())
            options = []
            udevice.mount(filesystem, options)


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
    return gobject.MainLoop().run()
