"""
Config utilities.

For an example config file, see the manual. If you don't have the man page
installed, a raw version is available in doc/udiskie.8.txt.
"""

import logging
import os
import yaml

from udiskie.compat import basestring


__all__ = ['OptionFilter',
           'FilterMatcher',
           'Config']


class OptionFilter(object):

    """Specify mount options for matching devices."""

    VALID_PARAMETERS = {
        'fstype': 'id_type',
        'uuid': 'id_uuid' }

    def __init__(self, match, options):
        """
        Construct an instance.

        :param dict match: device attributes
        :param list options: mount options for matching devices
        """
        self._log = logging.getLogger(__name__)
        self._match = match
        self._options = options
        self._log.debug('%s created' % self)

    @classmethod
    def from_config_item(cls, config_item):
        """
        Construct an instance from an entry in a config file.

        :param dict config_item:
        """
        match = {internal_name: config_item[public_name]
                 for public_name, internal_name in cls.VALID_PARAMETERS.items()
                 if public_name in config_item}
        options = config_item['options']
        if isinstance(options, basestring):
            options = [o.strip() for o in options.split(',')]
        return cls(match, options)

    def __str__(self):
        return ('<OptionFilter match={!r}: options={!r}>'
                .format(self._match, self._options))

    def match(self, device):
        """
        Check if the device matches this filter.

        :param Device device: device to be checked
        """
        return all(getattr(device, k) == v
                   for k, v in self._match.items())

    def get_options(self, device):
        """
        Get list of mount options for the device.

        :param Device device: matched device

        If :meth:`match` is False for the device, the return value of this
        method is undefined.
        """
        self._log.debug('%s used for %s' % (self, device.object_path))
        return self._options


class FilterMatcher(object):

    """Matches devices against multiple `OptionFilter`s."""

    def __init__(self, filters):
        """
        Construct a FilterMatcher instance from list of OptionFilters.

        :param list filters: list of callable(Device) -> list
        """
        self._filters = list(filters)

    @classmethod
    def from_config_section(cls, config_section):
        """
        Construct a FilterMatcher instance from config file section.

        :param string config_section: list of config items
        """
        return cls(map(OptionFilter.from_config_item, config_section))

    def get_mount_options(self, device):
        """
        Retrieve list of mount options for device.

        :param Device device: device to be mounted
        :returns: mount options
        :rtype: list
        """
        matching_mount_options = (filt.get_options(device)
                                  for filt in self._filters
                                  if filt.match(device))
        return next(iter(matching_mount_options), [])

    def is_ignored(self, device):
        """
        Check if the device should be ignored by udiskie.

        :param Device device: device to be checked
        :returns: if the device should be ignored
        :rtype: bool
        """
        return any('__ignore__' in filt.get_options(device)
                   for filt in self._filters
                   if filt.match(device))


class Config(object):

    """Udiskie config in memory representation."""

    def __init__(self, data):
        """
        Initialize with preparsed data object.

        :param ConfigParser data: config file accessor
        """
        self._data = data

    @classmethod
    def default_path(cls):
        """
        Return the default config file path.

        :rtype: str
        """
        try:
            from xdg.BaseDirectory import xdg_config_home as config_home
        except ImportError:
            config_home = os.path.expanduser('~/.config')
        return os.path.join(config_home, 'udiskie', 'config.yml')

    @classmethod
    def from_file(cls, path=None):
        """
        Read config file.

        :param str path: YAML config file name
        :returns: configuration object
        :rtype: Config
        """
        try:
            with open(path or cls.default_path()) as f:
                return cls(yaml.safe_load(f))
        except IOError:
            return cls({})

    @property
    def filter_options(self):
        """Get a :class:`FilterMatcher` instance from the config data."""
        return FilterMatcher.from_config_section(
            self._data.get('mount_options', []))

    @property
    def program_options(self):
        """Get the program options dictionary from the config file."""
        return self._data.get('program_options', {})

    @property
    def notifications(self):
        """Get the notification timeouts dictionary from the config file."""
        return self._data.get('notifications', {})
