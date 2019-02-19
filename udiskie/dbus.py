"""
Common DBus utilities.
"""

from functools import partial

from gi.repository import Gio
from gi.repository import GLib

from .async_ import gio_callback, pack, Future


__all__ = [
    'InterfaceProxy',
    'PropertiesProxy',
    'ObjectProxy',
    'BusProxy',
    'connect_service',
    'MethodsProxy',
]


unpack_variant = GLib.Variant.unpack


async def call(proxy, method_name, signature, args, flags=0, timeout_msec=-1):
    """
    Asynchronously call the specified method on a DBus proxy object.

    :param Gio.DBusProxy proxy:
    :param str method_name:
    :param str signature:
    :param tuple args:
    :param int flags:
    :param int timeout_msec:
    """
    future = Future()
    cancellable = None
    proxy.call(
        method_name,
        GLib.Variant(signature, tuple(args)),
        flags,
        timeout_msec,
        cancellable,
        gio_callback,
        future,
    )
    result = await future
    value = proxy.call_finish(result)
    return pack(*unpack_variant(value))


async def call_with_fd_list(proxy, method_name, signature, args, fds,
                            flags=0, timeout_msec=-1):
    """
    Asynchronously call the specified method on a DBus proxy object.

    :param Gio.DBusProxy proxy:
    :param str method_name:
    :param str signature:
    :param tuple args:
    :param list fds:
    :param int flags:
    :param int timeout_msec:
    """
    future = Future()
    cancellable = None
    fd_list = Gio.UnixFDList.new_from_array(fds)
    proxy.call_with_unix_fd_list(
        method_name,
        GLib.Variant(signature, tuple(args)),
        flags,
        timeout_msec,
        fd_list,
        cancellable,
        gio_callback,
        future,
    )
    result = await future
    value, fds = proxy.call_with_unix_fd_list_finish(result)
    return pack(*unpack_variant(value))


class InterfaceProxy:

    """
    DBus proxy object for a specific interface.

    :ivar str object_path: object path of the DBus object
    :ivar Gio.DBusProxy _proxy: underlying proxy object
    """

    def __init__(self, proxy):
        """
        Initialize property and method attribute accessors for the interface.

        :param Gio.DBusProxy proxy: accessed object
        """
        self._proxy = proxy
        self.object_path = proxy.get_object_path()

    @property
    def object(self):
        """Get an ObjectProxy instanec for the underlying object."""
        proxy = self._proxy
        return ObjectProxy(proxy.get_connection(),
                           proxy.get_name(),
                           proxy.get_object_path())

    def connect(self, event, handler):
        """Connect to a DBus signal, returns subscription id (int)."""
        interface = self._proxy.get_interface_name()
        return self.object.connect(interface, event, handler)

    def call(self, method_name, signature='()', *args):
        return call(self._proxy, method_name, signature, args)


class PropertiesProxy(InterfaceProxy):

    Interface = 'org.freedesktop.DBus.Properties'

    def __init__(self, proxy, interface_name=None):
        super().__init__(proxy)
        self.interface_name = interface_name

    def GetAll(self, interface_name=None):
        return self.call('GetAll', '(s)',
                         interface_name or self.interface_name)


class ObjectProxy:

    """Simple proxy class for a DBus object."""

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
        """Get a Future(Gio.DBusProxy) for the specified interface."""
        return proxy_new(
            self.connection,
            Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES |
            Gio.DBusProxyFlags.DO_NOT_CONNECT_SIGNALS,
            info=None,
            name=self.bus_name,
            object_path=self.object_path,
            interface_name=name,
        )

    async def get_interface(self, name):
        """Get an InterfaceProxy for the specified interface."""
        proxy = await self._get_interface(name)
        return InterfaceProxy(proxy)

    async def get_property_interface(self, interface_name=None):
        proxy = await self._get_interface(PropertiesProxy.Interface)
        return PropertiesProxy(proxy, interface_name)

    @property
    def bus(self):
        """Get a BusProxy for the underlying bus."""
        return BusProxy(self.connection, self.bus_name)

    def connect(self, interface, event, handler):
        """Connect to a DBus signal. Returns subscription id (int)."""
        object_path = self.object_path
        return self.bus.connect(interface, event, object_path, handler)

    async def call(self, interface_name, method_name, signature='()', *args):
        proxy = await self.get_interface(interface_name)
        result = await proxy.call(method_name, signature, *args)
        return result


class BusProxy:

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
        """Get an ObjectProxy representing the specified object."""
        return ObjectProxy(self.connection, self.bus_name, object_path)

    def connect(self, interface, event, object_path, handler):
        """
        Connect to a DBus signal. If ``object_path`` is None, subscribe for
        all objects and invoke the callback with the object_path as its first
        argument.
        """
        if object_path:
            def callback(connection, sender_name, object_path,
                         interface_name, signal_name, parameters):
                return handler(*unpack_variant(parameters))
        else:
            def callback(connection, sender_name, object_path,
                         interface_name, signal_name, parameters):
                return handler(object_path, *unpack_variant(parameters))
        return self.connection.signal_subscribe(
            self.bus_name,
            interface,
            event,
            object_path,
            None,
            Gio.DBusSignalFlags.NONE,
            callback,
        )

    def disconnect(self, subscription_id):
        """Disconnect a DBus signal subscription."""
        self.connection.signal_unsubscribe(subscription_id)


async def proxy_new(connection, flags, info, name, object_path, interface_name):
    """Asynchronously call the specified method on a DBus proxy object."""
    future = Future()
    cancellable = None
    Gio.DBusProxy.new(
        connection,
        flags,
        info,
        name,
        object_path,
        interface_name,
        cancellable,
        gio_callback,
        future,
    )
    result = await future
    value = Gio.DBusProxy.new_finish(result)
    if value is None:
        raise RuntimeError("Failed to connect DBus object!")
    return value


async def proxy_new_for_bus(bus_type, flags, info, name, object_path,
                            interface_name):
    """Asynchronously call the specified method on a DBus proxy object."""
    future = Future()
    cancellable = None
    Gio.DBusProxy.new_for_bus(
        bus_type,
        flags,
        info,
        name,
        object_path,
        interface_name,
        cancellable,
        gio_callback,
        future,
    )
    result = await future
    value = Gio.DBusProxy.new_for_bus_finish(result)
    if value is None:
        raise RuntimeError("Failed to connect DBus object!")
    return value


async def connect_service(bus_name, object_path, interface):
    """Connect to the service object on DBus, return InterfaceProxy."""
    proxy = await proxy_new_for_bus(
        Gio.BusType.SYSTEM,
        Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES |
        Gio.DBusProxyFlags.DO_NOT_CONNECT_SIGNALS,
        info=None,
        name=bus_name,
        object_path=object_path,
        interface_name=interface,
    )
    return InterfaceProxy(proxy)


class MethodsProxy:

    """Provide methods as attributes for one interface of a DBus object."""

    def __init__(self, object_proxy, interface_name):
        """Initialize from (ObjectProxy, str)."""
        self._object_proxy = object_proxy
        self._interface_name = interface_name

    def __getattr__(self, name):
        """Get a proxy for the specified method on this interface."""
        return partial(self._object_proxy.call, self._interface_name, name)
