"""
Tests for the udiskie.common module.

Since the tested classes are mainly a very light wrapper around the
dbus-python API the tests are not very comprehensive. In the hope that
python-dbus is tested thoroughly, we need only check that the wiring works
at all.

"""
# test utility
import dbus
import dbusmock

# tested library:
from udiskie.common import DBusProxy


class TestDBusProxy(dbusmock.DBusTestCase):
    """
    Test that the udiskie.common.DBusProxy class is working correctly.

    More specifically the .method and the .property (class DBusProperties)
    members are tested to work as expected.

    """
    @classmethod
    def setUpClass(cls):
        cls.start_system_bus()
        cls.bus = cls.get_dbus(True)

    def setUp(self):
        self.srv = self.spawn_server('com.example.Simple',
                                     '/com/example/Simple',
                                     'com.example.Simple',
                                     system_bus=True)
        self.obj, = self.bus.get_object('com.example.Simple',
                                       '/com/example/Simple'),
        self.mock_prox = dbus.Interface(self.obj, dbusmock.MOCK_IFACE)
        self.mock_prox.AddMethod('', 'Square', 'i', 'i',
                                 'ret = args[0]*args[0]')
        self.mock_prox.AddProperty('', 'Foo', 'foo')
        self.mock_prox.AddProperty('', 'Bar', 'bar')
        self.prox = DBusProxy(self.obj, 'com.example.Simple')

    def tearDown(self):
        self.srv.terminate()
        self.srv.wait()

    def test_method_working(self):
        """Test that valid method call via the .method member will succeed."""
        self.assertEqual(self.prox.method.Square(3), 9)
        self.assertEqual(self.prox.method.Square(4), 16)

    def test_method_failing(self):
        """Test that invalid method call will result in correct exception."""
        try:
            self.prox.method.SurelyThisMethodDoesNotExistOnTheDBusObject()
        except self.prox.Exception:
            pass
        else:
            assert False

    def test_property_working(self):
        """Test that the attribute access works as expected."""
        self.assertEqual(str(self.prox.property.Foo), 'foo')
        self.assertEqual(str(self.prox.property.Bar), 'bar')

    def test_property_failing(self):
        """Test that invalid property access will result in exception."""
        try:
            self.prox.property.SurelyThisPropertyDoesNotExistOnTheDBusObject
        except self.prox.Exception:
            pass
        else:
            assert False

