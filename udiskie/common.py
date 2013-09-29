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
        """Initialize a proxy object with standard dbus property interface."""
        self.__proxy = Interface(
                dbus_object,
                dbus_interface='org.freedesktop.DBus.Properties')
        self.__interface = interface

    def __getattr__(self, property):
        """Retrieve the property via the dbus proxy."""
        return self.__proxy.Get(self.__interface, property)

class DBusProxy(object):
    """
    DBus proxy object.

    Provides property and method bindings.

    """
    def __init__(self, proxy, interface):
        self.Exception = DBusException
        self.proxy = proxy
        self.object_path = proxy.object_path
        self.property = DBusProperties(self.proxy, interface)
        self.method = Interface(self.proxy, interface)

