"""
Filters for udiskie mount tools.

Used to communicate user configuration to udiskie. At the moment user
configuration can be used to ignore certain devices or add mount options.

"""
__all__ = ['InvalidFilter',
           'OptionFilter',
           'FilterMatcher',
           'Config']

try:                    # python2
    from ConfigParser import SafeConfigParser, NoSectionError
except ImportError:     # python3
    from configparser import SafeConfigParser, NoSectionError

import os
import re
import logging
from itertools import chain

class InvalidFilter(ValueError):
    """Inappropriate filter configuration entry."""

class OptionFilter(object):
    """Add a list of mount options for matching devices."""
    VALID_PARAMETERS = {
        'fstype': 'id_type',
        'uuid': 'id_uuid' }

    def __init__(self, key, value, options):
        """
        Construct an instance.

        :param string key: match key; one of 'fstype','uuid'
        :param string value: match value
        :param list options: mount options for matching devices

        """
        self._log = logging.getLogger(__name__)
        self._key = key
        self._value = value
        self._options = list(options)
        if self._key not in self.VALID_PARAMETERS:
            raise InvalidFilter("Invalid key: %s" % self)
        self._log.debug('%s created' % self)

    @classmethod
    def from_config_item(cls, config_item):
        """
        Construct an instance from an entry in a config file.

        :param tuple config_item: (LHS,RHS) of the config line

        """
        expr, options = config_item
        try:
            key,value = re.match(r'(\w+)\.(\S+)', expr).groups()
        except AttributeError:
            raise InvalidFilter('Invalid format: %s' % expr)
        return cls(key, value,
                   (S.strip() for S in options.split(',')))

    def __str__(self):
        return '<OptionFilter %s=%s: %s>' % (self._key,
                                             self._value,
                                             self._options)

    def __call__(self, device):
        """
        Get list of mount options that this filter wants to add.

        If the device can be matched against the filter a list of
        additional mount options is returned. Otherwise, an empty list is
        returned.

        """
        if getattr(device, self.VALID_PARAMETERS[self._key]) == self._value:
            self._log.debug('%s matched against %s' % (self,
                                                       device.object_path))
            return self._options
        else:
            return []

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

        The left hand side consists of either the property key to match and
        the value to search for separated by a dot: 'key.value'. Currently,
        the only possible keys are 'fstype' and 'uuid'. The right hand side
        is a comma separated list of all options. The special value
        '__ignore__' is used to specify that a device will not be handled
        by udiskie.

        Example:

        >>> filter = FilterMatcher.from_config_section([
        ...     ('fstype.vfat', 'ro,nouser'),
        ...     ('uuid.d730f9ea-1751-4f83-8244-c9b3e6b78c3a', '__ignore__')])

        """
        return cls(map(OptionFilter.from_config_item, config_section))

    def get_mount_options(self, device):
        """Retrieve list of mount options for device."""
        return list(set(chain.from_iterable(
            filt(device) for filt in self._filters)))

    def is_ignored(self, device):
        """Check if the device should be ignored by udiskie."""
        return '__ignore__' in self.get_mount_options(device)

class Config(object):
    """Read udiskie config."""
    MOUNT_OPTIONS_SECTION = 'mount_options'
    PROGRAM_OPTIONS_SECTION = 'program_options'
    NOTIFICATIONS_SECTION = 'notifications'

    def __init__(self, data):
        self._data = data

    @classmethod
    def config_path(cls):
        try:
            from xdg.BaseDirectory import xdg_config_home as config_home
        except ImportError:
            config_home = os.path.expanduser('~/.config')
        return os.path.join(config_home, 'udiskie.conf')

    @classmethod
    def from_config_file(cls, config_file=None):
        """
        Read config file.

        :param str config_file: config file name

        Config files should look as follows:

        .. code-block:: cfg

            [mount_options]
            fstype.vfat=sync
            uuid.9d53-13ba=noexec,nodev
            uuid.abcd-ef01=__ignore__

            [program_options]
            # Allowed values are '1' and '2'
            udisks_version=2
            # 'zenity', 'systemd-ask-password' or user program:
            password_prompt=zenity
            # Leave empty to set to ``False``:
            tray=
            automount=
            # Use '1' for ``True``:
            suppress_notify=1
            # Default program:
            file_manager=xdg-open

            [notifications]
            # Default timeout in seconds:
            timeout=1.5
            # Overwrite timeout for 'device_mounted' notification:
            device_mounted=0.5
            # Leave empty to disable:
            device_unmounted=
            # Use the libnotify default timeout:
            device_unlocked=-1
            device_locked=-1

        The left hand side consists of either the property key to match and
        the value to search for separated by a dot: 'key.value'. Currently,
        the only possible keys are 'fstype' and 'uuid'. The right hand side
        is a comma separated list of all options. The special value
        '__ignore__' is used to specify that a device will not be handled
        by udiskie.

        """
        parser = SafeConfigParser()
        parser.read(config_file or cls.config_path())
        return cls(parser)

    @property
    def filter_options(self):
        try:
            mount_options = self._data.items(self.MOUNT_OPTIONS_SECTION)
        except NoSectionError:
            return []
        else:
            return FilterMatcher.from_config_section(mount_options)

    def _get_section(self, name):
        try:
            items = self._data.items(name)
        except NoSectionError:
            return {}
        else:
            return dict((k, v.strip()) for k,v in items)

    @property
    def program_options(self):
        return self._get_section(self.PROGRAM_OPTIONS_SECTION)

    @property
    def notifications(self):
        return self._get_section(self.NOTIFICATIONS_SECTION)
