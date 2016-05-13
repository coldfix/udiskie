"""
User prompt utility.
"""

from __future__ import absolute_import
from __future__ import unicode_literals

from udiskie.depend import has_Gtk, require_Gtk

from distutils.spawn import find_executable
import getpass
import logging
import shlex
import subprocess
import sys

from .async_ import Async, Coroutine, Return, Subprocess
from .locale import _
from .compat import basestring


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


class Dialog(Async):

    _ACTIVE_INSTANCES = []

    def __init__(self, dialog):
        self._dialog = dialog
        self._dialog.connect("response", self._result_handler)
        self._dialog.show()
        # The connected signal is stored in the dialog, therefore creating a
        # reference cycle (self->dialog->handler->self) that does not protect
        # against garbage collection. Therefore, if the garbage collector gets
        # invoked, the `Dialog` instance and its members are deleted. When the
        # `_result_handler` is invoked, a new (empty) list of  `callbacks` is
        # created - and the original handlers never get invoked. Hence, we
        # need to increase the reference count manually:
        self._ACTIVE_INSTANCES.append(self)

    def _result_handler(self, dialog, response):
        self.callback(response)
        dialog.destroy()
        self._ACTIVE_INSTANCES.remove(self)


@Coroutine.from_generator_function
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
    builder.add_from_string(dialog_definition)
    dialog = builder.get_object('entry_dialog')
    label = builder.get_object('message')
    entry = builder.get_object('entry')
    dialog.set_title(title)
    label.set_label(message)
    dialog.show_all()
    response = yield Dialog(dialog)
    dialog.hide()
    if response == Gtk.ResponseType.OK:
        yield Return(entry.get_text())
    else:
        yield Return(None)


def get_password_gui(device):
    """Get the password to unlock a device from GUI."""
    text = _('Enter password for {0.device_presentation}: ', device)
    try:
        return password_dialog('udiskie', text)
    except RuntimeError:
        return None


@Coroutine.from_generator_function
def get_password_tty(device):
    """Get the password to unlock a device from terminal."""
    # TODO: make this a TRUE async
    text = _('Enter password for {0.device_presentation}: ', device)
    try:
        yield Return(getpass.getpass(text))
    except EOFError:
        print("")
        yield Return(None)


class DeviceCommand(object):

    """
    Launcher that starts user-defined password prompts. The command can be
    specified in terms of a command line template.
    """

    def __init__(self, argv):
        """Create the launcher object from the command line template."""
        if isinstance(argv, basestring):
            self.argv = shlex.split(argv)
        else:
            self.argv = argv

    @Coroutine.from_generator_function
    def __call__(self, device):
        """
        Invoke the subprocess to ask the user to enter a password for unlocking
        the specified device.
        """
        argv = [arg.format(device) for arg in self.argv]
        try:
            stdout = yield Subprocess(argv)
        except subprocess.CalledProcessError:
            yield Return(None)
        yield Return(stdout.rstrip('\n'))


def password(password_command):
    """
    Create a password prompt function.

    :param bool hint_gui: whether a GUI input dialog should be preferred
    """
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
