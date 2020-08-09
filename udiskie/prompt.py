"""
User prompt utility.
"""

from udiskie.depend import has_Gtk, require_Gtk
from udiskie.common import is_utf8

from distutils.spawn import find_executable
import getpass
import logging
import shlex
import string
import subprocess
import sys

try:
    from importlib.resources import read_text
except ImportError:  # for Python<3.7
    from importlib_resources import read_text

from .async_ import exec_subprocess, run_bg, Future
from .locale import _
from .config import DeviceFilter

Gtk = None

__all__ = ['password', 'browser']


dialog_definition = read_text(__package__, 'password_dialog.ui')


class Dialog(Future):

    def __init__(self, window):
        self._enter_count = 0
        self.window = window
        self.window.connect("response", self._result_handler)

    def _result_handler(self, window, response):
        self.set_result(response)

    def __enter__(self):
        self._enter_count += 1
        self._awaken()
        return self

    def __exit__(self, *exc_info):
        self._enter_count -= 1
        if self._enter_count == 0:
            self._cleanup()

    def _awaken(self):
        self.window.present()

    def _cleanup(self):
        self.window.hide()
        self.window.destroy()


class PasswordResult:
    def __init__(self, password=None, cache_hint=None):
        self.password = password
        self.cache_hint = cache_hint


class PasswordDialog(Dialog):

    INSTANCES = {}
    content = None

    @classmethod
    def create(cls, key, title, message, options):
        if key in cls.INSTANCES:
            return cls.INSTANCES[key]
        return cls(key, title, message, options)

    def _awaken(self):
        self.INSTANCES[self.key] = self
        super()._awaken()

    def _cleanup(self):
        del self.INSTANCES[self.key]
        super()._cleanup()

    def __init__(self, key, title, message, options):
        self.key = key
        global Gtk
        Gtk = require_Gtk()
        builder = Gtk.Builder.new()
        builder.add_from_string(dialog_definition)
        window = builder.get_object('entry_dialog')
        self.entry = builder.get_object('entry')

        show_password = builder.get_object('show_password')
        show_password.set_label(_('Show password'))
        show_password.connect('clicked', self.on_show_password)

        allow_keyfile = options.get('allow_keyfile')
        keyfile_button = builder.get_object('keyfile_button')
        keyfile_button.set_label(_('Open keyfile…'))
        keyfile_button.set_visible(allow_keyfile)
        keyfile_button.connect('clicked', run_bg(self.on_open_keyfile))

        allow_cache = options.get('allow_cache')
        cache_hint = options.get('cache_hint')
        self.use_cache = builder.get_object('remember')
        self.use_cache.set_label(_('Cache password'))
        self.use_cache.set_visible(allow_cache)
        self.use_cache.set_active(cache_hint)

        label = builder.get_object('message')
        label.set_label(message)
        window.set_title(title)
        window.set_keep_above(True)
        super().__init__(window)

    def on_show_password(self, button):
        self.entry.set_visibility(button.get_active())

    async def on_open_keyfile(self, button):
        gtk_dialog = Gtk.FileChooserDialog(
            _("Open a keyfile to unlock the LUKS device"), self.window,
            Gtk.FileChooserAction.OPEN,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
             Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        with Dialog(gtk_dialog) as dialog:
            response = await dialog
            if response == Gtk.ResponseType.OK:
                with open(dialog.window.get_filename(), 'rb') as f:
                    self.content = f.read()
                self.window.response(response)

    def get_text(self):
        if self.content is not None:
            return self.content
        return self.entry.get_text()


async def password_dialog(key, title, message, options):
    """
    Show a Gtk password dialog.

    :returns: the password or ``None`` if the user aborted the operation
    :raises RuntimeError: if Gtk can not be properly initialized
    """
    with PasswordDialog.create(key, title, message, options) as dialog:
        response = await dialog
        if response == Gtk.ResponseType.OK:
            return PasswordResult(dialog.get_text(),
                                  dialog.use_cache.get_active())
        return None


def get_password_gui(device, options):
    """Get the password to unlock a device from GUI."""
    text = _('Enter password for {0.device_presentation}: ', device)
    try:
        return password_dialog(device.id_uuid, 'udiskie', text, options)
    except RuntimeError:
        return None


async def get_password_tty(device, options):
    """Get the password to unlock a device from terminal."""
    # TODO: make this a TRUE async
    text = _('Enter password for {0.device_presentation}: ', device)
    try:
        return PasswordResult(getpass.getpass(text))
    except EOFError:
        print("")
        return None


class DeviceCommand:

    """
    Launcher that starts user-defined password prompts. The command can be
    specified in terms of a command line template.
    """

    def __init__(self, argv, capture=False, **extra):
        """Create the launcher object from the command line template."""
        if isinstance(argv, str):
            self.argv = shlex.split(argv)
        else:
            self.argv = argv
        self.capture = capture
        self.extra = extra.copy()
        # obtain a list of used fields names
        formatter = string.Formatter()
        self.used_attrs = set()
        for arg in self.argv:
            for text, kwd, spec, conv in formatter.parse(arg):
                if kwd is None:
                    continue
                if kwd in DeviceFilter.VALID_PARAMETERS:
                    self.used_attrs.add(kwd)
                if kwd not in DeviceFilter.VALID_PARAMETERS and \
                        kwd not in self.extra:
                    self.extra[kwd] = None
                    logging.getLogger(__name__).error(_(
                        'Unknown device attribute {!r} in format string: {!r}',
                        kwd, arg))

    async def __call__(self, device):
        """
        Invoke the subprocess to ask the user to enter a password for unlocking
        the specified device.
        """
        attrs = {attr: getattr(device, attr) for attr in self.used_attrs}
        attrs.update(self.extra)
        argv = [arg.format(**attrs) for arg in self.argv]
        try:
            stdout = await exec_subprocess(argv, self.capture)
        except subprocess.CalledProcessError:
            return None
        # Remove trailing newline for text answers, but not for binary
        # keyfiles. This logic is a guess that may cause bugs for some users:(
        if stdout and stdout.endswith(b'\n') and is_utf8(stdout):
            stdout = stdout[:-1]
        return stdout

    async def password(self, device, options):
        text = await self(device)
        return PasswordResult(text)


def password(password_command):
    """Create a password prompt function."""
    gui = lambda: has_Gtk() and get_password_gui
    tty = lambda: sys.stdin.isatty() and get_password_tty
    if password_command == 'builtin:gui':
        return gui() or tty()
    elif password_command == 'builtin:tty':
        return tty() or gui()
    elif password_command:
        return DeviceCommand(password_command, capture=True).password
    else:
        return None


def browser(browser_name='xdg-open'):

    """Create a browse-directory function."""

    if not browser_name:
        return None
    argv = shlex.split(browser_name)
    executable = find_executable(argv[0])
    if executable is None:
        # Why not raise an exception? -I think it is more convenient (for
        # end users) to have a reasonable default, without enforcing it.
        logging.getLogger(__name__).warn(
            _("Can't find file browser: {0!r}. "
              "You may want to change the value for the '-f' option.",
              browser_name))
        return None

    def browse(path):
        return subprocess.Popen(argv + [path])

    return browse


def notify_command(command_format, mounter):
    """
    Command notification tool.

    This works similar to Notify, but will issue command instead of showing
    the notifications on the desktop. This can then be used to react to events
    from shell scripts.

    The command can contain modern pythonic format placeholders like:
    {device_file}. The following placeholders are supported:
    event, device_file, device_id, device_size, drive, drive_label, id_label,
    id_type, id_usage, id_uuid, mount_path, root

    :param str command_format: command to run when an event occurs.
    :param mounter: Mounter object
    """
    udisks = mounter.udisks
    for event in ['device_mounted', 'device_unmounted',
                  'device_locked', 'device_unlocked',
                  'device_added', 'device_removed',
                  'job_failed']:
        udisks.connect(event, run_bg(DeviceCommand(
            command_format, event=event, capture=False)))
