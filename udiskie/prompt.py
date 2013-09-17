"""
Udiskie user prompt utility.
"""
__all__ = ['password']

import subprocess
from distutils.spawn import find_executable


def password(prompt_name):
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
            return doprompt(text, title).rstrip('\n')
        except subprocess.CalledProcessError:
            return None

    return password_prompt
