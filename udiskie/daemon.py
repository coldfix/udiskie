"""
Udisks event daemon module.

Provides the class `Daemon` which listens to udisks events. When a change
occurs this class detects what has changed and triggers an appropriate
event.

"""
__all__ = ['Daemon']

import logging
import sys

class Job(object):
    """
    Job information struct for devices.
    """
    __slots__ = ['id', 'percentage']

    def __init__(self, id, percentage):
        self.id = id
        self.percentage = percentage

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
        self.jobs = {}
        self.udisks = udisks

        event_stems = [
            'device_add',
            'device_remov',
            'device_mount',
            'device_unmount',
            'media_add',
            'media_remov',
            'device_unlock',
            'device_lock',
            'device_chang', ]

        self.event_handlers = {}
        for stem in event_stems:
            self.event_handlers[stem + 'ed'] = []
            self.event_handlers[stem + 'ing'] = []

        self.connect(self.on_device_changed, 'device_changed')

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
        udisks.bus.add_signal_receiver(
            self._device_job_changed,
            signal_name='DeviceJobChanged',
            bus_name='org.freedesktop.UDisks')

    # events
    def on_device_changed(self, udevice, old_state, new_state):
        """Detect type of event and trigger appropriate event handlers."""
        if old_state is None:
            self.trigger('device_added', udevice)
            return
        d = {}
        d['media_added'] = new_state.has_media and not old_state.has_media
        d['media_removed'] = old_state.has_media and not new_state.has_media
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
            if not udevice.is_handleable:
                return
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
            if not udevice.is_handleable:
                return
            old_state = self._get_device_state(object_path)
            new_state = self._store_device_state(udevice)
            self.trigger('device_changed', udevice, old_state, new_state)
        except self.udisks.Exception:
            err = sys.exc_info()[1]
            self.log.error('%s(%s): %s' % ('device_changed', object_path, err))

    # NOTE: it seems the udisks1 documentation for DeviceJobChanged is
    # fatally incorrect!
    def _device_job_changed(self,
                            object_path,
                            job_in_progress,
                            job_id,
                            job_initiated_by_user,
                            job_is_cancellable,
                            job_percentage):

        """Detect type of event and trigger appropriate event handlers."""
        try:
            event_mapping = {
                'FilesystemMount': 'device_mount',
                'FilesystemUnmount': 'device_unmount',
                'LuksUnlock': 'device_unlock',
                'LuksLock': 'device_lock', }
            if not job_in_progress and object_path in self.jobs:
                job_id = self.jobs[object_path].id

            if job_id in event_mapping:
                event_name = event_mapping[job_id]
                dev = self.udisks.create_device(object_path)
                if job_in_progress:
                    self.trigger(event_name + 'ing', dev, job_percentage)
                    self.jobs[object_path] = Job(job_id, job_percentage)
                else:
                    self.trigger(event_name + 'ed', dev)
                    del self.jobs[object_path]
        except self.udisks.Exception:
            err = sys.exc_info()[1]
            self.log.error('%s(%s): %s' % ('_device_job_changed', object_path, err))


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

