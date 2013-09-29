"""
Common utilities.
"""
__all__ = ['DBusProperties', 'get_udisks']

from dbus import Interface

def get_udisks():
    from . import udisks
    return udisks

class DBusProperties(object):
    """
    Dbus property map abstraction.

    Properties of the object can be accessed as attributes.

    """
    def __init__(self, dbus_object, interface, Ifc=Interface):
        """Initialize a proxy object with standard dbus property interface."""
        self.__proxy = Ifc(
                dbus_object,
                dbus_interface='org.freedesktop.DBus.Properties')
        self.__interface = interface

    def __getattr__(self, property):
        """Retrieve the property via the dbus proxy."""
        return self.__proxy.Get(self.__interface, property)

