"""
Command line interface logic.

The application classes in this module are installed as executables via
setuptools entry points.
"""

from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function

# import udiskie.depend first - for side effects!
from .depend import has_Notify, has_Gtk, _in_X

import sys
import inspect
import logging.config
import traceback

from docopt import docopt, DocoptExit

from gi.repository import GLib

import udiskie
import udiskie.config
import udiskie.mount
import udiskie.compat
from .async_ import AsyncList, Coroutine, Return, RunForever
from .common import extend, str2unicode, ObjDictView
from .locale import _


__all__ = [
    'Daemon',
    'Mount',
    'Umount',
]


def deprecation_warning(text):
    """Show a deprecation warning."""
    # NOTE: not using `warnings.warn(text, DeprecationWarning)`, because that
    # requires starting the python interpreter to be started with `-Wd`, which
    # in turn shows more warnings about removal of Gtk.StatusIcon.
    log = logging.getLogger("udiskie.DeprecationWarning")
    log.warning(_("Deprecation warning: {}", text))


@Coroutine.from_generator_function
def get_backend(version=None):
    """
    Return UDisks service.

    :param int version: requested UDisks backend version
    :returns: UDisks service wrapper object
    :raises GLib.GError: if unable to connect to UDisks dbus service.
    :raises ValueError: if the version is invalid

    If ``version`` has a false truth value, try to connect to UDisks1 and
    fall back to UDisks2 if not available.
    """
    if not version:
        try:
            daemon = yield get_backend(2)
        except GLib.GError:
            log = logging.getLogger(__name__)
            log.warning(_('Failed to connect UDisks2 dbus service..\n'
                          'Falling back to UDisks1.'))
            daemon = yield get_backend(1)
    elif version == 1:
        import udiskie.udisks1
        daemon = yield udiskie.udisks1.Daemon.create()
        deprecation_warning(_(
            'Using UDisks1. Support will be discontinued '
            'in the next major version of udiskie.'))
    elif version == 2:
        import udiskie.udisks2
        daemon = yield udiskie.udisks2.Daemon.create()
    else:
        raise ValueError(_("UDisks version not supported: {0}!", version))
    yield Return(daemon)


class Choice(object):

    """Mapping of command line arguments to option values."""

    def __init__(self, mapping):
        """Set mapping between arguments and values."""
        self._mapping = mapping

    def _check(self, args):
        """Exit in case of multiple exclusive arguments."""
        if sum(bool(args[arg]) for arg in self._mapping) > 1:
            raise DocoptExit(_('These options are mutually exclusive: {0}',
                               ', '.join(self._mapping)))

    def __call__(self, args):
        """Get the option value from the parsed arguments."""
        self._check(args)
        for arg, val in self._mapping.items():
            if args[arg] not in (None, False):
                return val


def Switch(name):
    """Negatable option."""
    return Choice({'--' + name: True,
                   '--no-' + name: False})


class Value(object):

    """Option which is given as value of a command line argument."""

    def __init__(self, name):
        """Set argument name."""
        self._name = name

    def __call__(self, args):
        """Get the value of the command line argument."""
        return str2unicode(args[self._name])


class OptionalValue(object):

    def __init__(self, name):
        """Set argument name."""
        self._name = name
        self._choice = Switch(name.lstrip('-'))

    def __call__(self, args):
        """Get the value of the command line argument."""
        return self._choice(args) and str2unicode(args[self._name])


class SelectLevel(logging.Filter):
    def __init__(self, level):
        self.level = level
    def filter(self, record):
        return record.levelno == self.level


class _EntryPoint(object):

    """
    Abstract base class for program entry points.

    Concrete implementations need to implement :meth:`run` and extend
    :meth:`finalize_options` to be usable with :meth:`main`. Furthermore
    the docstring of any concrete implementation must be usable with
    docopt. :ivar:`name` must be set to the name of the CLI utility.
    """

    option_defaults = {
        'log_level': logging.INFO,
        'udisks_version': None,
    }

    option_rules = {
        'log_level': Choice({
            '--verbose': logging.DEBUG,
            '--quiet': logging.ERROR}),
        'udisks_version': Choice({
            '--udisks-auto': 0,
            '--use-udisks1': 1,
            '--use-udisks2': 2}),
    }

    usage_remarks = _("""
    Note, that the options in the individual groups are mutually exclusive.

    The config file can be a JSON or preferrably a YAML file. For an
    example, see the MAN page (or doc/udiskie.8.txt in the repository).
    """)

    def __init__(self, argv=None):
        """
        Parse command line options, read config and initialize members.

        :param list argv: command line parameters
        """
        udiskie.compat.patch_print_unicode()
        # parse program options (retrieve log level and config file name):
        args = docopt(self.usage, version=self.name + ' ' + self.version)
        default_opts = self.option_defaults
        program_opts = self.program_options(args)
        # initialize logging configuration:
        log_level = program_opts.get('log_level', default_opts['log_level'])
        debug = log_level <= logging.DEBUG
        logging.config.dictConfig({
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'plain':  {'format': _('%(message)s')},
                'detail': {'format': _('%(levelname)s [%(asctime)s] %(name)s: %(message)s')},
            },
            'filters': {
                'info': {'()': 'udiskie.cli.SelectLevel', 'level': logging.INFO},
            },
            'handlers': {
                'info':  {'class': 'logging.StreamHandler',
                          'stream': 'ext://sys.stdout',
                          'formatter': 'plain',
                          'filters': ['info']},
                'error': {'class': 'logging.StreamHandler',
                          'stream': 'ext://sys.stderr',
                          'formatter': 'plain',
                          'level': 'WARNING'},
                'debug': {'class': 'logging.StreamHandler',
                          'stream': 'ext://sys.stderr',
                          'formatter': 'detail'},
            },
            # configure root logger:
            'root': {
                'handlers': ['info', 'debug' if debug else 'error'],
                'level': log_level,
            },
        })
        # parse config options
        config_file = OptionalValue('--config')(args)
        config = udiskie.config.Config.from_file(config_file)
        options = {}
        options.update(default_opts)
        options.update(config.program_options)
        options.update(program_opts)
        # initialize instance variables
        self.config = config
        self.options = options
        self.exit_status = 0
        if sys.version_info < (3,5):
            deprecation_warning(_(
                "Running on python {}.{}. The next major version of udiskie "
                "will require at least python 3.5!",
                *sys.version_info[:2]))

    def program_options(self, args):
        """
        Fully initialize Daemon object.

        :param dict args: arguments as parsed by docopt
        :returns: options from command line
        :rtype: dict
        """
        options = {}
        for name, rule in self.option_rules.items():
            val = rule(args)
            if val is not None:
                options[name] = val
        return options

    @classmethod
    def main(cls, argv=None):
        """
        Run program.

        :param list argv: command line parameters
        :returns: program exit code
        :rtype: int
        """
        return cls(argv).run()

    @property
    def version(self):
        """Get the version from setuptools metadata."""
        return udiskie.__version__

    @property
    def usage(self):
        """Get the full usage string."""
        return inspect.cleandoc(self.__doc__ + self.usage_remarks)

    @property
    def name(self):
        """Get the name of the CLI utility."""
        raise NotImplementedError()

    def _init(self):
        """
        Fully initialize Daemon object.

        :returns: the main application task
        :rtype: Async
        """
        raise NotImplementedError()

    def run(self):
        """
        Run the main loop.

        :returns: exit code
        :rtype: int
        """
        self.mainloop = GLib.MainLoop()
        self._start_async_tasks()
        try:
            self.mainloop.run()
            return self.exit_status
        except KeyboardInterrupt:
            return 1

    @Coroutine.from_generator_function
    def _start_async_tasks(self):
        """Start asynchronous operations."""
        try:
            self.udisks = yield get_backend(self.options['udisks_version'])
            results = yield self._init()
            if not all(results):
                self.exit_status = 1
        except Exception:
            self.exit_status = 1
            # Print the stack trace only up to the current level:
            traceback.print_exc()
        self.mainloop.quit()


class Component(object):

    def __init__(self, create):
        self.create = create
        self.instance = None

    @property
    def active(self):
        return self.instance is not None and self.instance.active

    def activate(self):
        if self.instance is None:
            self.instance = self.create()
        if not self.instance.active:
            self.instance.activate()

    def deactivate(self):
        if self.active:
            self.instance.deactivate()

    def toggle(self):
        if self.active:
            self.deactivate()
        else:
            self.activate()


class Daemon(_EntryPoint):

    """
    udiskie: a user-level daemon for auto-mounting.

    Usage:
        udiskie [options]
        udiskie (--help | --version)

    General options:
        -c FILE, --config=FILE                  Set config file
        -C, --no-config                         Don't use config file

        -v, --verbose                           Increase verbosity (DEBUG)
        -q, --quiet                             Decrease verbosity

        -0, --udisks-auto                       Auto discover UDisks version
        -1, --use-udisks1                       Use UDisks1 as backend
        -2, --use-udisks2                       Use UDisks2 as backend

        -h, --help                              Show this help
        -V, --version                           Show version information

    Daemon options:
        -a, --automount                         Automount new devices
        -A, --no-automount                      Disable automounting

        -n, --notify                            Show popup notifications
        -N, --no-notify                         Disable notifications

        -t, --tray                              Show tray icon
        -s, --smart-tray                        Auto hide tray icon
        -T, --no-tray                           Disable tray icon
        -m MENU, --menu MENU                    Tray menu [flat/nested]

        --appindicator                          Use appindicator for status icon
        --no-appindicator                       Don't use appindicator

        --password-cache MINUTES                Set password cache timeout
        --no-password-cache                     Disable password cache

        -p COMMAND, --password-prompt COMMAND   Command for password retrieval
        -P, --no-password-prompt                Disable unlocking

        --notify-command COMMAND                Command to execute on events
        --no-notify-command                     Disable command notifications

    Deprecated options:
        -f PROGRAM, --file-manager PROGRAM      Set program for browsing
        -F, --no-file-manager                   Disable browsing
    """

    name = 'udiskie'

    option_defaults = extend(_EntryPoint.option_defaults, {
        'automount': True,
        'notify': True,
        'tray': False,
        'menu': 'flat',
        'appindicator': False,
        'file_manager': 'xdg-open',
        'password_prompt': 'builtin:gui',
        'password_cache': False,
        'notify_command': None,
    })

    option_rules = extend(_EntryPoint.option_rules, {
        'automount': Switch('automount'),
        'notify': Switch('notify'),
        'tray': Choice({
            '--tray': True,
            '--no-tray': False,
            '--smart-tray': 'auto'}),
        'menu': Value('--menu'),
        'appindicator': Switch('appindicator'),
        'file_manager': OptionalValue('--file-manager'),
        'password_prompt': OptionalValue('--password-prompt'),
        'password_cache': OptionalValue('--password-cache'),
        'notify_command': OptionalValue('--notify-command'),
    })

    def _init(self):

        """Implements _EntryPoint._init."""

        import udiskie.prompt

        config = self.config
        options = self.options

        # prepare mounter object
        prompt = udiskie.prompt.password(options['password_prompt'])
        browser = udiskie.prompt.browser(options['file_manager'])
        cache = None

        if options['password_cache'] is not False:
            import udiskie.cache
            timeout = int(options['password_cache']) * 60
            cache = udiskie.cache.PasswordCache(timeout)

        self.mounter = udiskie.mount.Mounter(
            config=config.device_config,
            prompt=prompt,
            browser=browser,
            cache=cache,
            udisks=self.udisks)

        # check component availability
        if options['notify'] and not has_Notify():
            libnotify_not_available = _(
                "Typelib for 'libnotify' is not available. Possible causes include:"
                "\n\t- libnotify is not installed"
                "\n\t- the typelib is provided by a separate package"
                "\n\t- libnotify was built with introspection disabled"
                "\n\nStarting udiskie without notifications.")
            logging.getLogger(__name__).error(libnotify_not_available)
            options['notify'] = False

        if options['tray'] and not has_Gtk(3) and not _in_X:
            no_X_session = _(
                "Not run within X session. "
                "\nStarting udiskie without tray icon.\n")
            logging.getLogger(__name__).error(no_X_session)
            options['tray'] = False

        if options['tray'] and not has_Gtk(3):
            gtk3_not_available = _(
                "Typelib for 'Gtk 3.0' is not available. Possible causes include:"
                "\n\t- GTK3 is not installed"
                "\n\t- the typelib is provided by a separate package"
                "\n\t- GTK3 was built with introspection disabled"
                "\nStarting udiskie without tray icon.\n")
            logging.getLogger(__name__).error(gtk3_not_available)
            options['tray'] = False

        # start components
        tasks = []

        self.notify         = Component(self._load_notify)
        self.statusicon     = Component(self._load_statusicon)
        self.automounter    = Component(self._load_automounter)

        if options['notify']:
            self.notify.activate()
        if options['notify_command']:
            # is currently enabled/disabled statically only once:
            self.notify_command()
        if options['tray']:
            self.statusicon.activate()
            tasks.append(self.statusicon.instance._icon.task)
        else:
            tasks.append(RunForever)
        if options['automount']:
            self.automounter.activate()
            tasks.append(self.mounter.add_all())

        return AsyncList(tasks)

    def _load_notify(self):
        import udiskie.notify
        from gi.repository import Notify
        Notify.init('udiskie')
        aconfig = self.config.notification_actions
        if self.options['automount']:
            aconfig.setdefault('device_added', [])
        else:
            aconfig.setdefault('device_added', ['mount'])
        return udiskie.notify.Notify(
            Notify.Notification.new,
            mounter=self.mounter,
            timeout=self.config.notifications,
            aconfig=aconfig)

    def notify_command(self):
        import udiskie.prompt
        return udiskie.prompt.notify_command(
            self.options['notify_command'], self.mounter)

    def _load_statusicon(self):
        import udiskie.tray
        options = self.options

        if options['tray'] == 'auto':
            smart = True
        elif options['tray'] is True:
            smart = False
        else:
            raise ValueError("Invalid tray: %s" % (options['tray'],))
        icons = udiskie.tray.Icons(self.config.icon_names)
        actions = udiskie.mount.DeviceActions(self.mounter)

        if options['menu'] == 'flat':
            flat = True
        # dropped legacy 'nested' mode:
        elif options['menu'] in ('smart', 'nested'):
            flat = False
        else:
            raise ValueError("Invalid menu: %s" % (options['menu'],))

        menu_maker = udiskie.tray.UdiskieMenu(self, icons, actions, flat)
        if options['appindicator']:
            import udiskie.appindicator
            TrayIcon = udiskie.appindicator.AppIndicatorIcon
        else:
            TrayIcon = udiskie.tray.TrayIcon
        trayicon = TrayIcon(menu_maker, icons)
        return udiskie.tray.UdiskieStatusIcon(trayicon, menu_maker, smart)

    def _load_automounter(self):
        import udiskie.automount
        return udiskie.automount.AutoMounter(self.mounter)


class Mount(_EntryPoint):

    """
    udiskie-mount: a user-level command line utility for mounting.

    Usage:
        udiskie-mount [options] (-a | DEVICE...)
        udiskie-mount (--help | --version)

    General options:
        -c FILE, --config=FILE                  Set config file
        -C, --no-config                         Don't use config file

        -v, --verbose                           Increase verbosity (DEBUG)
        -q, --quiet                             Decrease verbosity

        -0, --udisks-auto                       Auto discover UDisks version
        -1, --use-udisks1                       Use UDisks1 as backend
        -2, --use-udisks2                       Use UDisks2 as backend

        -h, --help                              Show this help
        -V, --version                           Show version information

    Mount options:
        -a, --all                               Mount all handleable devices

        -r, --recursive                         Recursively mount partitions
        -R, --no-recursive                      Disable recursive mounting

        -o OPTIONS, --options OPTIONS           Mount option list

        -p COMMAND, --password-prompt COMMAND   Command for password retrieval
        -P, --no-password-prompt                Disable unlocking
    """

    name = 'udiskie-mount'

    option_defaults = extend(_EntryPoint.option_defaults, {
        'recursive': None,
        'options': None,
        '<device>': None,
        'password_prompt': 'builtin:tty',
    })

    option_rules = extend(_EntryPoint.option_rules, {
        'recursive': Switch('recursive'),
        'options': Value('--options'),
        '<device>': Value('DEVICE'),
        'password_prompt': OptionalValue('--password-prompt'),
    })

    def _init(self):

        """Implements _EntryPoint._init."""

        import udiskie.prompt

        config = self.config
        options = self.options

        device_config = config.device_config
        if options['options']:
            device_config._filters.insert(0, udiskie.config.MountOptions({
                'options': [o.strip() for o in options['options'].split(',')],
            }))

        prompt = udiskie.prompt.password(options['password_prompt'])
        mounter = udiskie.mount.Mounter(
            config=config.device_config,
            prompt=prompt,
            udisks=self.udisks)

        recursive = options['recursive']
        if options['<device>']:
            tasks = [mounter.add(path, recursive=recursive)
                     for path in options['<device>']]
        else:
            tasks = [mounter.add_all(recursive=recursive)]
        return AsyncList(tasks)


class Umount(_EntryPoint):

    """
    udiskie-umount: a user-level command line utility for unmounting.

    Usage:
        udiskie-umount [options] (-a | DEVICE...)
        udiskie-umount (--help | --version)

    General options:
        -c FILE, --config=FILE      Set config file
        -C, --no-config             Don't use config file

        -v, --verbose               Increase verbosity (DEBUG)
        -q, --quiet                 Decrease verbosity

        -0, --udisks-auto           Auto discover UDisks version
        -1, --use-udisks1           Use UDisks1 as backend
        -2, --use-udisks2           Use UDisks2 as backend

        -h, --help                  Show this help
        -V, --version               Show version information

    Unmount options:
        -a, --all                   Unmount all handleable devices

        -d, --detach                Power off drive if possible
        -D, --no-detach             Don't power off drive

        -e, --eject                 Eject media from device if possible
        -E, --no-eject              Don't eject media

        -f, --force                 Force removal (recursive unmounting)
        -F, --no-force              Don't force removal

        -l, --lock                  Lock device after unmounting
        -L, --no-lock               Don't lock device
    """

    name = 'udiskie-umount'

    option_defaults = extend(_EntryPoint.option_defaults, {
        'detach': None,
        'eject': False,
        'force': False,
        'lock': True,
        '<device>': None,
    })

    option_rules = extend(_EntryPoint.option_rules, {
        'detach': Switch('detach'),
        'eject': Switch('eject'),
        'force': Switch('force'),
        'lock': Switch('lock'),
        '<device>': Value('DEVICE'),
    })

    def _init(self):

        """Implements _EntryPoint._init."""

        config = self.config
        options = self.options

        mounter = udiskie.mount.Mounter(
            self.udisks,
            config=config.device_config)

        strategy = dict(detach=options['detach'],
                        eject=options['eject'],
                        lock=options['lock'])
        if options['<device>']:
            strategy['force'] = options['force']
            tasks = [mounter.remove(path, **strategy)
                     for path in options['<device>']]
        else:
            tasks = [mounter.remove_all(**strategy)]
        return AsyncList(tasks)


def _parse_filter(spec):
    try:
        key, val = spec.split('=', 1)
    except ValueError:
        if spec.startswith('!'):
            val = False
            key = spec[1:]
        else:
            val = True
            key = spec
    return key, val


class Info(_EntryPoint):

    """
    udiskie-info: get information about handleable devices.

    Usage:
        udiskie-info [options] [-o OUTPUT] [-f FILTER]... (-a | DEVICE...)
        udiskie-info (--help | --version)

    General options:
        -c FILE, --config=FILE      Set config file
        -C, --no-config             Don't use config file

        -v, --verbose               Increase verbosity (DEBUG)
        -q, --quiet                 Decrease verbosity

        -0, --udisks-auto           Auto discover UDisks version
        -1, --use-udisks1           Use UDisks1 as backend
        -2, --use-udisks2           Use UDisks2 as backend

        -h, --help                  Show this help
        -V, --version               Show version information

    Unmount options:
        -a, --all                   List all handleable devices

        -o COL, --output COL        Specify output columns in a format string
                                    containing the allowed device attributes,
                                    e.g.: "{ui_label} {is_luks}"
                                    [default: device_presentation].

        -f FILT, --filter FILT      Print only devices that match the given
                                    filter.
    """

    name = 'udiskie-info'

    option_defaults = extend(_EntryPoint.option_defaults, {
        'output': '',
        'filter': '',
        '<device>': None,
    })

    option_rules = extend(_EntryPoint.option_rules, {
        'output': Value('--output'),
        'filter': Value('--filter'),
        '<device>': Value('DEVICE'),
    })

    def _init(self):

        """Implements _EntryPoint._init."""

        config = self.config
        options = self.options

        mounter = udiskie.mount.Mounter(
            self.udisks,
            config=config.device_config)

        if options['<device>']:
            devices = [self.udisks.find(path) for path in options['<device>']]
        else:
            devices = mounter.get_all_handleable()

        DeviceFilter = udiskie.config.DeviceFilter
        output = options['output']
        # old behaviour: single attribute
        if output in DeviceFilter.VALID_PARAMETERS:
            def format_output(device):
                return getattr(device, output)
        # new behaviour: format string
        else:
            from string import Formatter
            formatter = Formatter()
            def format_output(device):
                view = ObjDictView(device, DeviceFilter.VALID_PARAMETERS)
                return formatter.vformat(output, (), view)

        filters = [_parse_filter(spec) for spec in options['filter']]
        matcher = DeviceFilter(dict(filters))

        for device in devices:
            if matcher.match(device):
                print(format_output(device))

        return AsyncList([])
