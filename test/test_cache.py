# encoding: utf-8
"""
Tests for the udiskie.cache module.
"""

from __future__ import unicode_literals

import unittest
import time

from udiskie.cache import PasswordCache


class TestDev(object):

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
        self.assertEqual(cache[device], password)
        time.sleep(1.5)
        with self.assertRaises(KeyError):
            _ = cache[device]

    def test_touch(self):
        """Key access refreshes the timeout."""
        device = TestDev('BETA')
        password = '{<}hëllo ωορλδ!{>}'
        cache = PasswordCache(3)
        cache[device] = password
        time.sleep(2)
        self.assertEqual(cache[device], password)
        time.sleep(2)
        self.assertEqual(cache[device], password)
        time.sleep(4)
        with self.assertRaises(KeyError):
            _ = cache[device]

    def test_revoke(self):
        """A key can be deleted manually."""
        device = TestDev('GAMMA')
        password = '{<}hëllo ωορλδ!{>}'
        cache = PasswordCache(0)
        cache[device] = password
        self.assertEqual(cache[device], password)
        del cache[device]
        with self.assertRaises(KeyError):
            _ = cache[device]

    def test_update(self):
        device = TestDev('DELTA')
        password = '{<}hëllo ωορλδ!{>}'
        cache = PasswordCache(0)
        cache[device] = password
        self.assertEqual(cache[device], password)
        cache[device] = password * 2
        self.assertEqual(cache[device], password*2)
        del cache[device]
        with self.assertRaises(KeyError):
            _ = cache[device]


if __name__ == '__main__':
    unittest.main()
