"""
This module defines the protocol used for asynchronous operations in udiskie.
"""

import asyncio
import traceback

from functools import wraps
from subprocess import CalledProcessError

from gi.repository import Gio


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


def exec_subprocess(argv):
    """
    An Async task that represents a subprocess. If successful, the task's
    result is set to the collected STDOUT of the subprocess.

    :raises subprocess.CalledProcessError: if the subprocess returns a non-zero exit code
    """
    future = asyncio.Future()
    process = Gio.Subprocess.new(argv, Gio.SubprocessFlags.STDOUT_PIPE)
    stdin_buf = None
    cancellable = None
    process.communicate_utf8_async(
        stdin_buf,
        cancellable,
        _exec_subprocess_result,
        future,
        process)
    return future


@gio_callback
def _exec_subprocess_result(proxy, result, process):
    success, stdout, stderr = process.communicate_utf8_finish(result)
    if not success:
        raise RuntimeError("Subprocess did not exit normally!")
    exit_code = process.get_exit_status()
    if exit_code != 0:
        raise CalledProcessError(
            "Subprocess returned a non-zero exit-status!",
            exit_code,
            stdout)
    return stdout
