"""
Common utilities.
"""
__all__ = ['Properties', 'system_bus']
import dbus


DBUS_PROPS_INTERFACE = 'org.freedesktop.DBus.Properties'

class Properties:
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

def system_bus():
    """
    Connect to system bus.

    When called for the first time, dbus will be initialized to use a glib
    mainloop.

    """
    if not system_bus.initialized:
        from dbus.mainloop.glib import DBusGMainLoop
        DBusGMainLoop(set_as_default=True)
        system_bus.initialized = True
    return dbus.SystemBus()
system_bus.initialized = False

