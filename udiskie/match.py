from ConfigParser import SafeConfigParser
import logging
import re

class InvalidFilter(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return 'Invalid Filter: %s' % (self.value,)


class OptionFilter:
    # This list also defines the order in which the filters are
    # processed. Should go from least specific to most specific.
    VALID_PARAMETERS = (
        'fstype',
        'uuid',
    )

    MATCH_PATTERN = re.compile(r'(\w+)\.(\S+)')

    def __init__(self, parameter, value, options):
        self.parameter = parameter
        self.value = value
        self.options = options

    def __str__(self):
        return '<OptionFilter: %s=%s, options=%s>' % (self.parameter,
                                                      self.value,
                                                      self.options)

    def __repr__(self):
        return str(self)


class Filters:
    def __init__(self):
        self.option_filters = []
        self.log = logging.getLogger('udiskie.match.Filters')

    def _parse_option_match(self, match_expression):
        match = OptionFilter.MATCH_PATTERN.match(match_expression)
        if not match:
            raise InvalidFilter('format is parameter=value')
        parameter, value = match.groups()
        if parameter not in OptionFilter.VALID_PARAMETERS:
            raise InvalidFilter('parameter "%s" is not allowed' % (parameter,))
        return parameter, value

    def add_option_filter(self, match_expression, options):
        parameter, value = self._parse_option_match(match_expression)
        options = [S.strip() for S in options.split(',')]
        filt = OptionFilter(parameter, value, options)
        self.log.debug('loaded filter: %s' % (filt,))
        self.option_filters.append(filt)

    def get_option_filters(self, parameter):
        return [F for F in self.option_filters if F.parameter == parameter]


class FilterMatcher:
    MOUNT_OPTIONS_SECTION = 'mount_options'

    def __init__(self, config_files):
        self.log = logging.getLogger('udiskie.match.FilterMatcher')
        self.filters = self._load_filters_from_config_files(config_files)

    def _load_filters_from_config_files(self, config_files):
        filters = Filters()

        parser = SafeConfigParser()
        parser.read(config_files)

        if parser.has_section(self.MOUNT_OPTIONS_SECTION):
            for (match, options) in parser.items(self.MOUNT_OPTIONS_SECTION):
                filters.add_option_filter(match, options)

        return filters

    def get_mount_options(self, device):
        device_info = {
            'fstype' : device.id_type(),
            'uuid' : device.id_uuid().lower()
        }

        mount_options = set()
        for match_type in OptionFilter.VALID_PARAMETERS:
            device_value = device_info.get(match_type)
            for filt in self.filters.get_option_filters(match_type):
                if device_value == filt.value:
                    self.log.info('filter matched: %s' % (filt,))
                    for option in filt.options:
                        mount_options.add(option)

        return list(mount_options)
