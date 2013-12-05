"""
Udisks event daemon module.

Provides the class `Daemon` which listens to udisks events. When a change
occurs this class detects what has changed and triggers an appropriate
event.

"""
__all__ = ['Daemon']

import logging
import sys


class DeviceState(object):
    """
    State information struct for devices.
    """
    __slots__ = ['mounted', 'has_media', 'unlocked']

    def __init__(self, mounted, has_media, unlocked):
        self.mounted = mounted
        self.has_media = has_media
        self.unlocked = unlocked

class Daemon(object):
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
    def __init__(self, udisks):
        """
        Initialize object and start listening to udisks events.
        """
        self.log = logging.getLogger('udiskie.daemon.Daemon')
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

        for device in self.udisks.get_all():
            self._store_device_state(device)

        udisks.bus.add_signal_receiver(
                self._device_added,
                signal_name='DeviceAdded',
                bus_name='org.freedesktop.UDisks')
        udisks.bus.add_signal_receiver(
                self._device_removed,
                signal_name='DeviceRemoved',
                bus_name='org.freedesktop.UDisks')
        udisks.bus.add_signal_receiver(
                self._device_changed,
                signal_name='DeviceChanged',
                bus_name='org.freedesktop.UDisks')

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

    def connect(self, handler, event=None):
        """Connect an event handler."""
        if event:
            self.event_handlers[event].append(handler)
        else:
            for event in self.event_handlers:
                if hasattr(handler, event):
                    self.connect(getattr(handler, event), event)

    def disconnect(self, handler, event=None):
        """Disconnect an event handler."""
        if event:
            self.event_handlers.remove(handler)
        else:
            for event in self.event_handlers:
                if hasattr(handler, event):
                    self.disconnect(getattr(handler, event), event)

    # udisks event listeners
    def _device_added(self, object_path):
        try:
            udevice = self.udisks.create_device(object_path)
            self._store_device_state(udevice)
            self.trigger('device_added', udevice)
        except self.udisks.Exception:
            err = sys.exc_info()[1]
            self.log.error('%s(%s): %s' % ('device_added', object_path, err))

    def _device_removed(self, object_path):
        try:
            self.trigger('device_removed', object_path)
            self._remove_device_state(object_path)
        except self.udisks.Exception:
            err = sys.exc_info()[1]
            self.log.error('%s(%s): %s' % ('device_removed', object_path, err))

    def _device_changed(self, object_path):
        try:
            udevice = self.udisks.create_device(object_path)
            old_state = self._get_device_state(object_path)
            new_state = self._store_device_state(udevice)
            self.trigger('device_changed', udevice, old_state, new_state)
        except self.udisks.Exception:
            err = sys.exc_info()[1]
            self.log.error('%s(%s): %s' % ('device_changed', object_path, err))

    # internal state keeping
    def _store_device_state(self, device):
        self.state[device.object_path] = DeviceState(
            device.is_mounted,
            device.has_media,
            device.is_unlocked)
        return self.state[device.object_path]

    def _remove_device_state(self, object_path):
        if object_path in self.state:
            del self.state[object_path]

    def _get_device_state(self, object_path):
        return self.state.get(object_path)

