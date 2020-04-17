"""
Config utilities.

For an example config file, see the manual. If you don't have the man page
installed, a raw version is available in doc/udiskie.8.txt.
"""

import logging
import os
import fnmatch

from .common import exc_message
from .locale import _


__all__ = ['DeviceFilter',
           'match_config',
           'Config']


def lower(s):
    try:
        return s.lower()
    except AttributeError:
        return s


def format_dict(d):
    return '{' + ', '.join([
        _format_item(k, v)
        for k, v in d.items()
    ]) + '}'


def _format_item(k, v):
    if isinstance(v, bool):
        return k if v else '!' + k
    else:
        return '{}={}'.format(k, v)


def match_value(value, pattern):
    if isinstance(value, (list, tuple)):
        return any(match_value(v, pattern) for v in value)
    if isinstance(value, str) and isinstance(pattern, str):
        return fnmatch.fnmatch(value.lower(), pattern.lower())
    return lower(value) == lower(pattern)


class DeviceFilter:

    """Associate a certain value to matching devices."""

    VALID_PARAMETERS = [
        'is_drive',
        'is_block',
        'is_partition_table',
        'is_partition',
        'is_filesystem',
        'is_luks',
        'is_loop',
        'is_toplevel',
        'is_detachable',
        'is_ejectable',
        'has_media',
        'device_file',
        'device_presentation',
        'device_size',
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
        'mount_path',
        'is_unlocked',
        'in_use',
        'should_automount',
        'ui_label',
        'loop_file',
        'setup_by_uid',
        'autoclear',
        'symlinks',
        'drive_model',
        'drive_vendor',
        'drive_label',
        'ui_device_label',
        'ui_device_presentation',
        'ui_id_label',
        'ui_id_uuid',
    ]

    def __init__(self, match):
        """Construct from dict of device matching attributes."""
        self._log = logging.getLogger(__name__)
        self._match = match = match.copy()
        self._values = {}
        # mount options:
        if 'options' in match:
            options = match.pop('options')
            if isinstance(options, str):
                options = [o.strip() for o in options.split(',')]
            self._values['options'] = options
        # ignore device:
        if 'ignore' in match:
            self._values['ignore'] = match.pop('ignore')
        # automount:
        if 'automount' in match:
            self._values['automount'] = match.pop('automount')
        # keyfile:
        if 'keyfile' in match:
            keyfile = match.pop('keyfile')
            keyfile = os.path.expandvars(keyfile)
            keyfile = os.path.expanduser(keyfile)
            self._values['keyfile'] = keyfile
        if 'skip' in match:
            self._values['skip'] = match.pop('skip')
        # the use of list() makes deletion inside the loop safe:
        for k in list(self._match):
            if k not in self.VALID_PARAMETERS:
                self._log.error(_('Unknown matching attribute: {!r}', k))
                del self._match[k]
        self._log.debug(_('new rule: {0}', self))

    def __str__(self):
        return _('{0} -> {1}',
                 format_dict(self._match),
                 format_dict(self._values))

    def match(self, device):
        """Check if the device object matches this filter."""
        return all(match_value(getattr(device, k), v)
                   for k, v in self._match.items())

    def has_value(self, kind):
        return kind in self._values

    def value(self, kind, device):
        """
        Get the value for the device object associated with this filter.

        If :meth:`match` is False for the device, the return value of this
        method is undefined.
        """
        self._log.debug(_('{0} matched {1}',
                          device.device_file or device.object_path, self))
        return self._values[kind]


class MountOptions(DeviceFilter):

    """Associate a list of mount options to matched devices."""

    def __init__(self, config_item):
        config_item.setdefault('options', None)
        super().__init__(config_item)


class IgnoreDevice(DeviceFilter):

    """Associate a boolean ignore flag to matched devices."""

    def __init__(self, config_item):
        config_item.setdefault('ignore', True)
        super().__init__(config_item)


def match_config(filters, device, kind, default):
    """
    Matches devices against multiple :class:`DeviceFilter`s.

    :param list filters: device filters
    :param Device device: device to be mounted
    :param str kind: value kind
    :param default: default value
    :returns: value of the first matching filter
    """
    while device is not None:
        for f in filters:
            if f.has_value(kind) and f.match(device):
                return f.value(kind, device)
            # 'skip' allows skipping further rules and directly moving on
            # lookup on the parent device:
            if f.has_value('skip') and f.match(device) and (
                    f.value('skip', device) in (True, 'all', kind)):
                break
        device = device.partition_slave or device.luks_cleartext_slave
    return default


class Config:

    """Udiskie config in memory representation."""

    def __init__(self, data):
        """Initialize with preparsed data dict."""
        self._data = data or {}

    @classmethod
    def default_pathes(cls):
        """Return the default config file paths as a list."""
        config_home = (
            os.environ.get('XDG_CONFIG_HOME') or
            os.path.expanduser('~/.config'))
        return [os.path.join(config_home, 'udiskie', 'config.yml'),
                os.path.join(config_home, 'udiskie', 'config.json')]

    @classmethod
    def from_file(cls, path=None):
        """
        Read YAML config file. Returns Config object.

        :raises IOError: if the path does not exist
        """
        # None => use default
        if path is None:
            for path in cls.default_pathes():
                try:
                    return cls.from_file(path)
                except IOError as e:
                    logging.getLogger(__name__).debug(
                        _("Failed to read config file: {0}", exc_message(e)))
                except ImportError as e:
                    logging.getLogger(__name__).warn(
                        _("Failed to read {0!r}: {1}", path, exc_message(e)))
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
    def device_config(self):
        device_config = map(DeviceFilter, self._data.get('device_config', []))
        mount_options = map(MountOptions, self._data.get('mount_options', []))
        ignore_device = map(IgnoreDevice, self._data.get('ignore_device', []))
        return list(device_config) + list(mount_options) + list(ignore_device)

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

    @property
    def quickmenu_actions(self):
        """Get the set of actions to be shown in the quickmenu (left-click)."""
        return self._data.get('quickmenu_actions', None)
