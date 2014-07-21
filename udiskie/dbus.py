"""
Common DBus utilities.
"""

from __future__ import absolute_import

from gi.repository import Gio
from gi.repository import GLib


__all__ = ['DBusProperties',
           'DBusProxy',
           'DBusObject',
           'DBusBus',
           'DBusService',
           'DBusException']


DBusException = GLib.GError


class DBusProperties(object):

    """
    Dbus property map abstraction.

    Wraps properties of a DBus interface on a DBus object as attributes.

    :ivar Gio.DBusProxy __proxy: proxy for the DBus.Properties interface
    :ivar str __interface: inspected interface name
    """

    def __init__(self, object, name):
        """
        Initialize a proxy object with standard DBus property interface.

        :param Gio.DBusObject object: accessed object
        :param str name: interface name
        """
        self.__proxy = object._get_interface(
            'org.freedesktop.DBus.Properties')
        self.__interface = name

    def __getattr__(self, key):
        """
        Retrieve the property via the DBus proxy.

        :param str key: name of the dbus property
        :returns: the property value
        """
        return self.__proxy.Get('(ss)', self.__interface, key)


class DBusProxy(object):

    """
    DBus proxy object for a specific interface.

    Provides attribute accessors to properties and methods of a DBus
    interface on a DBus object.

    :ivar str object_path: object path of the DBus object
    :ivar DBusProperties property: attribute access to DBus properties
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
        self.property = DBusProperties(self.object,
                                       proxy.get_interface_name())
        self.method = proxy

    @property
    def object(self):
        """
        Get a proxy for the underlying object.

        :rtype: DBusObject
        """
        proxy = self._proxy
        return DBusObject(proxy.get_connection(),
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


class DBusObject(object):

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

        This performs IO at all.
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
        :rtype: DBusProxy
        """
        return DBusProxy(self._get_interface(name))

    @property
    def bus(self):
        """
        Get a proxy object for the underlying bus.

        :rtype: DBusBus
        """
        return DBusBus(self.connection, self.bus_name)

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


class DBusBus(object):

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
        :rtype: DBusObject
        """
        return DBusObject(self.connection, self.bus_name, object_path)

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
        :rtype: DBusProxy
        :raises BusException: if unable to connect to service.
        """
        return DBusProxy(Gio.DBusProxy.new_for_bus_sync(
            Gio.BusType.SYSTEM,
            Gio.DBusProxyFlags.NONE,
            info=None,
            name=cls.BusName,
            object_path=cls.ObjectPath,
            interface_name=cls.Interface,
            cancellable=None,
        ))
