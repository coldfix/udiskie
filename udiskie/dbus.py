"""
Common DBus utilities.
"""

from __future__ import absolute_import
from __future__ import unicode_literals

import sys
from functools import partial

from gi.repository import Gio
from gi.repository import GLib

from .async_ import Async, Coroutine, Return
from .common import format_exc


__all__ = [
    'InterfaceProxy',
    'PropertiesProxy',
    'ObjectProxy',
    'BusProxy',
    'connect_service',
    'MethodsProxy',
]


if sys.version_info >= (3,):
    unpack_variant = GLib.Variant.unpack

else:
    dict_type = GLib.VariantType.new('a{?*}')

    def unpack_variant(v):
        """Unpack a GLib.Variant."""
        if v.get_type_string() in 'sog':
            return v.get_string().decode('utf-8')
        t = v.get_type()
        if t.is_basic():
            return v.unpack()
        elems = [v.get_child_value(i) for i in range(v.n_children())]
        if t.is_subtype_of(dict_type):
            return dict(map(unpack_variant, elems))
        if t.is_tuple():
            return tuple(map(unpack_variant, elems))
        if t.is_array():
            return list(map(unpack_variant, elems))
        if t.is_dict_entry():
            return list(map(unpack_variant, elems))
        # The following cases should never occur for DBus data:
        if t.is_variant():
            return unpack_variant(elems[0])
        if t.is_maybe():
            return unpack_variant(elems[0]) if elems else None
        raise ValueError("Unknown variant type: {}!".format(v.get_type_string()))


class DBusCall(Async):

    """
    Asynchronously call a DBus method.
    """

    def __init__(self,
                 proxy,
                 method_name,
                 signature,
                 args,
                 flags=0,
                 timeout_msec=-1):
        """
        Asynchronously call the specified method on a DBus proxy object.

        :param Gio.DBusProxy proxy:
        :param str method_name:
        :param str signature:
        :param tuple args:
        :param int flags:
        :param int timeout_msec:
        """
        cancellable = None
        user_data = None
        proxy.call(
            method_name,
            GLib.Variant(signature, tuple(args)),
            flags,
            timeout_msec,
            cancellable,
            self._callback,
            user_data,
        )

    def _callback(self, proxy, result, user_data):
        """
        Handle call result.

        :param Gio.DBusProxy proxy:
        :param Gio.AsyncResult result:
        :param user_data: unused
        """
        try:
            value = proxy.call_finish(result)
        except Exception as e:
            self.errback(e, format_exc())
        else:
            self.callback(*unpack_variant(value))


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

    def __init__(self, proxy):
        """
        Initialize property and method attribute accessors for the interface.

        :param Gio.DBusProxy proxy: accessed object
        :param str interface: accessed interface
        """
        self._proxy = proxy
        self.object_path = proxy.get_object_path()

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

    def call(self, method_name, signature='()', *args):
        return DBusCall(self._proxy, method_name, signature, args)


class PropertiesProxy(InterfaceProxy):

    Interface = 'org.freedesktop.DBus.Properties'

    def __init__(self, proxy, interface_name=None):
        super(PropertiesProxy, self).__init__(proxy)
        self.interface_name = interface_name

    def GetAll(self, interface_name=None):
        return self.call('GetAll', '(s)',
                         interface_name or self.interface_name)


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
        return DBusProxyNew(
            self.connection,
            Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES |
            Gio.DBusProxyFlags.DO_NOT_CONNECT_SIGNALS,
            info=None,
            name=self.bus_name,
            object_path=self.object_path,
            interface_name=name,
        )

    @Coroutine.from_generator_function
    def get_interface(self, name):
        """
        Get an interface proxy for this Dbus object.

        :param str name: interface name
        :returns: a proxy object for the other interface
        :rtype: InterfaceProxy
        """
        proxy = yield self._get_interface(name)
        yield Return(InterfaceProxy(proxy))

    @Coroutine.from_generator_function
    def get_property_interface(self, interface_name=None):
        proxy = yield self._get_interface(PropertiesProxy.Interface)
        yield Return(PropertiesProxy(proxy, interface_name))

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

    @Coroutine.from_generator_function
    def call(self, interface_name, method_name, signature='()', *args):
        proxy = yield self.get_interface(interface_name)
        result = yield proxy.call(method_name, signature, *args)
        yield Return(result)


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
        return self._handler(*unpack_variant(parameters))


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
        return self._handler(object_path, *unpack_variant(parameters))


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


class DBusProxyNew(Async):

    """
    Asynchronously call a DBus method.
    """

    def __init__(self,
                 connection,
                 flags,
                 info,
                 name,
                 object_path,
                 interface_name):
        """
        Asynchronously call the specified method on a DBus proxy object.
        """
        cancellable = None
        user_data = None
        Gio.DBusProxy.new(
            connection,
            flags,
            info,
            name,
            object_path,
            interface_name,
            cancellable,
            self._callback,
            user_data,
        )

    def _callback(self, proxy, result, user_data):
        """
        Handle call result.

        :param Gio.DBusProxy proxy:
        :param Gio.AsyncResult result:
        :param user_data: unused
        """
        try:
            value = Gio.DBusProxy.new_finish(result)
            if value is None:
                raise RuntimeError("Failed to connect DBus object!")
        except Exception as e:
            self.errback(e, format_exc())
        else:
            self.callback(value)


class DBusProxyNewForBus(Async):

    """
    Asynchronously call a DBus method.
    """

    def __init__(self,
                 bus_type,
                 flags,
                 info,
                 name,
                 object_path,
                 interface_name):
        """
        Asynchronously call the specified method on a DBus proxy object.
        """
        cancellable = None
        user_data = None
        Gio.DBusProxy.new_for_bus(
            bus_type,
            flags,
            info,
            name,
            object_path,
            interface_name,
            cancellable,
            self._callback,
            user_data,
        )

    def _callback(self, proxy, result, user_data):
        """
        Handle call result.

        :param Gio.DBusProxy proxy:
        :param Gio.AsyncResult result:
        :param user_data: unused
        """
        try:
            value = Gio.DBusProxy.new_for_bus_finish(result)
            if value is None:
                raise RuntimeError("Failed to connect DBus object!")
        except Exception as e:
            self.errback(e, format_exc())
        else:
            self.callback(value)


@Coroutine.from_generator_function
def connect_service(cls):
    """
    Connect to the service object on DBus.

    :returns: new proxy object for the service
    :rtype: InterfaceProxy
    :raises BusException: if unable to connect to service.
    """
    proxy = yield DBusProxyNewForBus(
        Gio.BusType.SYSTEM,
        Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES |
        Gio.DBusProxyFlags.DO_NOT_CONNECT_SIGNALS,
        info=None,
        name=cls.BusName,
        object_path=cls.ObjectPath,
        interface_name=cls.Interface,
    )
    yield Return(InterfaceProxy(proxy))


class MethodsProxy(object):

    """Provide methods as attributes for one interface of a DBus object."""

    def __init__(self, object_proxy, interface_name):
        """Initialize from (ObjectProxy, str)."""
        self._object_proxy = object_proxy
        self._interface_name = interface_name

    def __getattr__(self, name):
        """Get a proxy for the specified method on this interface."""
        return partial(self._object_proxy.call, self._interface_name, name)
