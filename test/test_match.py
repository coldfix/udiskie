# encoding: utf-8
"""
Tests for the udiskie.match module.

These tests are intended to demonstrate and ensure the correct usage of the
config file used by udiskie for custom device options.

"""
import unittest

import os.path

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
    config_file = os.path.join(os.path.dirname(__file__), '..',
                               'udiskie', 'config_example.py')

    def setUp(self):
        """Create a temporary config file."""
        self.config = Config.from_config_file(self.config_file)
        self.filter_matcher = self.config.mount_option_filter

    def test_ignored(self):
        """Test the FilterMatcher.is_ignored() method."""
        self.assertFalse(
            self.filter_matcher.is_ignored(
                TestDev('/vfat-0', 'vfat', 'abcd-ef00')))
        self.assertTrue(
            self.filter_matcher.is_ignored(
                TestDev('/vfat-1', 'vfat', 'abcd-ef01')))

    try:
        unittest.TestCase.assertItemsEqual
    except AttributeError:
        assertItemsEqual = unittest.TestCase.assertCountEqual

    def test_options(self):
        """Test the FilterMatcher.get_mount_options() method."""
        # only the first uuid OptionFilter should be used:
        self.assertItemsEqual(
            ['ro', 'noexec'],
            self.filter_matcher.get_mount_options(
                TestDev('/vfat-0', 'vfat', 'abcd-ef00')))
        self.assertItemsEqual(
            ['ro', 'noexec'],
            self.filter_matcher.get_mount_options(
                TestDev('/ext-0', 'ext', 'abcd-ef00')))
        # only the id_type OptionFilter should be used:
        self.assertItemsEqual(
            ['nosync'],
            self.filter_matcher.get_mount_options(
                TestDev('/vfat-unknown', 'vfat', 'no-matching-id')))
        self.assertItemsEqual(
            [],
            self.filter_matcher.get_mount_options(
                TestDev('/ext-unknown', 'ext', 'no-matching-id')))
