"""
Config file utility classes.
"""

import os
import logging


__all__ = ['OptionFilter',
           'FilterMatcher',
           'Config']


class OptionFilter(object):

    """Add a list of mount options for matching devices."""

    def __init__(self, key, value, options):
        """
        Create an OptionFilter.

        :param string key: attribute to match by, e.g. 'id_type', 'id_uuid'
        :param string value: property value to match
        :param list options: mount options for matching devices
        """
        self._log = logging.getLogger(__name__)
        self._key = key
        self._value = value
        self._options = list(options)
        self._log.debug('%s created' % self)

    def __str__(self):
        return '<OptionFilter %s=%s: %s>' % (self._key,
                                             self._value,
                                             self._options)

    def match(self, device):
        """
        Check if the device is matched by this filter.

        :param device: udiskie device object
        :returns: whether the device is matched by this filter
        :rtype: bool
        """
        return getattr(device, self._key) == self._value

    def options(self, device):
        """
        Get list of mount options for the specified device.

        :param device: udiskie device object
        :returns: mount options to be used
        :rtype: list
        """
        self._log.debug('%s matched against %s' % (self, device.object_path))
        return self._options


class FilterMatcher(object):

    """
    Matches devices against multiple :class:`OptionFilter`s.

    Only the first matching filter will be used.
    """

    def __init__(self, *filters):
        """
        Construct a FilterMatcher instance from list of OptionFilters.

        :param *filters: objects of :class:`OptionFilter` or compatible
        """
        self._filters = filters

    def get_mount_options(self, device):
        """Retrieve list of mount options for device."""
        try:
            return next(iter(filt.options(device)
                             for filt in self._filters
                             if filt.match(device)))
        except StopIteration:
            return []

    def is_ignored(self, device):
        """Check if the device should be ignored by udiskie."""
        return any('__ignore__' in filt.options(device)
                   for filt in self._filters
                   if filt.match(device))


class Config(object):

    """
    Config file representation.

    The following instance variables hold the config sections:

    :ivar dict program_options:
    :ivar FilterMatcher mount_option_filter:
    :ivar dict notification_timeouts:
    """

    def __init__(self, **kwargs):
        """
        Initialize with specified configuration data.

        :param int udisks_version: corresponds to '-1' or '-2'.
        :param bool automount: corresponds to '--no-automount'
        :param bool suppress_notify: corresponds to '--suppress'
        :param callable password_prompt: corresponds to '--password-prompt'
        :param callable file_manager: corresponds to '--file-manager'
        :param callable tray: corresponds to '--tray' or '--auto-tray'
        :param dict notification_timeouts: notification timeouts in seconds
        :param FilterMatcher mount_option_filter: mount options
        """
        try:
            self.mount_option_filter = kwargs.pop('mount_option_filter')
        except KeyError:
            self.mount_option_filter = FilterMatcher()
        self.notification_timeouts = kwargs.pop('notification_timeouts', None)
        self.program_options = kwargs

    @classmethod
    def default_config_path(cls):
        """
        Return the default config path.

        :returns: something like "$XDG_CONFIG_HOME/udiskie.py"
        :rtype: str
        """
        try:
            from xdg.BaseDirectory import xdg_config_home as config_home
        except ImportError:
            config_home = os.path.expanduser('~/.config')
        return os.path.join(config_home, 'udiskie.py')

    @classmethod
    def from_config_file(cls, config_file=None):
        """
        Read config file.

        :param str config_file: config file name (optional)
        :returns: the resulting configuration
        :rtype: Config

        The config file is a python script file that should define a global
        :var:`config`.

        For an example config file, see :file:`udiskie/config_example.py`.
        """
        config_file = config_file or cls.default_config_path()
        try:
            with open(config_file) as f:
                source = f.read()
        except IOError:
            return Config()
        else:
            code = compile(source, config_file, 'exec')
            # for convenience
            globals_ = globals()
            locals_ = {}
            exec(code, globals_, locals_)
            return locals_['config']
