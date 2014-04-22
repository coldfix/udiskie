"""
Command line interface logic.

The application classes in this module are installed as executables via
setuptools entry points.
"""

import logging
import optparse
import pkg_resources
import sys
import warnings

from docopt import docopt

import udiskie.config
import udiskie.mount


__all__ = ['Daemon', 'Mount', 'Umount']


warnings.filterwarnings("ignore", ".*could not open display.*", Warning)
warnings.filterwarnings("ignore", ".*g_object_unref.*", Warning)


def get_backend(clsname, version=None):
    """
    Return UDisks service.

    :param str clsname: requested service object
    :param int version: requested UDisks backend version
    :returns: UDisks service wrapper object
    :raises dbus.DBusException: if unable to connect to UDisks dbus service.
    :raises ValueError: if the version is invalid

    If ``version`` has a false truth value, try to connect to UDisks1 and
    fall back to UDisks2 if not available.
    """
    def udisks1():
        import udiskie.udisks1
        return getattr(udiskie.udisks1, clsname)()
    def udisks2():
        import udiskie.udisks2
        return getattr(udiskie.udisks2, clsname)()
    if not version:
        from udiskie.dbus import DBusException
        try:
            return udisks1()
        except DBusException:
            msg = sys.exc_info()[1].get_dbus_message()
            log = logging.getLogger(__name__)
            log.warning('Failed to connect UDisks1 dbus service: %s.\n'
                        'Falling back to UDisks2 [experimental].' % (msg,))
            return udisks2()
    elif version == 1:
        return udisks1()
    elif version == 2:
        return udisks2()
    else:
        raise ValueError("UDisks version not supported: %s!" % (version,))


def extend(a, b):
    """Merge two dicts and return a new dict. Much like subclassing works."""
    res = a.copy()
    res.update(b)
    return res


class Choice(object):

    """Mapping of command line arguments to option values."""

    def __init__(self, mapping):
        """Set mapping between arguments and values."""
        self._mapping = mapping

    def __call__(self, args):
        """Get the option value from the parsed arguments."""
        for arg, val in self._mapping.items():
            if args[arg]:
                return val


class Value(object):

    """Option which is given as value of a command line argument."""

    def __init__(self, name):
        """Set argument name."""
        self._name = name

    def __call__(self, args):
        """Get the value of the command line argument."""
        return args[self._name]


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
            '--use-udisks1': 1,
            '--use-udisks2': 2}),
    }

    def __init__(self, argv=None):
        """
        Parse command line options, read config and initialize members.

        :param list argv: command line parameters
        """
        # parse program options (retrieve log level and config file name):
        args = docopt(self.__doc__, version=self.name + ' ' + self.version)
        default_opts = self.option_defaults
        program_opts = self.program_options(args)
        # initialize logging configuration:
        log_level = program_opts.get('log_level', default_opts['log_level'])
        if log_level <= logging.DEBUG:
            fmt = '%(levelname)s [%(asctime)s] %(name)s: %(message)s'
        else:
            fmt = '%(message)s'
        logging.basicConfig(level=log_level, format=fmt)
        # parse config options
        config = udiskie.config.Config.from_file(args['--config'])
        options = {}
        options.update(default_opts)
        options.update(config.program_options)
        options.update(program_opts)
        # initialize instance variables
        self.config = config
        self.options = options
        self._init(config, options)

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
        try:
            return pkg_resources.get_distribution('udiskie').version
        except pkg_resources.DistributionNotFound:
            return '(unknown version)'

    @property
    def name(self):
        """Get the name of the CLI utility."""
        raise NotImplementedError()

    def _init(self, config, options):
        """
        Fully initialize Daemon object.

        :param Config config: configuration object
        :param options: program options as returned by optparse
        """
        raise NotImplementedError()

    def run(self):
        """
        Run main program logic.

        :param options: program options as returned by optparse
        :returns: exit code
        :rtype: int
        """
        raise NotImplementedError()


class Daemon(_EntryPoint):

    """
    udiskie: a user-level daemon for auto-mounting.

    Usage:
        udiskie [-C FILE] [-v|-q] [-1|-2] [-Ns] [-F PROGRAM] [-t|-T]
        udiskie (--help | --version)

    General options:
        -C FILE, --config=FILE                  Set config file

        -v, --verbose                           Increase verbosity (DEBUG)
        -q, --quiet                             Decrease verbosity

        -1, --use-udisks1                       Use UDisks1 as backend
        -2, --use-udisks2                       Use UDisks2 as backend

        -h, --help                              Show this help
        -V, --version                           Show version information

    Daemon options:
        -N, --no-automount                      do not automount new devices
        -s, --suppress                          suppress popup notifications
        -t, --tray                              show tray icon
        -T, --auto-tray                         show tray icon (auto-hiding)
        -F PROGRAM, --file-manager PROGRAM      [deprecated]
    """

    name = 'udiskie'

    option_defaults = extend(_EntryPoint.option_defaults, {
        'automount': True,
        'notify': True,
        'tray': False,
        'file_manager': 'xdg-open'
    })

    option_rules = extend(_EntryPoint.option_rules, {
        'notify': Choice({
            '--suppress': False}),
        'automount': Choice({
            '--no-automount': False}),
        'tray': Choice({
            '--tray': True,
            '--auto-tray': 'auto'}),
        'file_manager': Value('--file-manager'),
    })

    def _init(self, config, options):

        """Implements _EntryPoint._init."""

        from gi.repository import GObject
        import udiskie.prompt

        mainloop = GObject.MainLoop()
        daemon = get_backend('Daemon', options['udisks_version'])
        browser = udiskie.prompt.browser(options['file_manager'])
        mounter = udiskie.mount.Mounter(
            mount_options=config.mount_options,
            ignore_device=config.ignore_device,
            prompt=udiskie.prompt.password(True),
            browser=browser,
            udisks=daemon)

        # notifications (optional):
        if not options['notify']:
            import udiskie.notify
            from gi.repository import Notify
            Notify.init('udiskie')
            notify = udiskie.notify.Notify(Notify.Notification.new,
                                           mounter=mounter,
                                           timeout=config.notifications)

        # tray icon (optional):
        if options['tray']:
            import udiskie.tray
            tray_classes = {True: udiskie.tray.TrayIcon,
                            'auto': udiskie.tray.AutoTray}
            if options['tray'] not in tray_classes:
                raise ValueError("Invalid tray: %s" % (options['tray'],))
            menu_maker = udiskie.tray.SmartUdiskieMenu(
                mounter,
                {'quit': mainloop.quit})
            TrayIcon = tray_classes[options['tray']]
            statusicon = TrayIcon(menu_maker)
        else:
            statusicon = None

        # automounter
        if options['automount']:
            import udiskie.automount
            udiskie.automount.AutoMounter(mounter)

        # Note: mounter and statusicon are saved so these are kept alive:
        self.mainloop = mainloop
        self.mounter = mounter
        self.statusicon = statusicon

    def run(self):
        """Implements _EntryPoint.run."""
        if self.options['automount']:
            self.mounter.add_all()
        try:
            return self.mainloop.run()
        except KeyboardInterrupt:
            return 0


class Mount(_EntryPoint):

    """
    udiskie-mount: a user-level command line utility for mounting.

    Usage:
        udiskie-mount [-C FILE] [-v|-q] [-1|-2] [-r] [-o OPTIONS] (-a | DEVICE...)
        udiskie-mount (--help | --version)

    General options:
        -C FILE, --config=FILE                  Set config file

        -v, --verbose                           Increase verbosity (DEBUG)
        -q, --quiet                             Decrease verbosity

        -1, --use-udisks1                       Use UDisks1 as backend
        -2, --use-udisks2                       Use UDisks2 as backend

        -h, --help                              Show this help
        -V, --version                           Show version information

    Mount options:
        -a, --all                               Mount all handleable devices
        -r, --recursive                         Recursively mount partitions
        -o OPTIONS, --options OPTIONS           Mount option list
    """

    name = 'udiskie-mount'

    option_defaults = extend(_EntryPoint.option_defaults, {
        'recursive': False,
        'options': None,
        '<device>': None,
    })

    option_rules = extend(_EntryPoint.option_rules, {
        'recursive': Choice({
            '--recursive': True}),
        'options': Value('--options'),
        '<device>': Value('DEVICE'),
    })

    def _init(self, config, options):
        """Implements _EntryPoint._init."""
        import udiskie.prompt
        if options['options']:
            opts = [o.strip() for o in options['options'].split(',')]
            mount_options = lambda dev: opts
        else:
            mount_options = config.mount_options
        self.mounter = udiskie.mount.Mounter(
            mount_options=mount_options,
            ignore_device=config.ignore_device,
            prompt=udiskie.prompt.password(False),
            udisks=get_backend('Sniffer', options['udisks_version']))

    def run(self):
        """Implements _EntryPoint.run."""
        options = self.options
        mounter = self.mounter
        recursive = options['recursive']
        # only mount the desired devices
        if options['<device>']:
            success = True
            for path in options['<device>']:
                success = success and mounter.add(path, recursive=recursive)
        # mount all present devices
        else:
            success = mounter.add_all(recursive=recursive)
        return 0 if success else 1


class Umount(_EntryPoint):

    """
    udiskie-umount: a user-level command line utility for unmounting.

    Usage:
        udiskie-umount [-C FILE] [-v|-q] [-1|-2] [-e] [-d] (-a | DEVICE...)
        udiskie-umount (--help | --version)

    General options:
        -C FILE, --config=FILE      Set config file

        -v, --verbose               Increase verbosity (DEBUG)
        -q, --quiet                 Decrease verbosity

        -1, --use-udisks1           Use UDisks1 as backend
        -2, --use-udisks2           Use UDisks2 as backend

        -h, --help                  Show this help
        -V, --version               Show version information

    Unmount options:
        -a, --all                   Unmount all handleable devices
        -e, --eject                 Eject media from device if possible
        -d, --detach                Power off drive if possible
    """

    name = 'udiskie-umount'

    option_defaults = extend(_EntryPoint.option_defaults, {
        'eject': False,
        'detach': False,
        '<device>': None,
    })

    option_rules = extend(_EntryPoint.option_rules, {
        'eject': Choice({'--eject': True}),
        'detach': Choice({'--detach': True}),
        '<device>': Value('DEVICE'),
    })

    def _init(self, config, options):
        """Implements _EntryPoint._init."""
        self.mounter = udiskie.mount.Mounter(
            udisks=get_backend('Sniffer', options['udisks_version']))

    def run(self):
        """Implements _EntryPoint.run."""
        options = self.options
        mounter = self.mounter
        strategy = dict(detach=options['detach'],
                        eject=options['eject'],
                        lock=True)
        if options['<device>']:
            success = True
            for path in options['<device>']:
                success = mounter.remove(path, **strategy) and success
        else:
            success = mounter.remove_all(**strategy)
        return 0 if success else 1
