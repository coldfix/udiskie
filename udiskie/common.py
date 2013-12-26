"""
Common DBus utilities.
"""
__all__ = ['DBusProperties', 'DBusProxy']

from dbus import Interface
from dbus.exceptions import DBusException

class DBusProperties(object):
    """
    Dbus property map abstraction.

    Properties of the object can be accessed as attributes.

    """
    def __init__(self, dbus_object, interface):
        """Initialize a proxy object with standard DBus property interface."""
        self.__proxy = Interface(
                dbus_object,
                dbus_interface='org.freedesktop.DBus.Properties')
        self.__interface = interface

    def __getattr__(self, property):
        """Retrieve the property via the DBus proxy."""
        return self.__proxy.Get(self.__interface, property)

class DBusProxy(object):
    """
    DBus proxy object.

    Provides property and method bindings.

    """
    def __init__(self, proxy, interface):
        self.Exception = DBusException
        self.object_path = proxy.object_path
        self.property = DBusProperties(proxy, interface)
        self.method = Interface(proxy, interface)
        self._bus = proxy._bus

class Emitter(object):
    """
    Event emitter class.

    Provides a simple event engine featuring a known finite set of events.

    """
    def __init__(self, event_names=(), *args, **kwargs):
        """
        Initialize with empty lists of event handlers.

        :param iterable event_names: names of known events.

        """
        super(Emitter, self).__init__(*args, **kwargs)
        self.event_handlers = {}
        for evt in event_names:
            self.event_handlers[evt] = []

    def trigger(self, event, *args):
        """Trigger event handlers."""
        for handler in self.event_handlers[event]:
            handler(*args)

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

