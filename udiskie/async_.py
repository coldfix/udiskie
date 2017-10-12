"""
This module defines the protocol used for asynchronous operations in udiskie.
"""

# NOTE: neither AsyncList nor Coroutine save references to the active tasks!
# Although this would create a reference cycle (coro->task->callbacks->coro),
# the garbage collector can generally detect the cycle and delete the involved
# objects anyway (there is usually no independent reference to the coroutine).
# So you must take care to increase the reference-count of all active tasks
# manually.

import asyncio

from functools import partial, wraps
from subprocess import CalledProcessError
import sys

from gi.repository import Gio

from .common import cachedproperty, wraps, format_exc


__all__ = [
    'Async',
    'AsyncList',
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


Async = asyncio.Future


def to_coro(func):
    @wraps(func)
    async def coro(*args, **kwargs):
        return func(*args, **kwargs)
    return coro


def run_bg(func):
    @wraps(func)
    def runner(*args, **kwargs):
        return asyncio.ensure_future(func(*args, **kwargs))
    return runner


def AsyncList(tasks):
    return asyncio.gather(*tasks)


def gio_callback(extract_result):
    def callback(proxy, result, future, *args):
        try:
            value = extract_result(proxy, result, *args)
        except Exception as e:
            future.set_exception(e)
        else:
            future.set_result(value)
    return callback


def Subprocess(argv):
    """
    An Async task that represents a subprocess. If successful, the task's
    result is set to the collected STDOUT of the subprocess.

    :raises subprocess.CalledProcessError: if the subprocess returns a non-zero exit code
    """
    future = Async()
    process = Gio.Subprocess.new(argv, Gio.SubprocessFlags.STDOUT_PIPE)
    stdin_buf = None
    cancellable = None
    process.communicate_utf8_async(
        stdin_buf,
        cancellable,
        _Subprocess_callback,
        future,
        process)
    return future


@gio_callback
def _Subprocess_callback(proxy, result, process):
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
