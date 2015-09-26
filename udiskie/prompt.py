"""
User prompt utility.
"""

from distutils.spawn import find_executable
import getpass
import logging
import subprocess
import sys

from udiskie.locale import _
from udiskie.compat import basestring


__all__ = ['password', 'browser']


def require_Gtk():
    """
    Make sure Gtk is properly initialized.

    :raises RuntimeError: if Gtk can not be properly initialized
    """
    from gi.repository import Gtk
    # if we attempt to create any GUI elements with no X server running the
    # program will just crash, so let's make a way to catch this case:
    if not Gtk.init_check(None)[0]:
        raise RuntimeError(_("X server not connected!"))
    return Gtk


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
        <child>
          <object class="GtkLabel" id="message">
            <property name="xalign">0</property>
          </object>
        </child>
        <child>
          <object class="GtkEntry" id="entry">
            <property name="visibility">False</property>
            <property name="activates_default">True</property>
          </object>
        </child>
        <child internal-child="action_area">
          <object class="GtkButtonBox" id="action_box">
            <child>
              <object class="GtkButton" id="cancel_button">
                <property name="label">gtk-cancel</property>
                <property name="use_stock">True</property>
              </object>
            </child>
            <child>
              <object class="GtkButton" id="ok_button">
                <property name="label">gtk-ok</property>
                <property name="use_stock">True</property>
                <property name="can_default">True</property>
                <property name="has_default">True</property>
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


def password_dialog(title, message):
    """
    Show a Gtk password dialog.

    :param str title:
    :param str message:
    :returns: the password or ``None`` if the user aborted the operation
    :rtype: str
    :raises RuntimeError: if Gtk can not be properly initialized
    """
    Gtk = require_Gtk()
    builder = Gtk.Builder.new()
    builder.add_from_string (dialog_definition)
    dialog = builder.get_object('entry_dialog')
    label = builder.get_object('message')
    entry = builder.get_object('entry')
    dialog.set_title(title)
    label.set_label(message)
    dialog.show_all()
    response = dialog.run()
    dialog.hide()
    if response == Gtk.ResponseType.OK:
        return entry.get_text()
    else:
        return None


def get_password_gui(device):
    """Get the password to unlock a device from GUI."""
    text = _('Enter password for {0.device_presentation}: ', device)
    try:
        return password_dialog('udiskie', text)
    except RuntimeError:
        return None


def get_password_tty(device):
    """Get the password to unlock a device from terminal."""
    text = _('Enter password for {0.device_presentation}: ', device)
    try:
        return getpass.getpass(text)
    except EOFError:
        print("")
        return None


class DeviceCommand(object):

    def __init__(self, argv):
        self.argv = argv

    def __call__(self, device):
        if isinstance(self.argv, basestring):
            argv = self.argv.format(device)
            shell = True
        else:
            argv = [arg.format(device) for arg in self.argv]
            shell = False
        try:
            blob = subprocess.check_output(argv, shell=shell)
        except subprocess.CalledProcessError:
            return None
        return blob.decode('utf-8').rstrip('\n')


def password(password_command):

    """
    Create a password prompt function.

    :param bool hint_gui: whether a GUI input dialog should be preferred
    """

    def gui():
        try:
            require_Gtk()
            return get_password_gui
        except (RuntimeError, ImportError):
            return None

    def tty():
        if sys.stdin.isatty():
            return get_password_tty
        else:
            return None

    if password_command == 'builtin:gui':
        return gui() or tty()
    elif password_command == 'builtin:tty':
        return tty() or gui()
    elif password_command:
        return DeviceCommand(password_command)
    else:
        return None


def browser(browser_name='xdg-open'):

    """
    Create a browse-directory function.

    :param str browser_name: file manager program name
    :returns: one-parameter open function
    :rtype: callable
    """

    if not browser_name:
        return None
    executable = find_executable(browser_name)
    if executable is None:
        # Why not raise an exception? -I think it is more convenient (for
        # end users) to have a reasonable default, without enforcing it.
        logging.getLogger(__name__).warn(
            _("Can't find file browser: {0!r}. "
              "You may want to change the value for the '-b' option.",
              browser_name))
        return None

    def browse(path):
        return subprocess.Popen([executable, path])

    return browse
