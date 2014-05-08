"""
User prompt utility.
"""

from distutils.spawn import find_executable
import logging
import subprocess

from gi.repository import Gtk


__all__ = ['password', 'browser']


def require_Gtk():
    """
    Make sure Gtk is properly initialized.

    :raises RuntimeError: if Gtk can not be properly initialized
    """
    # if we attempt to create any GUI elements with no X server running the
    # program will just crash, so let's make a way to catch this case:
    if not Gtk.init_check()[0]:
        raise RuntimeError("X server not connected!")


dialog_definition = r"""
<interface>
  <object class="GtkDialog" id="entry_dialog">
    <property name="border_width">5</property>
    <property name="window_position">center</property>
    <property name="type_hint">dialog</property>
    <child internal-child="vbox">
      <object class="GtkBox">
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
          <object class="GtkButtonBox">
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
    require_Gtk()
    builder = Gtk.Builder.new_from_string(dialog_definition, -1)
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


def password(prompt_name='zenity'):

    """
    Create a password prompt function.

    :param str prompt_name: password program name
    :returns: one-parameter prompt function
    :rtype: callable
    """

    if not prompt_name:
        return None

    text = 'Enter password for {0.device_presentation}:'

    if prompt_name == 'builtin':
        def doprompt(device):
            try:
                return password_dialog("udiskie", text.format(device))
            except RuntimeError:
                pass
        return doprompt

    executable = find_executable(prompt_name)
    if executable is None:
        return None

    # builtin variant: enter password via zenity:
    if prompt_name == 'zenity':
        def doprompt(device):
            return subprocess.check_output([
                executable,
                '--entry', '--hide-text',
                '--text', text.format(device),
                '--title', 'Unlock encrypted device' ])

    # builtin variant: enter password via systemd-ask-password:
    elif prompt_name == 'systemd-ask-password':
        def doprompt(device):
            return subprocess.check_output([executable, text.format(device)])

    # enter password via user supplied binary:
    else:
        def doprompt(device):
            return subprocess.check_output([executable,
                                            device.device_presentation])

    def password_prompt(device):
        try:
            answer = doprompt(device).decode('utf-8')
            # strip trailing newline from program output:
            return answer.rstrip('\n')
        except subprocess.CalledProcessError:
            # usually this means the user cancelled
            return None

    return password_prompt


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
            "Can't find file browser: '%s'. "
            "You may want to change the value for the '-b' option."
            % (browser_name,))
        return None
    def browse(path):
        return subprocess.Popen([executable, path])
    return browse
