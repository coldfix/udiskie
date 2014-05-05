"""
Config utilities.

For an example config file, see the manual. If you don't have the man page
installed, a raw version is available in doc/udiskie.8.txt.
"""

import logging
import os
import yaml

from udiskie.compat import basestring


__all__ = ['DeviceFilter',
           'FilterMatcher',
           'Config']


def lower(s):
    try:
        return s.lower()
    except AttributeError:
        return s


class DeviceFilter(object):

    """Associate a certain value to matching devices."""

    VALID_PARAMETERS = {
        'fstype': 'id_type',
        'uuid': 'id_uuid' }

    def __init__(self, match, value):
        """
        Construct an instance.

        :param dict match: device attributes
        :param list value: value
        """
        self._log = logging.getLogger(__name__)
        self._match = {self.VALID_PARAMETERS[k]: v for k, v in match.items()}
        self._value = value
        self._log.debug('%s created' % self)

    def __str__(self):
        return ('{}(match={!r}, value={!r})'
                .format(self.__class__.__name__,
                        self._match, self._value))

    def match(self, device):
        """
        Check if the device matches this filter.

        :param Device device: device to be checked
        """
        return all(lower(getattr(device, k)) == lower(v)
                   for k, v in self._match.items())

    def value(self, device):
        """
        Get the associated value.

        :param Device device: matched device

        If :meth:`match` is False for the device, the return value of this
        method is undefined.
        """
        self._log.debug('%s used for %s' % (self, device.object_path))
        return self._value


class MountOptions(DeviceFilter):

    """Associate a list of mount options to matched devices."""

    def __init__(self, config_item):
        """Parse the MountOptions filter from the config item."""
        config_item = config_item.copy()
        options = config_item.pop('options')
        if isinstance(options, basestring):
            options = [o.strip() for o in options.split(',')]
        super(MountOptions, self).__init__(config_item, options)


class IgnoreDevice(DeviceFilter):

    """Associate a boolean ignore flag to matched devices."""

    def __init__(self, config_item):
        """Parse the IgnoreDevice filter from the config item."""
        config_item = config_item.copy()
        ignore = config_item.pop('ignore', True)
        super(IgnoreDevice, self).__init__(config_item, ignore)


class FilterMatcher(object):

    """Matches devices against multiple `DeviceFilter`s."""

    def __init__(self, filters, default):
        """
        Construct a FilterMatcher instance from list of DeviceFilter.

        :param list filters:
        """
        self._filters = list(filters)
        self._default = default

    def __call__(self, device):
        """
        Matches devices against multiple :class:`DeviceFilter`s.

        :param default: default value
        :param list filters: device filters
        :param Device device: device to be mounted
        :returns: value of the first matching filter
        """
        matches = (f.value(device) for f in self._filters if f.match(device))
        return next(matches, self._default)


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
    def mount_options(self):
        """Get a MountOptions filter list from the config data."""
        config_list = self._data.get('mount_options', [])
        return FilterMatcher(map(MountOptions, config_list), None)

    @property
    def ignore_device(self):
        """Get a IgnoreDevice filter list from the config data"""
        config_list = self._data.get('ignore_device', [])
        return FilterMatcher(map(IgnoreDevice, config_list), False)

    @property
    def program_options(self):
        """Get the program options dictionary from the config file."""
        return self._data.get('program_options', {})

    @property
    def notifications(self):
        """Get the notification timeouts dictionary from the config file."""
        return self._data.get('notifications', {})
