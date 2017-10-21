"""
This module defines the protocol used for asynchronous operations in udiskie.
"""

import asyncio
import traceback

from subprocess import CalledProcessError, PIPE
from asyncio.subprocess import create_subprocess_exec

from .common import wraps


__all__ = [
    'pack',
    'to_coro',
    'run_bg',
]


def pack(*values):
    """Unpack a return tuple to a yield expression return value."""
    # Schizophrenic returns from asyncs. Inspired by
    # gi.overrides.Gio.DBusProxy.
    if len(values) == 0:
        return None
    elif len(values) == 1:
        return values[0]
    else:
        return values


def to_coro(func):
    @wraps(func)
    async def coro(*args, **kwargs):
        return func(*args, **kwargs)
    return coro


def run_bg(func):
    @wraps(func)
    def runner(*args, **kwargs):
        future = asyncio.ensure_future(func(*args, **kwargs))
        future.add_done_callback(show_traceback)
        return future
    return runner


def show_traceback(future):
    try:
        future.result()
    except Exception:
        traceback.print_exc()


def gio_callback(extract_result):
    def callback(proxy, result, future, *args):
        try:
            value = extract_result(proxy, result, *args)
        except Exception as e:
            future.set_exception(e)
        else:
            future.set_result(value)
    return callback


async def exec_subprocess(argv):
    """
    An Async task that represents a subprocess. If successful, the task's
    result is set to the collected STDOUT of the subprocess.

    :raises subprocess.CalledProcessError: if the subprocess returns a non-zero exit code
    """
    process = await create_subprocess_exec(*argv, stdout=PIPE)
    stdout, stderr = await process.communicate()
    stdout = stdout.decode('utf-8')
    exit_code = await process.wait()
    if exit_code != 0:
        raise CalledProcessError(
            "Subprocess returned a non-zero exit-status!",
            exit_code,
            stdout)
    return stdout
