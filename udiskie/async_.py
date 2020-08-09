"""
Lightweight asynchronous framework.

This module defines the protocol used for asynchronous operations in udiskie.
It is based on ideas from "Twisted" and the "yield from" expression in
python3, but more lightweight (incomplete) and compatible with python2.
"""

import traceback
from functools import partial
from subprocess import CalledProcessError

from gi.repository import GLib
from gi.repository import Gio

from .common import cachedproperty, wraps


__all__ = [
    'pack',
    'to_coro',
    'run_bg',
    'Future',
    'gather',
    'Task',
]


ACTIVE_TASKS = set()


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


class Future:

    """
    Base class for asynchronous operations.

    One `Future' object represents an asynchronous operation. It allows for
    separate result and error handlers which can be set by appending to the
    `callbacks` and `errbacks` lists.

    Implementations must conform to the following very lightweight protocol:

    The task is started on initialization, but most not finish immediately.

    Success/error exit is signaled to the observer by calling exactly one of
    `self.set_result(value)` or `self.set_exception(exception)` when the
    operation finishes.

    For implementations, see :class:`Task` or :class:`Dialog`.
    """

    @cachedproperty
    def callbacks(self):
        """Functions to be called on successful completion."""
        return []

    @cachedproperty
    def errbacks(self):
        """Functions to be called on error completion."""
        return []

    def _finish(self, callbacks, *args):
        """Set finished state and invoke specified callbacks [internal]."""
        return [fn(*args) for fn in callbacks]

    def set_result(self, value):
        """Signal successful completion."""
        self._finish(self.callbacks, value)

    def set_exception(self, exception):
        """Signal unsuccessful completion."""
        was_handled = self._finish(self.errbacks, exception)
        if not was_handled:
            traceback.print_exception(
                type(exception), exception, exception.__traceback__)

    def __await__(self):
        ACTIVE_TASKS.add(self)
        try:
            return (yield self)
        finally:
            ACTIVE_TASKS.remove(self)


def to_coro(func):
    @wraps(func)
    async def coro(*args, **kwargs):
        return func(*args, **kwargs)
    return coro


def run_bg(func):
    @wraps(func)
    def runner(*args, **kwargs):
        return ensure_future(func(*args, **kwargs))
    return runner


class gather(Future):

    """
    Manages a collection of asynchronous tasks.

    The callbacks are executed when all of the subtasks have completed.
    """

    def __init__(self, *tasks):
        """Create from a list of `Future`-s."""
        tasks = list(tasks)
        self._done = False
        self._results = {}
        self._num_tasks = len(tasks)
        if not tasks:
            run_soon(self.set_result, [])
        for idx, task in enumerate(tasks):
            task = ensure_future(task)
            task.callbacks.append(partial(self._subtask_result, idx))
            task.errbacks.append(partial(self._subtask_error, idx))

    def _subtask_result(self, idx, value):
        """Receive a result from a single subtask."""
        self._results[idx] = value
        if len(self._results) == self._num_tasks:
            self.set_result([
                self._results[i]
                for i in range(self._num_tasks)
            ])

    def _subtask_error(self, idx, error):
        """Receive an error from a single subtask."""
        self.set_exception(error)
        self.errbacks.clear()


def call_func(fn, *args):
    """
    Call the function with the specified arguments but return None.

    This rather boring helper function is used by run_soon to make sure the
    function is executed only once.
    """
    # NOTE: Apparently, idle_add does not re-execute its argument if an
    # exception is raised. So it's okay to let exceptions propagate.
    fn(*args)


def run_soon(fn, *args):
    """Run the function once."""
    GLib.idle_add(call_func, fn, *args)


def sleep(seconds):
    future = Future()
    GLib.timeout_add(int(seconds*1000), future.set_result, True)
    return future


def ensure_future(awaitable):
    if isinstance(awaitable, Future):
        return awaitable
    return Task(iter(awaitable.__await__()))


class Task(Future):

    """Turns a generator into a Future."""

    def __init__(self, generator):
        """Create and start a ``Task`` from the specified generator."""
        self._generator = generator
        run_soon(self._resume, next, self._generator)

    def _resume(self, func, *args):
        """Resume the coroutine by throwing a value or returning a value from
        the ``await`` and handle further awaits."""
        try:
            value = func(*args)
        except StopIteration:
            self._generator.close()
            self.set_result(None)
        except Exception as e:
            self._generator.close()
            self.set_exception(e)
        else:
            assert isinstance(value, Future)
            value.callbacks.append(partial(self._resume, self._generator.send))
            value.errbacks.append(partial(self._resume, self._generator.throw))


def gio_callback(proxy, result, future):
    future.set_result(result)


async def exec_subprocess(argv, capture=True):
    """
    An Future task that represents a subprocess. If successful, the task's
    result is set to the collected STDOUT of the subprocess.

    :raises subprocess.CalledProcessError: if the subprocess returns a non-zero
                                           exit code
    """
    future = Future()
    flags = ((Gio.SubprocessFlags.STDOUT_PIPE if capture else
              Gio.SubprocessFlags.NONE) |
             Gio.SubprocessFlags.STDIN_INHERIT)
    process = Gio.Subprocess.new(argv, flags)
    stdin_buf = None
    cancellable = None
    process.communicate_async(
        stdin_buf, cancellable, gio_callback, future)
    result = await future
    success, stdout, stderr = process.communicate_finish(result)
    stdout = stdout.get_data() if capture else None     # GLib.Bytes -> bytes
    if not success:
        raise RuntimeError("Subprocess did not exit normally!")
    exit_code = process.get_exit_status()
    if exit_code != 0:
        raise CalledProcessError(
            "Subprocess returned a non-zero exit-status!",
            exit_code,
            stdout)
    return stdout
