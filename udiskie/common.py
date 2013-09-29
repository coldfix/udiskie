"""
Common utilities.
"""
__all__ = ['Properties', 'get_udisks', 'default_udisks']
import dbus

DBUS_PROPS_INTERFACE = 'org.freedesktop.DBus.Properties'
default_udisks = 'udiskie.udisks'


def get_udisks():
    import importlib
    return importlib.import_module(default_udisks)

class Properties(object):
    """
    Dbus property map abstraction.

    Properties of the object can be accessed as attributes.

    """
    def __init__(self, dbus_object, interface):
        """Initialize a proxy object with standard dbus property interface."""
        self.__proxy = dbus.Interface(
                dbus_object,
                dbus_interface=DBUS_PROPS_INTERFACE)
        self.__interface = interface

    def __getattr__(self, property):
        """Retrieve the property via the dbus proxy."""
        return self.__proxy.Get(self.__interface, property)

