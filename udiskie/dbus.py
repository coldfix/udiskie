"""
Common DBus utilities.
"""

from __future__ import absolute_import

from dbus import Interface, SystemBus
from dbus.exceptions import DBusException
from dbus.mainloop.glib import DBusGMainLoop


__all__ = ['DBusProperties',
           'DBusProxy',
           'DBusService',
           'DBusException']


class DBusProperties(object):

    """
    Dbus property map abstraction.

    Wraps properties of a DBus interface on a DBus object as attributes.
    """

    def __init__(self, dbus_object, interface):
        """
        Initialize a proxy object with standard DBus property interface.

        :param dbus.proxies.ProxyObject dbus_object: accessed object
        :param str interface: accessed interface name
        """
        self.__proxy = Interface(
            dbus_object,
            dbus_interface='org.freedesktop.DBus.Properties')
        self.__interface = interface

    def __getattr__(self, property):
        """
        Retrieve the property via the DBus proxy.

        :param str property: name of the dbus property
        :returns: the property
        """
        return self.__proxy.Get(self.__interface, property)


class DBusProxy(object):

    """
    DBus proxy object.

    Provides attribute accessors to properties and methods of a DBus
    interface on a DBus object.

    :ivar object_path: object path of the DBus object
    :ivar property: attribute access to DBus properties
    :ivar method: attribute access to DBus methods
    """

    Exception = DBusException

    def __init__(self, proxy, interface):
        """
        Initialize property and method attribute accessors for the interface.

        :param dbus.proxies.ProxyObject proxy: accessed object
        :param str interface: accessed interface
        """
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
        Connect to the service object on DBus.

        :param dbus.Bus bus: connection to system bus
        :param dbus.mainloop.NativeMainLoop mainloop: system bus event loop
        :returns: new proxy object for the service
        :rtype: DBusProxy
        :raises BusException: if unable to connect to service.

        The mainloop parameter is only relevant if no bus is given. In this
        case if ``mainloop is True``, use the default (glib) mainloop provided
        by dbus-python.
        """
        if bus is None:
            mainloop = mainloop if mainloop is not None else cls.mainloop
            if mainloop is True:
                mainloop = DBusGMainLoop()
            elif mainloop is False:
                mainloop = None
            bus = SystemBus(mainloop=mainloop)
        obj = bus.get_object(cls.BusName, cls.ObjectPath)
        return DBusProxy(obj, cls.Interface)
