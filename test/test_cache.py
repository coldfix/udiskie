"""
Tests for the udiskie.cache module.
"""

import unittest
import time

from udiskie.cache import PasswordCache


class TestDev:

    def __init__(self, id_uuid):
        self.id_uuid = id_uuid


class TestPasswordCache(unittest.TestCase):

    """
    Tests for the udiskie.cache.PasswordCache class.
    """

    # NOTE: The device names are different in each test so that they do not
    # interfere accidentally.

    def test_timeout(self):
        """The cached password expires after the specified timeout."""
        device = TestDev('ALPHA')
        password = '{<}hëllo ωορλδ!{>}'
        cache = PasswordCache(1)
        cache[device] = password
        self.assertEqual(cache[device], password.encode('utf-8'))
        time.sleep(1.5)
        with self.assertRaises(KeyError):
            cache[device]

    def test_touch(self):
        """Key access refreshes the timeout."""
        device = TestDev('BETA')
        password = '{<}hëllo ωορλδ!{>}'
        cache = PasswordCache(3)
        cache[device] = password
        time.sleep(2)
        self.assertEqual(cache[device], password.encode('utf-8'))
        time.sleep(2)
        self.assertEqual(cache[device], password.encode('utf-8'))
        time.sleep(4)
        with self.assertRaises(KeyError):
            cache[device]

    def test_revoke(self):
        """A key can be deleted manually."""
        device = TestDev('GAMMA')
        password = '{<}hëllo ωορλδ!{>}'
        cache = PasswordCache(0)
        cache[device] = password
        self.assertEqual(cache[device], password.encode('utf-8'))
        del cache[device]
        with self.assertRaises(KeyError):
            cache[device]

    def test_update(self):
        device = TestDev('DELTA')
        password = '{<}hëllo ωορλδ!{>}'
        cache = PasswordCache(0)
        cache[device] = password
        self.assertEqual(cache[device], password.encode('utf-8'))
        cache[device] = password * 2
        self.assertEqual(cache[device], password.encode('utf-8')*2)
        del cache[device]
        with self.assertRaises(KeyError):
            cache[device]


if __name__ == '__main__':
    unittest.main()
