# encoding: utf-8
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

from udiskie.config import Config

class TestDev(object):
    def __init__(self, object_path, id_type, id_uuid):
        self.object_path = object_path
        self.id_type = id_type
        self.id_uuid = id_uuid

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

        config = Config.from_file(self.config_file)
        self.mount_options = config.mount_options
        self.ignore_device = config.ignore_device

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

