"""
Common DBus utilities.
"""

from __future__ import absolute_import

from gi.repository import Gio
from gi.repository import GLib


__all__ = ['PropertiesProxy',
           'InterfaceProxy',
           'ObjectProxy',
           'BusProxy',
           'DBusService',
           'DBusException']


DBusException = GLib.GError


class PropertiesProxy(object):

    """
    Resolve attribute accesses by querying properties of a DBus object.
    """

    def __init__(self, dbus_object, interface_name):
        """
        Initialize from a ObjectProxy and interface name.

        :param ObjectProxy dbus_object:
        :param str interface_name:
        """
        properties_interface = 'org.freedesktop.DBus.Properties'
        self.__proxy = dbus_object._get_interface(properties_interface)
        self.__interface = interface_name

    def __getattr__(self, property_name):
        """
        Retrieve the property via the DBus proxy.

        :param str property_name: name of the dbus property
        :returns: the property value
        """
        return self.__proxy.Get('(ss)', self.__interface, property_name)


class InterfaceProxy(object):

    """
    DBus proxy object for a specific interface.

    Provides attribute accessors to properties and methods of a DBus
    interface on a DBus object.

    :ivar str object_path: object path of the DBus object
    :ivar PropertiesProxy property: attribute access to DBus properties
    :ivar Gio.DBusProxy method: attribute access to DBus methods
    :ivar Gio.DBusProxy _proxy: underlying proxy object
    """

    Exception = DBusException

    def __init__(self, proxy):
        """
        Initialize property and method attribute accessors for the interface.

        :param Gio.DBusProxy proxy: accessed object
        :param str interface: accessed interface
        """
        self._proxy = proxy
        self.object_path = proxy.get_object_path()
        self.property = PropertiesProxy(self.object,
                                        proxy.get_interface_name())
        self.method = proxy

    @property
    def object(self):
        """
        Get a proxy for the underlying object.

        :rtype: ObjectProxy
        """
        proxy = self._proxy
        return ObjectProxy(proxy.get_connection(),
                           proxy.get_name(),
                           proxy.get_object_path())

    def connect(self, event, handler):
        """
        Connect to a DBus signal.

        :param str event: event name
        :param handler: callback
        :returns: subscription id
        :rtype: int
        """
        interface = self._proxy.get_interface_name()
        return self.object.connect(interface, event, handler)


class ObjectProxy(object):

    """
    Simple proxy class for a DBus object.

    :param Gio.DBusConnection connection:
    :param str bus_name:
    :param str object_path:
    """

    def __init__(self, connection, bus_name, object_path):
        """
        Initialize member variables.

        :ivar Gio.DBusConnection connection:
        :ivar str bus_name:
        :ivar str object_path:

        This performs no IO at all.
        """
        self.connection = connection
        self.bus_name = bus_name
        self.object_path = object_path

    def _get_interface(self, name):
        """
        Get a Gio native interface proxy for this Dbus object.

        :param str name: interface name
        :returns: a proxy object for the other interface
        :rtype: Gio.DBusProxy
        """
        return Gio.DBusProxy.new_sync(
            self.connection,
            Gio.DBusProxyFlags.NONE,
            info=None,
            name=self.bus_name,
            object_path=self.object_path,
            interface_name=name,
            cancellable=None,
        )

    def get_interface(self, name):
        """
        Get an interface proxy for this Dbus object.

        :param str name: interface name
        :returns: a proxy object for the other interface
        :rtype: InterfaceProxy
        """
        return InterfaceProxy(self._get_interface(name))

    @property
    def bus(self):
        """
        Get a proxy object for the underlying bus.

        :rtype: BusProxy
        """
        return BusProxy(self.connection, self.bus_name)

    def connect(self, interface, event, handler):
        """
        Connect to a DBus signal.

        :param str interface: interface name
        :param str event: event name
        :param handler: callback
        :returns: subscription id
        :rtype: int
        """
        object_path = self.object_path
        return self.bus.connect(interface, event, object_path, handler)


class DBusCallback(object):

    def __init__(self, handler):
        """Store reference to handler."""
        self._handler = handler

    def __call__(self,
                 connection,
                 sender_name,
                 object_path,
                 interface_name,
                 signal_name,
                 parameters,
                 *user_data):
        """Call handler unpacked signal parameters."""
        return self._handler(*parameters.unpack())


class DBusCallbackWithObjectPath(object):

    def __init__(self, handler):
        """Store reference to handler."""
        self._handler = handler

    def __call__(self,
                 connection,
                 sender_name,
                 object_path,
                 interface_name,
                 signal_name,
                 parameters,
                 *user_data):
        """Call handler with object_path and unpacked signal parameters."""
        return self._handler(object_path, *parameters.unpack())


class BusProxy(object):

    """
    Simple proxy class for a connected bus.

    :ivar Gio.DBusConnection connection:
    :ivar str bus_name:
    """

    def __init__(self, connection, bus_name):
        """
        Initialize member variables.

        :param Gio.DBusConnection connection:
        :param str bus_name:

        This performs IO at all.
        """
        self.connection = connection
        self.bus_name = bus_name

    def get_object(self, object_path):
        """
        Get a object representing the specified object.

        :param str object_path: object path
        :returns: a simple representative for the object
        :rtype: ObjectProxy
        """
        return ObjectProxy(self.connection, self.bus_name, object_path)

    def connect(self, interface, event, object_path, handler):
        """
        Connect to a DBus signal.

        :param str interface: interface name
        :param str event: event name
        :param str object_path: object path or ``None``
        :param handler: callback
        """
        if object_path:
            callback = DBusCallback(handler)
        else:
            callback = DBusCallbackWithObjectPath(handler)
        return self.connection.signal_subscribe(
            self.bus_name,
            interface,
            event,
            object_path,
            None,
            Gio.DBusSignalFlags.NONE,
            callback,
            None,
        )

    def disconnect(self, subscription_id):
        """
        Disconnect a DBus signal subscription.
        """
        self.connection.signal_unsubscribe(subscription_id)


class DBusService(object):

    """
    Abstract base class for UDisksX service wrapper classes.
    """

    @classmethod
    def connect_service(cls):
        """
        Connect to the service object on DBus.

        :returns: new proxy object for the service
        :rtype: InterfaceProxy
        :raises BusException: if unable to connect to service.
        """
        return InterfaceProxy(Gio.DBusProxy.new_for_bus_sync(
            Gio.BusType.SYSTEM,
            Gio.DBusProxyFlags.NONE,
            info=None,
            name=cls.BusName,
            object_path=cls.ObjectPath,
            interface_name=cls.Interface,
            cancellable=None,
        ))
