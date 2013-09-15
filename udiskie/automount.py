import logging
import gobject

import udiskie
import udiskie.device
import udiskie.mount
import udiskie.notify

class DeviceState:
    def __init__(self, mounted, has_media):
        self.mounted = mounted
        self.has_media = has_media

class AutoMounter:

    def __init__(self, bus=None, filter_file=None, notify=None, prompt=None):
        self.log = logging.getLogger('udiskie.mount.AutoMounter')
        self.mounter = udiskie.mount.Mounter(bus, filter_file, notify, prompt)
        self.bus = self.mounter.bus

        self.last_device_state = {}

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
        self._store_device_state(udiskie_device)
        self.mounter.add_device(udiskie_device)

    def device_removed(self, device):
        self.log.debug('device removed: %s' % (device,))
        self._remove_device_state(udiskie.device.Device(self.bus, device))

    def device_changed(self, device):
        self.log.debug('device changed: %s' % (device,))

        udiskie_device = udiskie.device.Device(self.bus, device)
        last_state = self._get_device_state(udiskie_device)

        if not last_state:
            # First time we saw the device, try to mount it.
            self.mounter.add_device(udiskie_device)
        else:
            media_added = False
            if udiskie_device.has_media and not last_state.has_media:
                media_added = True

            if media_added and not last_state.mounted:
                # Wasn't mounted before, but it has new media now.
                self.mounter.add_device(udiskie_device)

        self._store_device_state(udiskie_device)


    def _store_device_state(self, device):
        state = DeviceState(device.is_mounted,
                            device.has_media)
        self.last_device_state[device.device_path] = state

    def _remove_device_state(self, device):
        if device.device_path in self.last_device_state:
            del self.last_device_state[device.device_path]

    def _get_device_state(self, device):
        return self.last_device_state.get(device.device_path)



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
        mounter.mounter.mount_present_devices()
        return gobject.MainLoop().run()


