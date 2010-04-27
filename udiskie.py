#! /usr/bin/env python

import dbus
from dbus.mainloop.glib import DBusGMainLoop
import gobject

DBusGMainLoop(set_as_default=True)
system_bus = dbus.SystemBus()

def device_added(device):
    print 'device added: %s' % (device,)

def device_changed(device):
    print 'device changed: %s' % (device,)

def device_removed(device):
    print 'device removed: %s' % (device,)

system_bus.add_signal_receiver(device_added,
                               signal_name='DeviceAdded',
                               bus_name='org.freedesktop.UDisks')
system_bus.add_signal_receiver(device_changed,
                               signal_name='DeviceChanged',
                               bus_name='org.freedesktop.UDisks')
system_bus.add_signal_receiver(device_removed,
                               signal_name='DeviceRemoved',
                               bus_name='org.freedesktop.UDisks')

loop = gobject.MainLoop()
loop.run()
