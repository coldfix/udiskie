"""
Config utilities.

For an example config file, see the manual. If you don't have the man page
installed, a raw version is available in doc/udiskie.8.txt.
"""

import logging
import os
import sys

from udiskie.compat import basestring
from udiskie.locale import _


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

    VALID_PARAMETERS = [
        'is_drive',
        'is_block',
        'is_partition_table',
        'is_partition',
        'is_filesystem',
        'is_luks',
        'is_toplevel',
        'is_detachable',
        'is_ejectable',
        'has_media',
        'device_file',
        'device_presentation',
        'device_id',
        'id_usage',
        'is_crypto',
        'is_ignored',
        'id_type',
        'id_label',
        'id_uuid',
        'is_luks_cleartext',
        'is_external',
        'is_systeminternal',
        'is_mounted',
        'mount_paths',
        'is_unlocked',
        'in_use',
        'should_automount',
    ]

    def __init__(self, match, value):
        """
        Construct an instance.

        :param dict match: device attributes
        :param list value: value
        """
        self._log = logging.getLogger(__name__)
        self._match = match.copy()
        # the use of keys() makes deletion inside the loop safe:
        for k in self._match.keys():
            if k not in self.VALID_PARAMETERS:
                self._log.warn(_('Unknown matching attribute: {!r}', k))
                del self._match[k]
        self._value = value
        self._log.debug(_('{0} created', self))

    def __str__(self):
        return _('{0}(match={1!r}, value={2!r})',
                 self.__class__.__name__,
                 self._match,
                 self._value)

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
        self._log.debug(_('{0} used for {1}', self, device.object_path))
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
    def default_pathes(cls):
        """
        Return the default config file pathes.

        :rtype: list
        """
        try:
            from xdg.BaseDirectory import xdg_config_home as config_home
        except ImportError:
            config_home = os.path.expanduser('~/.config')
        return [os.path.join(config_home, 'udiskie', 'config.yml'),
                os.path.join(config_home, 'udiskie', 'config.json')]

    @classmethod
    def from_file(cls, path=None):
        """
        Read config file.

        :param str path: YAML config file name
        :returns: configuration object
        :rtype: Config
        :raises IOError: if the path does not exist
        """
        # None => use default
        if path is None:
            for path in cls.default_pathes():
                try:
                    return cls.from_file(path)
                except IOError:
                    logging.getLogger(__name__).debug(
                        "Failed to read config file: {0}"
                        .format(sys.exc_info()[1]))
                except ImportError:
                    logging.getLogger(__name__).warn(
                        "Failed to read {0!r}: {1}"
                        .format(path, sys.exc_info()[1]))
            return cls({})
        # False/'' => no config
        if not path:
            return cls({})
        if os.path.splitext(path)[1].lower() == '.json':
            from json import load
        else:
            from yaml import safe_load as load
        with open(path) as f:
            return cls(load(f))

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
        return self._data.get('program_options', {}).copy()

    @property
    def notifications(self):
        """Get the notification timeouts dictionary from the config file."""
        return self._data.get('notifications', {}).copy()

    @property
    def icon_names(self):
        """Get the icon names dictionary from the config file."""
        return self._data.get('icon_names', {}).copy()

    @property
    def notification_actions(self):
        """Get the notification actions dictionary from the config file."""
        return self._data.get('notification_actions', {}).copy()
