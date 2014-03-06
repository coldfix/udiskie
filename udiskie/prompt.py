"""
Udiskie user prompt utility.
"""
__all__ = ['password']

import subprocess
from distutils.spawn import find_executable
import logging

def password(prompt_name='zenity'):
    """
    Create a password prompt function.
    """
    if not prompt_name:
        return None

    executable = find_executable(prompt_name)
    if executable is None:
        return None

    # builtin variant: enter password via zenity:
    if prompt_name == 'zenity':
        def doprompt(text, title):
            return subprocess.check_output([executable,
                '--entry', '--hide-text',
                '--text', text, '--title', title ])

    # builtin variant: enter password via systemd-ask-password:
    elif prompt_name == 'systemd-ask-password':
        def doprompt(text, title):
            return subprocess.check_output([executable, text])

    # enter password via user supplied binary:
    else:
        def doprompt(text, title):
            return subprocess.check_output([executable, text, title])

    def password_prompt(text, title):
        try:
            return doprompt(text, title).decode('utf-8').rstrip('\n')
        except subprocess.CalledProcessError:
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
        return subprocess.call([executable, path])
    return browse
