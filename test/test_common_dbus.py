"""
Tests for the udiskie.common module.

Since the tested classes are mainly a very light wrapper around the
dbus-python API the tests are not very comprehensive. In the hope that
python-dbus is tested thoroughly, we need only check that the wiring works
at all.

Still, the tests should be improved to have better defined behaviour.

"""
# test utility
import unittest
import dbus
import socket

# tested library:
from udiskie.common import DBusProxy


class TestDBusProxy(unittest.TestCase):
    """
    Test that the udiskie.common.DBusProxy class is working correctly.

    More specifically only the .method member is tested here. If the test
    fails this might be due to inavailability of the requested object.

    """
    def setUp(self):
        self.bus = dbus.SystemBus()
        self.obj = self.bus.get_object("org.freedesktop.DBus",
                                       "/org/freedesktop/DBus")
        self.proxy = DBusProxy(self.obj,
                               "org.freedesktop.DBus.Introspectable")

    def test_method_working(self):
        """Test that valid method call via the .method member will succeed."""
        self.assertTrue(
            isinstance(self.proxy.method.Introspect(), dbus.String))

    def test_method_failing(self):
        """Test that invalid method call will result in correct exception."""
        try:
            self.proxy.method.SurelyThisMethodDoesNotExistOnTheDBusObject()
        except self.proxy.Exception:
            pass
        else:
            assert False


class TestDBusProperty(unittest.TestCase):
    """
    Test the DBusProxy.property member (class DBusProperty).

    NOTE: this test may fail if org.freedesktop.hostname1 is not available.
    If you can come up with any standard dbus object containing properties,
    this test should be adapted!

    """
    def setUp(self):
        self.bus = dbus.SystemBus()
        self.obj = self.bus.get_object("org.freedesktop.hostname1",
                                       "/org/freedesktop/hostname1")
        self.proxy = DBusProxy(self.obj,
                               "org.freedesktop.hostname1")

    def test_property_working(self):
        """
        Test that the attribute access works as expected.

        This test may be somewhat risky:
        Is the hostname well-defined enough?

        """
        self.assertEqual(
            str(self.proxy.property.Hostname),
            socket.gethostname())

    def test_property_failing(self):
        """Test that invalid property access will result in exception."""
        try:
            self.proxy.property.SurelyThisPropertyDoesNotExistOnTheDBusObject
        except self.proxy.Exception:
            pass
        else:
            assert False

