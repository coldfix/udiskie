"""
Udiskie CLI entry points.
"""
__all__ = ['Daemon', 'Mount', 'Umount']

import warnings
warnings.filterwarnings("ignore", ".*could not open display.*", Warning)
warnings.filterwarnings("ignore", ".*g_object_unref.*", Warning)

import optparse
import sys
import logging
from functools import partial

def udisks_service_object(clsname, version=None):
    """
    Return UDisks service.

    :param str clsname: requested service object
    :param int version: requested udisks backend version
    :return: udisks service wrapper object
    :raises dbus.DBusException: if unable to connect to UDisks dbus service.
    :raises ValueError: if the version is invalid

    If ``version`` has a false truth value, try to connect to UDisks1 and
    fall back to UDisks2 if not available.

    """
    def udisks1():
        import udiskie.udisks1
        return getattr(udiskie.udisks1, clsname).create()
    def udisks2():
        import udiskie.udisks2
        return getattr(udiskie.udisks2, clsname).create()
    if not version:
        from udiskie.common import DBusException
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
    Base class for other entry points.
    """
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    @classmethod
    def program_options_parser(cls):
        """
        Return a command line option parser for options common to all modes.
        """
        parser = optparse.OptionParser()
        parser.add_option('-v', '--verbose', dest='log_level',
                          action='store_const', default=logging.INFO,
                          const=logging.DEBUG, help='verbose output')
        parser.add_option('-1', '--use-udisks1', dest='udisks_version',
                          action='store_const', default=0, const=1,
                          help='use udisks1 as underlying daemon (default)')
        parser.add_option('-2', '--use-udisks2', dest='udisks_version',
                          action='store_const', default=0, const=2,
                          help='use udisks2 as underlying daemon (experimental)')
        parser.add_option('-f', '--filters', dest='config_file',
                          action='store', default=None,
                          metavar='FILE', help='synonym of --config [deprecated]')
        parser.add_option('-C', '--config', dest='config_file',
                          action='store', default=None,
                          metavar='FILE', help='config file')
        return parser

    @classmethod
    def main(cls, argv=None):
        """
        Run the entry point.
        """
        import udiskie.config

        # parse program options (retrieve log level and config file name):
        parser = cls.program_options_parser()
        options, posargs = parser.parse_args(argv)

        # initialize logging configuration:
        log_level = options.log_level
        if log_level <= logging.DEBUG:
            fmt = '%(levelname)s [%(asctime)s] %(name)s.%(funcName)s(): %(message)s'
        else:
            fmt = '%(message)s'
        logging.basicConfig(level=log_level, format=fmt)

        # parse config options (reparse to get the real values now):
        config = udiskie.config.Config.from_config_file(options.config_file)
        parser.set_defaults(**config.program_options)
        options, posargs = parser.parse_args(argv)

        return cls.create(config, options, posargs).run(options, posargs)


class Daemon(_EntryPoint):
    """
    Execute udiskie as a daemon.
    """
    @classmethod
    def program_options_parser(cls):
        parser = _EntryPoint.program_options_parser()
        parser.add_option('-P', '--password-prompt', dest='password_prompt',
                          action='store', default='zenity', metavar='PROGRAM',
                          help="replace password prompt")
        parser.add_option('-s', '--suppress', dest='suppress_notify',
                          action='store_true', default=False,
                          help='suppress popup notifications')
        parser.add_option('-t', '--tray', dest='tray',
                          action='store_true', default=False,
                          help='show tray icon')
        parser.add_option('-F', '--file-manager', action='store',
                          dest='file_manager', default='xdg-open',
                          metavar='PROGRAM', help="to open mount pathes")
        return parser

    @classmethod
    def create(cls, config, options, posargs):
        import gobject
        import udiskie.automount
        import udiskie.mount
        import udiskie.prompt

        mainloop = gobject.MainLoop()
        daemon = udisks_service_object('Daemon', int(options.udisks_version))
        browser = udiskie.prompt.browser(options.file_manager)
        mounter = udiskie.mount.Mounter(
            filter=config.filter_options,
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
                                           browser=browser,
                                           config=config.notifications)
            notify.subscribe(daemon)

        # tray icon (optional):
        if options.tray:
            import udiskie.tray
            menu_maker = udiskie.tray.SmartUdiskieMenu.create(mounter)
            menu_maker._actions['quit'] = mainloop.quit
            statusicon = udiskie.tray.TrayIcon(menu_maker)
        else:
            status_icon = None

        # automounter
        automount = udiskie.automount.AutoMounter(mounter)
        daemon.connect(automount)
        # Note: mounter and statusicon are saved so these are kept alive:
        return cls(mainloop=mainloop,
                   mounter=mounter,
                   statusicon=statusicon)

    def run(self, options, posargs):
        self.mounter.mount_all()
        try:
            return self.mainloop.run()
        except KeyboardInterrupt:
            return 0

class Mount(_EntryPoint):
    """
    Execute the mount command.
    """
    @classmethod
    def program_options_parser(cls):
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

    @classmethod
    def create(cls, config, options, posargs):
        import udiskie.mount
        import udiskie.prompt
        mounter = udiskie.mount.Mounter(
            filter=config.filter_options,
            prompt=udiskie.prompt.password(options.password_prompt),
            udisks=udisks_service_object('Sniffer', int(options.udisks_version)))
        return cls(mounter=mounter)

    def run(self, options, posargs):
        mounter = self.mounter
        recursive = options.recursive

        # mount all present devices
        if options.all:
            success = mounter.mount_all(recursive=recursive)
        # only mount the desired devices
        elif len(posargs) > 0:
            success = True
            for path in posargs:
                success = success and mounter.mount(path, recursive=recursive)
        # print command line options
        else:
            self.program_options_parser().print_help()
            success = False

        return 0 if success else 1

class Umount(_EntryPoint):
    """
    Execute the umount command.
    """
    @classmethod
    def program_options_parser(cls):
        parser = _EntryPoint.program_options_parser()
        parser.add_option('-a', '--all', dest='all', default=False,
                          action='store_true', help='all devices')
        parser.add_option('-e', '--eject', dest='eject', default=False,
                          action='store_true', help='Eject drive')
        parser.add_option('-d', '--detach', dest='detach', default=False,
                          action='store_true', help='Detach drive')
        return parser

    @classmethod
    def create(cls, config, options, posargs):
        import udiskie.mount
        mounter = udiskie.mount.Mounter(
            udisks=udisks_service_object('Sniffer', int(options.udisks_version)))
        return cls(mounter=mounter)

    def run(self, options, posargs):
        mounter = self.mounter
        if options.all:
            success = mounter.unmount_all(detach=options.detach,
                                          eject=options.eject, lock=True)
        elif len(posargs) > 0:
            success = True
            for path in posargs:
                success = (success and
                           mounter.unmount(path, detach=options.detach,
                                           eject=options.eject, lock=True))
        else:
            self.program_options_parser().print_help()
            success = False
        return 0 if success else 1

