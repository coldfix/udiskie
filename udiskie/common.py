"""
Common DBus utilities.
"""

from dbus import Interface, SystemBus
from dbus.exceptions import DBusException
from dbus.mainloop.glib import DBusGMainLoop


__all__ = ['DBusProperties',
           'DBusProxy',
           'DBusService',
           'DBusException',
           'Emitter']


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


class DBusService(object):

    """
    Abstract base class for UDisksX service wrapper classes.
    """

    mainloop = None

    @classmethod
    def connect_service(cls, bus=None, mainloop=None):
        """
        Connect to the service object on dbus.

        :param dbus.Bus bus: connection to system bus
        :param dbus.mainloop.NativeMainLoop mainloop: system bus event loop
        :raises dbus.DBusException: if unable to connect to service.

        The mainloop parameter is only relevant if no bus is given. In this
        case if ``mainloop is True``, use the default (glib) mainloop
        provided by dbus-python.
        """
        if bus is None:
            mainloop = mainloop or cls.mainloop
            if mainloop is True:
                mainloop = DBusGMainLoop()
            bus = SystemBus(mainloop=mainloop or cls.mainloop)
        obj = bus.get_object(cls.BusName, cls.ObjectPath)
        return DBusProxy(obj, cls.Interface)


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
        self._event_handlers = {}
        for evt in event_names:
            self._event_handlers[evt] = []

    def trigger(self, event, *args):
        """Trigger event handlers."""
        for handler in self._event_handlers[event]:
            handler(*args)

    def connect_all(self, obj):
        """
        Connect all handlers of a multi-slot object.

        :param obj: multi-slot
        """
        for event in self._event_handlers:
            if hasattr(obj, event):
                self.connect(event, getattr(obj, event))

    def disconnect_all(self, obj):
        """
        Disconnect all handlers of a multi-slot object.

        :param obj: multi-slot
        """
        for event in self._event_handlers:
            if hasattr(obj, event):
                self.disconnect(event, getattr(obj, event))

    def connect(self, event, handler):
        """
        Connect an event handler.

        :param str event: event name
        :param callable handler: event handler
        """
        self._event_handlers[event].append(handler)

    def disconnect(self, event, handler):
        """
        Disconnect an event handler.

        :param str event: event name
        :param callable handler: event handler
        """
        self._event_handlers[event].remove(handler)
