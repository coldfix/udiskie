"""
Tests for the udiskie.keyutils wrapper.
"""

import unittest
import time

import udiskie.keyutils as keyutils


class TestKeyutils(unittest.TestCase):

    """
    Tests for the udiskie.keyutils wrapper.
    """

    # NOTE: The key names are different in each test so that they do not
    # interfere accidentally.

    def setUp(self):
        keyutils.clear()

    def test_add_request_read(self):
        """The cached password expires after the specified timeout."""
        key = b'ALPHA'
        val = '{<}hëllo ωορλδ!{>}'.encode('utf-8')
        key_id = keyutils.add_key(key, val)
        self.assertEqual(keyutils.request_key(key), key_id)
        self.assertEqual(keyutils.read_key(key_id), val)

    def test_touch(self):
        """Key access refreshes the timeout."""
        key = b'BETA'
        val = '{<}hëllo ωορλδ!{>}'.encode('utf-8')
        key_id = keyutils.add_key(key, val)
        self.assertEqual(keyutils.request_key(key), key_id)
        self.assertEqual(keyutils.read_key(key_id), val)

        keyutils.set_timeout(key_id, 3)
        time.sleep(1)
        self.assertEqual(keyutils.read_key(key_id), val)

        keyutils.set_timeout(key_id, 3)
        time.sleep(2)
        self.assertEqual(keyutils.read_key(key_id), val)

        keyutils.set_timeout(key_id, 3)
        time.sleep(4)
        with self.assertRaises(keyutils.KeyExpired):
            keyutils.read_key(key_id)

    def test_revoke(self):
        """A key can be deleted manually."""
        key = b'GAMMA'
        val = '{<}hëllo ωορλδ!{>}'.encode('utf-8')
        key_id = keyutils.add_key(key, val)
        self.assertEqual(keyutils.request_key(key), key_id)
        self.assertEqual(keyutils.read_key(key_id), val)

        keyutils.revoke(key_id)
        with self.assertRaises(keyutils.KeyRevoked):
            keyutils.read_key(key_id)

    def test_update(self):
        key = b'DELTA'
        val = '{<}hëllo ωορλδ!{>}'.encode('utf-8')
        key_id = keyutils.add_key(key, val)
        self.assertEqual(keyutils.request_key(key), key_id)
        self.assertEqual(keyutils.read_key(key_id), val)

        key_id = keyutils.add_key(key, val + val)
        self.assertEqual(keyutils.request_key(key), key_id)
        self.assertEqual(keyutils.read_key(key_id), val + val)

        keyutils.revoke(key_id)
        with self.assertRaises(keyutils.KeyRevoked):
            keyutils.read_key(key_id)

    def test_clear(self):
        key1 = b'eps'
        key2 = b'tau'
        val1 = b'hello'
        val2 = b'world'
        id1 = keyutils.add_key(key1, val1)
        id2 = keyutils.add_key(key2, val2)
        self.assertEqual(keyutils.request_key(key1), id1)
        self.assertEqual(keyutils.request_key(key2), id2)
        self.assertEqual(keyutils.read_key(id1), val1)
        self.assertEqual(keyutils.read_key(id2), val2)

        keyutils.clear()
        with self.assertRaises(keyutils.KeyutilsError):
            keyutils.read_key(id1)
        with self.assertRaises(keyutils.KeyutilsError):
            keyutils.read_key(id2)


if __name__ == '__main__':
    unittest.main()
