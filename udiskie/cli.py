"""
Command line interface logic.

The application classes in this module are installed as executables via
setuptools entry points.
"""

# import udiskie.depend first - for side effects!
from .depend import has_Notify, has_Gtk, _in_X, _in_Wayland, has_AppIndicator3

import inspect
import logging.config
import traceback

from gi.repository import GLib

from docopt import docopt, DocoptExit

import udiskie
import udiskie.config
import udiskie.mount
import udiskie.udisks2
from .common import extend, ObjDictView
from .locale import _
from .async_ import Future, ensure_future, gather


__all__ = [
    'Daemon',
    'Mount',
    'Umount',
]


class Choice:

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


class Value:

    """Option which is given as value of a command line argument."""

    def __init__(self, name):
        """Set argument name."""
        self._name = name

    def __call__(self, args):
        """Get the value of the command line argument."""
        return args[self._name]


class OptionalValue:

    def __init__(self, name):
        """Set argument name."""
        self._name = name
        self._choice = Switch(name.lstrip('-'))

    def __call__(self, args):
        """Get the value of the command line argument."""
        return self._choice(args) and args[self._name]


class SelectLevel(logging.Filter):

    def __init__(self, level):
        self.level = level

    def filter(self, record):
        return record.levelno == self.level


class _EntryPoint:

    """
    Abstract base class for program entry points.

    Implementations need to

    - implement :meth:`_init`
    - provide a docstring
    - extend :cvar:`option_defaults` and :cvar:`option_rules`.
    """

    option_defaults = {
        'log_level': logging.INFO,
    }

    option_rules = {
        'log_level': Choice({
            '--verbose': logging.DEBUG,
            '--quiet': logging.ERROR}),
    }

    usage_remarks = _("""
    Note, that the options in the individual groups are mutually exclusive.

    The config file can be a JSON or preferably a YAML file. For an
    example, see the MAN page (or doc/udiskie.8.txt in the repository).
    """)

    def __init__(self, argv=None):
        """Parse command line options, read config and initialize members."""
        # parse program options (retrieve log level and config file name):
        args = docopt(self.usage, version='udiskie ' + self.version)
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
                'detail': {'format': _(
                    '%(levelname)s [%(asctime)s] %(name)s: %(message)s')},
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

    def program_options(self, args):
        """Get program options from docopt parsed options."""
        options = {}
        for name, rule in self.option_rules.items():
            val = rule(args)
            if val is not None:
                options[name] = val
        return options

    @classmethod
    def main(cls, argv=None):
        """Run program. Returns program exit code."""
        return cls(argv).run()

    @property
    def version(self):
        """Version from setuptools metadata."""
        return udiskie.__version__

    @property
    def usage(self):
        """Full usage string."""
        return inspect.cleandoc(self.__doc__ + self.usage_remarks)

    def _init(self):
        """Return the application main task as Future."""
        raise NotImplementedError()

    def run(self):
        """Run the main loop. Returns exit code."""
        self.exit_code = 1
        self.mainloop = GLib.MainLoop()
        try:
            future = ensure_future(self._start_async_tasks())
            future.callbacks.append(self.set_exit_code)
            self.mainloop.run()
            return self.exit_code
        except KeyboardInterrupt:
            return 1

    def set_exit_code(self, exit_code):
        self.exit_code = exit_code

    async def _start_async_tasks(self):
        """Start asynchronous operations."""
        try:
            self.udisks = await udiskie.udisks2.Daemon.create()
            results = await self._init()
            return 0 if all(results) else 1
        except Exception:
            traceback.print_exc()
            return 1
        finally:
            self.mainloop.quit()


class Component:

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

        -f PROGRAM, --file-manager PROGRAM      Set program for browsing
        -F, --no-file-manager                   Disable browsing

        --terminal COMMAND                      Set terminal command line
                                                (e.g. "termite -d")
        --no-terminal                           Disable terminal action

        -p COMMAND, --password-prompt COMMAND   Command for password retrieval
        -P, --no-password-prompt                Disable unlocking

        --notify-command COMMAND                Command to execute on events
        --no-notify-command                     Disable command notifications
    """

    option_defaults = extend(_EntryPoint.option_defaults, {
        'automount': True,
        'notify': True,
        'tray': False,
        'menu': 'flat',
        'appindicator': None,
        'file_manager': 'xdg-open',
        'terminal': '',
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

        import udiskie.prompt

        config = self.config
        options = self.options

        # prepare mounter object
        prompt = udiskie.prompt.password(options['password_prompt'])
        browser = udiskie.prompt.browser(options['file_manager'])
        terminal = udiskie.prompt.browser(options['terminal'])
        cache = None

        try:
            import udiskie.cache
            timeout = int(options['password_cache']) * 60
            cache = udiskie.cache.PasswordCache(timeout)
        except ImportError:
            cache = None

        self.mounter = udiskie.mount.Mounter(
            config=config.device_config,
            prompt=prompt,
            browser=browser,
            terminal=terminal,
            cache=cache,
            cache_hint=options['password_cache'],
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

        show_tray = options['tray'] or options['appindicator']
        if show_tray and _in_Wayland and options['appindicator'] is None:
            options['appindicator'] = True

        if show_tray and not (_in_X or _in_Wayland):
            no_tray_support = _(
                "Not run within X or Wayland session."
                "\nStarting udiskie without tray icon.\n")
            logging.getLogger(__name__).error(no_tray_support)
            show_tray = False

        if show_tray and not has_Gtk(3):
            gtk3_not_available = _(
                "Typelib for 'Gtk 3.0' is not available. Possible causes include:"
                "\n\t- GTK3 is not installed"
                "\n\t- the typelib is provided by a separate package"
                "\n\t- GTK3 was built with introspection disabled"
                "\nStarting udiskie without tray icon.\n")
            logging.getLogger(__name__).error(gtk3_not_available)
            show_tray = False

        if show_tray and options['appindicator'] and not has_AppIndicator3():
            appindicator_not_available = _(
                "Typelib for 'AppIndicator3 0.1' is not available. Possible "
                "causes include:"
                "\n\t- libappindicator is not installed"
                "\n\t- the typelib is provided by a separate package"
                "\n\t- it was built with introspection disabled"
                "\nStarting udiskie without appindicator icon.\n")
            logging.getLogger(__name__).error(appindicator_not_available)
            options['appindicator'] = False

        # start components
        tasks = []

        self.notify = Component(self._load_notify)
        self.statusicon = Component(self._load_statusicon)
        self.automounter = self._load_automounter(options['automount'])
        self.automounter.activate()

        if options['notify']:
            self.notify.activate()
        if options['notify_command']:
            # is currently enabled/disabled statically only once:
            self.notify_command()
        if show_tray:
            self.statusicon.activate()
            tasks.append(self.statusicon.instance._icon.task)
        else:
            tasks.append(Future())
        if options['automount']:
            tasks.append(self.mounter.add_all())

        return gather(*tasks)

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
        config = self.config

        smart = options['tray'] == 'auto'
        if options['tray'] not in ('auto', True, False):
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

        menu_maker = udiskie.tray.UdiskieMenu(self, icons, actions, flat,
                                              config.quickmenu_actions)
        if options['appindicator']:
            import udiskie.appindicator
            TrayIcon = udiskie.appindicator.AppIndicatorIcon
        else:
            TrayIcon = udiskie.tray.TrayIcon
        trayicon = TrayIcon(menu_maker, icons)
        return udiskie.tray.UdiskieStatusIcon(trayicon, menu_maker, smart)

    def _load_automounter(self, automount):
        import udiskie.automount
        return udiskie.automount.AutoMounter(self.mounter, automount)


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

        import udiskie.prompt

        config = self.config
        options = self.options

        device_config = config.device_config
        if options['options']:
            device_config.insert(0, udiskie.config.MountOptions({
                'options': [o.strip() for o in options['options'].split(',')],
            }))

        prompt = udiskie.prompt.password(options['password_prompt'])
        mounter = udiskie.mount.Mounter(
            config=device_config,
            prompt=prompt,
            udisks=self.udisks)

        recursive = options['recursive']
        if options['<device>']:
            tasks = [mounter.add(path, recursive=recursive)
                     for path in options['<device>']]
        else:
            tasks = [mounter.add_all(recursive=recursive)]
        return gather(*tasks)


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
        return gather(*tasks)


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
            def format_output(device):
                view = ObjDictView(device, DeviceFilter.VALID_PARAMETERS)
                return output.format_map(view)

        filters = [_parse_filter(spec) for spec in options['filter']]
        matcher = DeviceFilter(dict(filters))

        for device in devices:
            if matcher.match(device):
                print(format_output(device))

        return gather()
