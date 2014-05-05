"""
Command line interface logic.

The application classes in this module are installed as executables via
setuptools entry points.
"""

import logging
import optparse
import sys
import warnings


__all__ = ['Daemon', 'Mount', 'Umount']


warnings.filterwarnings("ignore", ".*could not open display.*", Warning)
warnings.filterwarnings("ignore", ".*g_object_unref.*", Warning)


def udisks_service_object(clsname, version=None):
    """
    Return UDisks service.

    :param str clsname: requested service object
    :param int version: requested udisks backend version
    :returns: udisks service wrapper object
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


class _EntryPoint(object):

    """
    Abstract base class for program entry points.

    Concrete implementations need to implement :meth:`run` and
    :meth:`_init` to be usable with :meth:`main`.
    """

    @classmethod
    def program_options_parser(cls):
        """Return a parser for common program options."""
        parser = optparse.OptionParser()
        parser.add_option('-v', '--verbose', dest='log_level',
                          action='store_const', default=logging.INFO,
                          const=logging.DEBUG, help='verbose output')
        parser.add_option('-q', '--quiet', dest='log_level',
                          action='store_const', default=logging.INFO,
                          const=logging.ERROR, help='quiet output')
        parser.add_option('-1', '--use-udisks1', dest='udisks_version',
                          action='store_const', default=0, const=1,
                          help='use udisks1 as underlying daemon (default)')
        parser.add_option('-2', '--use-udisks2', dest='udisks_version',
                          action='store_const', default=0, const=2,
                          help='use udisks2 as underlying daemon (experimental)')
        parser.add_option('-C', '--config', dest='config_file',
                          action='store', default=None,
                          metavar='FILE', help='config file')
        return parser

    def __init__(self, argv=None):
        """
        Parse command line options, read config and initialize members.

        :param list argv: command line parameters
        """
        import udiskie.config
        # parse program options (retrieve log level and config file name):
        parser = self.program_options_parser()
        options, posargs = parser.parse_args(argv)
        # initialize logging configuration:
        log_level = options.log_level
        if log_level <= logging.DEBUG:
            fmt = '%(levelname)s [%(asctime)s] %(name)s.%(funcName)s(): %(message)s'
        else:
            fmt = '%(message)s'
        logging.basicConfig(level=log_level, format=fmt)
        # parse config options (reparse to get the real values now):
        config = udiskie.config.Config.from_file(options.config_file)
        parser.set_defaults(**config.program_options)
        options, posargs = parser.parse_args(argv)
        # initialize instance variables
        self.config = config
        self.options = options
        self.posargs = posargs
        self._init(config, options, posargs)

    @classmethod
    def main(cls, argv=None):
        """
        Run program.

        :param list argv: command line parameters
        :returns: program exit code
        :rtype: int
        """
        return cls(argv).run()

    def _init(self, config, options, posargs):
        """
        Fully initialize Daemon object.

        :param Config config: configuration object
        :param options: program options as returned by optparse
        :param list posargs: positional arguments as returned by optparse
        """
        raise NotImplementedError("{0}._init".format(self.__class__.__name__))

    def run(self):
        """
        Run main program logic.

        :param options: program options as returned by optparse
        :param list posargs: positional arguments as returned by optparse
        :returns: exit code
        :rtype: int
        """
        raise NotImplementedError("{0}.run".format(self.__class__.__name__))


class Daemon(_EntryPoint):

    """
    Execute udiskie as a daemon.

    The daemon listens to UDisks events and has the following optional
    components:

    - :class:`automount.AutoMounter`
    - :class:`notify.Notify`
    - :class:`tray.TrayIcon`
    """

    @classmethod
    def program_options_parser(cls):
        """Extends _EntryPoint.program_option_parser."""
        parser = _EntryPoint.program_options_parser()
        parser.add_option('-P', '--password-prompt', dest='password_prompt',
                          action='store', default='zenity', metavar='PROGRAM',
                          help="replace password prompt [deprecated]")
        parser.add_option('-s', '--suppress', dest='suppress_notify',
                          action='store_true', default=False,
                          help='suppress popup notifications')
        parser.add_option('-t', '--tray', dest='tray',
                          action='store_const', default=None,
                          const=True, help='show tray icon')
        parser.add_option('-T', '--auto-tray', dest='tray',
                          action='store_const', default=None,
                          const='auto', help='show tray icon')
        parser.add_option('-F', '--file-manager', action='store',
                          dest='file_manager', default='xdg-open',
                          metavar='PROGRAM',
                          help="to open mount pathes [deprecated]")
        parser.add_option('-N', '--no-automount', action='store_false',
                          dest='automount', default=True,
                          help="do not automount new devices")
        return parser

    def _init(self, config, options, posargs):

        """Implements _EntryPoint._init."""

        import gobject
        import udiskie.mount
        import udiskie.prompt

        mainloop = gobject.MainLoop()
        daemon = udisks_service_object('Daemon', options.udisks_version)
        browser = udiskie.prompt.browser(options.file_manager)
        mounter = udiskie.mount.Mounter(
            mount_options=config.mount_options,
            ignore_device=config.ignore_device,
            prompt=udiskie.prompt.password(options.password_prompt),
            browser=browser,
            udisks=daemon)

        # notifications (optional):
        if not options.suppress_notify:
            import udiskie.notify
            try:
                import notify2 as notify_service
            except ImportError:
                import pynotify as notify_service
            notify_service.init('udiskie.mount')
            notify = udiskie.notify.Notify(notify_service,
                                           mounter=mounter,
                                           timeout=config.notifications)

        # tray icon (optional):
        if options.tray:
            import udiskie.tray
            tray_classes = {True: udiskie.tray.TrayIcon,
                            'auto': udiskie.tray.AutoTray}
            if options.tray not in tray_classes:
                raise ValueError("Invalid tray: %s" % (options.tray,))
            menu_maker = udiskie.tray.SmartUdiskieMenu(
                mounter,
                {'quit': mainloop.quit})
            TrayIcon = tray_classes[options.tray]
            statusicon = TrayIcon(menu_maker)
        else:
            statusicon = None

        # automounter
        if options.automount:
            import udiskie.automount
            udiskie.automount.AutoMounter(mounter)

        # Note: mounter and statusicon are saved so these are kept alive:
        self.mainloop = mainloop
        self.mounter = mounter
        self.statusicon = statusicon

    def run(self):
        """Implements _EntryPoint.run."""
        if self.options.automount:
            self.mounter.add_all()
        try:
            return self.mainloop.run()
        except KeyboardInterrupt:
            return 0


class Mount(_EntryPoint):

    """
    Execute the mount command line utility.
    """

    @classmethod
    def program_options_parser(cls):
        """Extends _EntryPoint._program_options_parser."""
        parser = _EntryPoint.program_options_parser()
        parser.add_option('-P', '--password-prompt', dest='password_prompt',
                          action='store', default='zenity', metavar='PROGRAM',
                          help="replace password prompt")
        parser.add_option('-a', '--all', dest='all',
                          action='store_true', default=False,
                          help='mount all present devices')
        parser.add_option('-r', '--recursive', dest='recursive',
                          action='store_true', default=False,
                          help='recursively mount LUKS partitions (if the automount daemon is running, this is not necessary)')
        return parser

    def _init(self, config, options, posargs):
        """Implements _EntryPoint._init."""
        import udiskie.mount
        import udiskie.prompt
        self.mounter = udiskie.mount.Mounter(
            mount_options=config.mount_options,
            ignore_device=config.ignore_device,
            prompt=udiskie.prompt.password(options.password_prompt),
            udisks=udisks_service_object('Sniffer', options.udisks_version))

    def run(self):
        """Implements _EntryPoint.run."""
        options = self.options
        posargs = self.posargs
        mounter = self.mounter
        recursive = options.recursive
        # mount all present devices
        if options.all:
            success = mounter.add_all(recursive=recursive)
        # only mount the desired devices
        elif len(posargs) > 0:
            success = True
            for path in posargs:
                success = success and mounter.add(path, recursive=recursive)
        # print command line options
        else:
            self.program_options_parser().print_help()
            success = False
        return 0 if success else 1


class Umount(_EntryPoint):

    """
    Execute the unmount command line utility.
    """

    @classmethod
    def program_options_parser(cls):
        """Extends _EntryPoint._program_options_parser."""
        parser = _EntryPoint.program_options_parser()
        parser.add_option('-a', '--all', dest='all', default=False,
                          action='store_true', help='all devices')
        parser.add_option('-e', '--eject', dest='eject', default=False,
                          action='store_true', help='Eject media from drive (CDROM etc)')
        parser.add_option('-d', '--detach', dest='detach', default=False,
                          action='store_true', help='Detach drive (power off)')
        return parser

    def _init(self, config, options, posargs):
        """Implements _EntryPoint._init."""
        import udiskie.mount
        self.mounter = udiskie.mount.Mounter(
            udisks=udisks_service_object('Sniffer', options.udisks_version))

    def run(self):
        """Implements _EntryPoint.run."""
        options = self.options
        posargs = self.posargs
        mounter = self.mounter
        if options.all:
            success = mounter.remove_all(detach=options.detach,
                                         eject=options.eject, lock=True)
        elif len(posargs) > 0:
            success = True
            for path in posargs:
                success = (success and
                           mounter.remove(path, detach=options.detach,
                                          eject=options.eject, lock=True))
        else:
            self.program_options_parser().print_help()
            success = False
        return 0 if success else 1
