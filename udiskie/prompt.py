"""
Udiskie user prompt utility.
"""

from distutils.spawn import find_executable
import logging
import subprocess


__all__ = ['password']


def password(prompt_name='zenity'):

    """
    Create a password prompt function.
    """

    if not prompt_name:
        return None

    executable = find_executable(prompt_name)
    if executable is None:
        return None

    text = 'Enter password for {0.device_presentation}:'

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
