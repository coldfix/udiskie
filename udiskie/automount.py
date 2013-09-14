import logging
import gobject

import udiskie.notify
import udiskie.mount
import udiskie.device


class AutoMounter(udiskie.mount.Mounter):

    def __init__(self, bus=None, filter_file=None, notify=None, prompt=None):
        udiskie.mount.Mounter.__init__(self, bus, filter_file, notify, prompt)
        self.log = logging.getLogger('udiskie.mount.AutoMounter')

        self.bus.add_signal_receiver(self.device_added,
                                     signal_name='DeviceAdded',
                                     bus_name='org.freedesktop.UDisks')
        self.bus.add_signal_receiver(self.device_removed,
                                     signal_name='DeviceRemoved',
                                     bus_name='org.freedesktop.UDisks')
        self.bus.add_signal_receiver(self.device_changed,
                                     signal_name='DeviceChanged',
                                     bus_name='org.freedesktop.UDisks')


    def device_added(self, device):
        self.log.debug('device added: %s' % (device,))
        udiskie_device = udiskie.device.Device(self.bus, device)
        # Since the device just appeared we don't want the old state.
        self._remove_device_state(udiskie_device)
        self.add_device(udiskie_device)

    def device_removed(self, device):
        self.log.debug('device removed: %s' % (device,))
        self._remove_device_state(udiskie.device.Device(self.bus, device))

    def device_changed(self, device):
        self.log.debug('device changed: %s' % (device,))

        udiskie_device = udiskie.device.Device(self.bus, device)
        last_state = self._get_device_state(udiskie_device)

        if not last_state:
            # First time we saw the device, try to mount it.
            self.add_device(udiskie_device)
        else:
            media_added = False
            if udiskie_device.has_media() and not last_state.has_media:
                media_added = True

            if media_added and not last_state.mounted:
                # Wasn't mounted before, but it has new media now.
                self.add_device(udiskie_device)

        self._store_device_state(udiskie_device)



def cli(args):
    import udiskie.mount
    options, posargs = udiskie.mount.option_parser().parse_args(args)

    # invoked as a mount tool
    if options.all or len(posargs) > 0:
        return udiskie.mount.cli(args)

    # run as a daemon
    else:
        logging.basicConfig(level=options.log_level, format='%(message)s')

        if options.suppress_notify:
            notify = None
        else:
            notify = udiskie.notify.Notify('udiskie.mount')

        import udiskie.prompt
        prompt = udiskie.prompt.password(options.password_prompt)

        mounter = AutoMounter(
                bus=None, filter_file=options.filters,
                notify=notify, prompt=prompt)
        mounter.mount_present_devices()
        return gobject.MainLoop().run()


