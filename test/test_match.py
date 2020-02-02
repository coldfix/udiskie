"""
Tests for the udiskie.match module.

These tests are intended to demonstrate and ensure the correct usage of the
config file used by udiskie for custom device options.
"""

import unittest

import tempfile
import shutil
import os.path
import gc

from udiskie.config import Config, match_config


class TestDev:

    def __init__(self, object_path, id_type, id_uuid):
        self.device_file = object_path
        self.id_type = id_type
        self.id_uuid = id_uuid
        self.partition_slave = None
        self.luks_cleartext_slave = None


class TestFilterMatcher(unittest.TestCase):

    """
    Tests for the udiskie.match.FilterMatcher class.
    """

    def setUp(self):
        """Create a temporary config file."""
        self.base = tempfile.mkdtemp()
        self.config_file = os.path.join(self.base, 'filters.conf')

        with open(self.config_file, 'wt') as f:
            f.write('''
mount_options:
- id_uuid: device-with-options
  options: noatime,nouser
- id_type: vfat
  options: ro,nouser

ignore_device:
- id_uuid: ignored-DEVICE
''')

        self.filters = Config.from_file(self.config_file).device_config

    def mount_options(self, device):
        return match_config(self.filters, device, 'options', None)

    def ignore_device(self, device):
        return match_config(self.filters, device, 'ignore', False)

    def tearDown(self):
        """Remove the config file."""
        gc.collect()
        shutil.rmtree(self.base)

    def test_ignored(self):
        """Test the FilterMatcher.is_ignored() method."""
        self.assertTrue(
            self.ignore_device(
                TestDev('/ignore', 'vfat', 'IGNORED-device')))
        self.assertFalse(
            self.ignore_device(
                TestDev('/options', 'vfat', 'device-with-options')))
        self.assertFalse(
            self.ignore_device(
                TestDev('/nomatch', 'vfat', 'no-matching-id')))

    def test_options(self):
        """Test the FilterMatcher.get_mount_options() method."""
        self.assertEqual(
            ['noatime', 'nouser'],
            self.mount_options(
                TestDev('/options', 'vfat', 'device-with-options')))
        self.assertEqual(
            ['noatime', 'nouser'],
            self.mount_options(
                TestDev('/optonly', 'ext', 'device-with-options')))
        self.assertEqual(
            ['ro', 'nouser'],
            self.mount_options(
                TestDev('/fsonly', 'vfat', 'no-matching-id')))
        self.assertEqual(
            None,
            self.mount_options(
                TestDev('/nomatch', 'ext', 'no-matching-id')))


if __name__ == '__main__':
    unittest.main()
