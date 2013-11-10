"""
Filters for udiskie mount tools.

Used to communicate user configuration to udiskie. At the moment user
configuration can be used to ignore certain devices or add mount options.

"""
__all__ = ['InvalidFilter', 'OptionFilter', 'FilterMatcher']

try:
    from ConfigParser import SafeConfigParser, NoSectionError
except ImportError:
    # module was renamed to 'configparser' in python3:
    from configparser import SafeConfigParser, NoSectionError

import re
import logging
from itertools import chain

class InvalidFilter(ValueError):
    """Inapropriate filter configuration entry."""
    pass


class OptionFilter(object):
    """
    A filter to add a list of mount options for matching devices.

    """
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
        self.log = logging.getLogger('udiskie.match.OptionFilter')
        self.key = key
        self.value = value
        self.options = list(options)
        if self.key not in self.VALID_PARAMETERS:
            raise InvalidFilter("Invalid key: %s" % self)
        self.log.debug('%s created' % self)

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
        return '<OptionFilter %s=%s: %s>' % (self.key,
                                             self.value,
                                             self.options)

    def __call__(self, device):
        """
        Get list of mount options that this filter wants to add.

        If the device can be matched against the filter a list of
        additional mount options is returned. Otherwise, an empty list is
        returned.

        """
        if getattr(device, self.VALID_PARAMETERS[self.key]) == self.value:
            self.log.debug('%s matched against %s' % (self,
                                                      device.object_path))
            return self.options
        else:
            return []


class FilterMatcher(object):
    """
    Matches multiple OptionFilter filters against devices.
    """
    MOUNT_OPTIONS_SECTION = 'mount_options'

    def __init__(self, filters):
        """
        Construct a FilterMatcher instance from list of OptionFilters.

        :param list filters: list of callable(Device) -> list

        """
        self.filters = list(filters)

    @classmethod
    def from_config_file(cls, config_file):
        """
        Construct a FilterMatcher instance from config file.

        :param string config_file: config file name

        Config files should look as follows:

            [mount_options]
            fstype.vfat = ro,nouser
            uuid.d730f9ea-1751-4f83-8244-c9b3e6b78c3a = __ignore__

        The left hand side consists of either the property key to match and
        the value to search for separated by a dot: 'key.value'. Currently,
        the only possible keys are 'fstype' and 'uuid'. The right hand side
        is a comma separated list of all options. The special value
        '__ignore__' is used to specify that a device will not be handled
        by udiskie.

        """
        parser = SafeConfigParser()
        parser.read(config_file)
        try:
            filters = map(OptionFilter.from_config_item,
                          parser.items(cls.MOUNT_OPTIONS_SECTION))
        except NoSectionError:
            filters = []
        return cls(filters)

    def get_mount_options(self, device):
        """Retrieve list of mount options for device."""
        return list(set(chain.from_iterable(
            filt(device) for filt in self.filters)))

