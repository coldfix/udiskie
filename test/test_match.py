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

from udiskie.config import OptionFilter, Config

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
[mount_options]
uuid.ignored-device = __ignore__
uuid.device-with-options = noatime,nouser
fstype.vfat = ro,nouser''')

        self.filter_matcher = Config.from_config_file(self.config_file).filter_options
    
    def tearDown(self):
        """Remove the config file."""
        gc.collect()
        shutil.rmtree(self.base)

    def test_ignored(self):
        """Test the FilterMatcher.is_ignored() method."""
        self.assertTrue(
            self.filter_matcher.is_ignored(
                TestDev('/ignore', 'vfat', 'ignored-device')))
        self.assertFalse(
            self.filter_matcher.is_ignored(
                TestDev('/options', 'vfat', 'device-with-options')))
        self.assertFalse(
            self.filter_matcher.is_ignored(
                TestDev('/nomatch', 'vfat', 'no-matching-id')))

    try:
        unittest.TestCase.assertItemsEqual
    except AttributeError:
        assertItemsEqual = unittest.TestCase.assertCountEqual

    def test_options(self):
        """Test the FilterMatcher.get_mount_options() method."""
        self.assertItemsEqual(
            ['noatime', 'ro', 'nouser'],
            self.filter_matcher.get_mount_options(
                TestDev('/options', 'vfat', 'device-with-options')))
        self.assertItemsEqual(
            ['noatime', 'nouser'],
            self.filter_matcher.get_mount_options(
                TestDev('/optonly', 'ext', 'device-with-options')))
        self.assertItemsEqual(
            ['ro', 'nouser'],
            self.filter_matcher.get_mount_options(
                TestDev('/fsonly', 'vfat', 'no-matching-id')))
        self.assertItemsEqual(
            [],
            self.filter_matcher.get_mount_options(
                TestDev('/nomatch', 'ext', 'no-matching-id')))

