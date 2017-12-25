"""
User prompt utility.
"""

from udiskie.depend import has_Gtk, require_Gtk

import asyncio

from distutils.spawn import find_executable
import getpass
import logging
import re
import shlex
import string
import subprocess
import sys

from .async_ import exec_subprocess, run_bg
from .locale import _
from .common import AttrDictView
from .config import DeviceFilter

Gtk = None

__all__ = ['password', 'browser']


dialog_definition = r"""
<interface>
  <object class="GtkDialog" id="entry_dialog">
    <property name="border_width">5</property>
    <property name="window_position">center</property>
    <property name="type_hint">dialog</property>
    <child internal-child="vbox">
      <object class="GtkBox" id="entry_box">
        <property name="spacing">6</property>
        <property name="border_width">6</property>
        <property name="visible">True</property>
        <child>
          <object class="GtkLabel" id="message">
            <property name="xalign">0</property>
            <property name="visible">True</property>
          </object>
        </child>
        <child>
          <object class="GtkEntry" id="entry">
            <property name="visibility">False</property>
            <property name="activates_default">True</property>
            <property name="visible">True</property>
          </object>
        </child>
        <child internal-child="action_area">
          <object class="GtkButtonBox" id="action_box">
            <property name="visible">True</property>
            <child>
              <object class="GtkButton" id="cancel_button">
                <property name="label">gtk-cancel</property>
                <property name="use_stock">True</property>
                <property name="visible">True</property>
              </object>
            </child>
            <child>
              <object class="GtkButton" id="ok_button">
                <property name="label">gtk-ok</property>
                <property name="use_stock">True</property>
                <property name="can_default">True</property>
                <property name="has_default">True</property>
                <property name="visible">True</property>
              </object>
            </child>
          </object>
        </child>
      </object>
    </child>
    <action-widgets>
      <action-widget response="-6">cancel_button</action-widget>
      <action-widget response="-5">ok_button</action-widget>
    </action-widgets>
  </object>
</interface>
"""


class Dialog(asyncio.Future):

    def __init__(self, window):
        super().__init__()
        self.window = window
        self.window.connect("response", self._result_handler)
        self.window.show()

    def _result_handler(self, window, response):
        self.set_result(response)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.window.hide()
        self.window.destroy()


class PasswordDialog(Dialog):

    content = None

    def __init__(self, title, message, allow_keyfile):
        global Gtk
        Gtk = require_Gtk()
        builder = Gtk.Builder.new()
        builder.add_from_string(dialog_definition)
        window = builder.get_object('entry_dialog')
        self.entry = builder.get_object('entry')
        if allow_keyfile:
            button = Gtk.Button(_('Open keyfile…'))
            button.set_visible(True)
            button.connect('clicked', run_bg(self.on_open_keyfile))
            window.get_action_area().pack_end(button, False, False, 10)

        label = builder.get_object('message')
        label.set_label(message)
        window.set_title(title)
        window.set_keep_above(True)
        super(PasswordDialog, self).__init__(window)

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


async def password_dialog(title, message, allow_keyfile):
    """
    Show a Gtk password dialog.

    :returns: the password or ``None`` if the user aborted the operation
    :raises RuntimeError: if Gtk can not be properly initialized
    """
    with PasswordDialog(title, message, allow_keyfile) as dialog:
        response = await dialog
        if response == Gtk.ResponseType.OK:
            return dialog.get_text()
        return None


def get_password_gui(device, allow_keyfile=False):
    """Get the password to unlock a device from GUI."""
    text = _('Enter password for {0.device_presentation}: ', device)
    try:
        return password_dialog('udiskie', text, allow_keyfile)
    except RuntimeError:
        return None


async def get_password_tty(device, allow_keyfile=False):
    """Get the password to unlock a device from terminal."""
    # TODO: make this a TRUE async
    text = _('Enter password for {0.device_presentation}: ', device)
    try:
        return getpass.getpass(text)
    except EOFError:
        print("")
        return None


class DeviceCommand:

    """
    Launcher that starts user-defined password prompts. The command can be
    specified in terms of a command line template.
    """

    def __init__(self, argv, **extra):
        """Create the launcher object from the command line template."""
        if isinstance(argv, str):
            self.argv = shlex.split(argv)
        else:
            self.argv = argv
        self.extra = extra.copy()
        # obtain a list of used fields names
        formatter = string.Formatter()
        field_name = re.compile('(\d*\.)?(\w+)')
        self.used_attrs = []
        for arg in self.argv:
            for text, name, spec, conv in formatter.parse(arg):
                if name is None:
                    continue
                pos, kwd = field_name.match(name).groups()
                if pos is not None:
                    logging.getLogger(__name__).warn(
                        _('Positional field in format string {!r} is deprecated.', arg))
                # check used field names
                if kwd in self.used_attrs or kwd in self.extra:
                    continue
                if kwd in DeviceFilter.VALID_PARAMETERS:
                    self.used_attrs.append(kwd)
                else:
                    self.extra[kwd] = None
                    logging.getLogger(__name__).error(_(
                        'Unknown device attribute {!r} in format string: {!r}',
                        kwd, arg))

    # NOTE: *ignored swallows `allow_keyfile`
    async def __call__(self, device, *ignored):
        """
        Invoke the subprocess to ask the user to enter a password for unlocking
        the specified device.
        """
        attrs = {attr: getattr(device, attr) for attr in self.used_attrs}
        attrs.update(self.extra)
        # for backward compatibility provide positional argument:
        fake_dev = AttrDictView(attrs)
        argv = [arg.format(fake_dev, **attrs) for arg in self.argv]
        try:
            stdout = await exec_subprocess(argv)
        except subprocess.CalledProcessError:
            return None
        return stdout.rstrip('\n')


def password(password_command):
    """Create a password prompt function."""
    gui = lambda: has_Gtk()          and get_password_gui
    tty = lambda: sys.stdin.isatty() and get_password_tty
    if password_command == 'builtin:gui':
        return gui() or tty()
    elif password_command == 'builtin:tty':
        return tty() or gui()
    elif password_command:
        return DeviceCommand(password_command)
    else:
        return None


def browser(browser_name='xdg-open'):

    """Create a browse-directory function."""

    if not browser_name:
        return None
    executable = find_executable(browser_name)
    if executable is None:
        # Why not raise an exception? -I think it is more convenient (for
        # end users) to have a reasonable default, without enforcing it.
        logging.getLogger(__name__).warn(
            _("Can't find file browser: {0!r}. "
              "You may want to change the value for the '-f' option.",
              browser_name))
        return None

    def browse(path):
        return subprocess.Popen([executable, path])

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

    :param str command_format: The command format string to run when an event occurs.
    :param mounter: Mounter object
    """
    udisks = mounter.udisks
    for event in ['device_mounted', 'device_unmounted',
                  'device_locked', 'device_unlocked',
                  'device_added', 'device_removed',
                  'job_failed']:
        udisks.connect(event, run_bg(DeviceCommand(command_format, event=event)))
