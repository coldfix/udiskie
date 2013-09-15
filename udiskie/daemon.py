"""
Udisks event daemon module.

Provides the class `Daemon` which listens to udisks events. When a change
occurs this class detects what has changed and triggers an appropriate
event.

"""
__all__ = ['Daemon']

import gobject
import logging
import dbus

import sys


class DeviceState:
    """
    State information struct for devices.
    """
    __slots__ = ['mounted', 'has_media', 'unlocked']

    def __init__(self, mounted, has_media, unlocked):
        self.mounted = mounted
        self.has_media = has_media
        self.unlocked = unlocked

class Daemon:
    """
    Udisks listener daemon.

    Listens to udisks events. When a change occurs this class detects what
    has changed and triggers an appropriate event. Valid events are:

        - device_added    / device_removed
        - device_unlocked / device_locked
        - device_mounted  / device_unmounted
        - media_added     / media_removed
        - device_changed

    A very primitive mechanism that gets along without external
    dependencies is used for event dispatching. The methods `connect` and
    `disconnect` can be used to add or remove event handlers.

    """
    def __init__(self, bus, udisks):
        """
        Initialize object and start listening to udisks events.
        """
        self.log = logging.getLogger('udiskie.daemon.Daemon')
        self.bus = bus
        self.state = {}
        self.udisks = udisks

        self.event_handlers = {
            'device_added': [],
            'device_removed': [],
            'device_mounted': [],
            'device_unmounted': [],
            'media_added': [],
            'media_removed': [],
            'device_unlocked': [],
            'device_locked': [],
            'device_changed': [self.on_device_changed]
        }

        for device in self.udisks.get_all_handleable(bus):
            self._store_device_state(device)

        self.bus.add_signal_receiver(
                self._device_added,
                signal_name='DeviceAdded',
                bus_name='org.freedesktop.UDisks')
        self.bus.add_signal_receiver(
                self._device_removed,
                signal_name='DeviceRemoved',
                bus_name='org.freedesktop.UDisks')
        self.bus.add_signal_receiver(
                self._device_changed,
                signal_name='DeviceChanged',
                bus_name='org.freedesktop.UDisks')

    def run(self):
        """Run main loop."""
        return gobject.MainLoop().run()

    # events
    def on_device_changed(self, udevice, old_state, new_state):
        """Detect type of event and trigger appropriate event handlers."""
        if old_state is None:
            self.trigger('device_added', udevice)
            return
        d = {}
        d['device_mounted'] = new_state.mounted and not old_state.mounted
        d['device_unmounted'] = old_state.mounted and not new_state.mounted
        d['media_added'] = new_state.has_media and not old_state.has_media
        d['media_removed'] = old_state.has_media and not new_state.has_media
        d['device_unlocked'] = new_state.unlocked and not old_state.unlocked
        d['device_locked'] = old_state.unlocked and not new_state.unlocked
        for event in d:
            if d[event]:
                self.trigger(event, udevice)

    # event machinery
    def trigger(self, event, device, *args):
        """Trigger event handlers."""
        self.log.debug('%s: %s' % (event, device))
        for handler in self.event_handlers[event]:
            handler(device, *args)

    def connect(self, event, handler):
        """Connect an event handler."""
        self.event_handlers[event].append(handler)

    def disconnect(self, event, handler):
        """Disconnect an event handler."""
        self.event_handlers.remove(handler)

    # udisks event listeners
    def _device_added(self, device_name):
        try:
            udevice = self.udisks.Device(self.bus, device_name)
            if not udevice.is_handleable:
                return
            self._store_device_state(udevice)
            self.trigger('device_added', udevice)
        except dbus.exceptions.DBusException:
            err = sys.exc_info()[1]
            self.log.error('%s(%s): %s' % ('device_added', device_name, err))

    def _device_removed(self, device_name):
        try:
            self.trigger('device_removed', device_name)
            self._remove_device_state(device_name)
        except dbus.exceptions.DBusException:
            err = sys.exc_info()[1]
            self.log.error('%s(%s): %s' % ('device_removed', device_name, err))

    def _device_changed(self, device_name):
        try:
            udevice = self.udisks.Device(self.bus, device_name)
            if not udevice.is_handleable:
                return
            old_state = self._get_device_state(udevice)
            new_state = self._store_device_state(udevice)
            self.trigger('device_changed', udevice, old_state, new_state)
        except dbus.exceptions.DBusException:
            err = sys.exc_info()[1]
            self.log.error('%s(%s): %s' % ('device_changed', device_name, err))

    # internal state keeping
    def _store_device_state(self, device):
        self.state[device.device_path] = DeviceState(
            device.is_mounted,
            device.has_media,
            device.is_unlocked)
        return self.state[device.device_path]

    def _remove_device_state(self, device_name):
        if device_name in self.state:
            del self.state[device_name]

    def _get_device_state(self, device):
        return self.state.get(device.device_path)

