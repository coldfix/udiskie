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
    'Return',
    'Coroutine',
]

# NOTE: neither gather nor Coroutine save references to the active tasks!
# Although this would create a reference cycle (coro->task->callbacks->coro),
# the garbage collector can generally detect the cycle and delete the involved
# objects anyway (there is usually no independent reference to the coroutine).
# So we must take care to increase the reference-count of all active tasks
# manually:
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

    For implementations, see :class:`Coroutine` and :class:`DBusCall`.
    """

    done = False

    def __init__(self):
        ACTIVE_TASKS.add(self)

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
        if self.done:
            # TODO: more output
            raise RuntimeError("Future already finished!")
        ACTIVE_TASKS.remove(self)
        self.done = True
        # TODO: handle Future callbacks:
        return [fn(*args) for fn in callbacks]

    # accept multiple values for convenience (for now!):
    def set_result(self, value):
        """Signal successful completion."""
        self._finish(self.callbacks, value)

    def set_exception(self, exception):
        """Signal unsuccessful completion."""
        was_handled = self._finish(self.errbacks, exception)
        if not any(was_handled):
            traceback.print_exception(
                type(exception), exception, exception.__traceback__)

    def __await__(self):
        return (yield self)


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
        super().__init__()
        tasks = list(tasks)
        self._results = {}
        self._num_tasks = len(tasks)
        if not tasks:
            run_soon(self.set_result, [])
        for idx, task in enumerate(tasks):
            task = ensure_future(task)
            task.callbacks.append(partial(self._subtask_result, idx))
            task.errbacks.append(partial(self._subtask_error, idx))

    def _set_subtask_result(self, idx, result):
        """Set result of a single subtask."""
        self._results[idx] = result
        if len(self._results) == self._num_tasks:
            self.set_result([
                self._results[i]
                for i in range(self._num_tasks)
            ])

    def _subtask_result(self, idx, value):
        """Receive a result from a single subtask."""
        self._set_subtask_result(idx, AsyncResult(True, value))

    def _subtask_error(self, idx, error):
        """Receive an error from a single subtask."""
        self._set_subtask_result(idx, AsyncResult(False, error))


class AsyncResult:

    def __init__(self, success, *values):
        self.success = success
        self.values = values

    def __bool__(self):
        return self.success and all(self.values)

    __nonzero__ = __bool__


class Return:

    """Wraps a return value from a coroutine."""

    def __init__(self, value=None):
        self.value = value


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
    return Coroutine(iter(awaitable.__await__()))


class Coroutine(Future):

    """
    A coroutine processes a sequence of asynchronous tasks.

    Coroutines resemble non-atomic asynchronous operations. They merely
    aggregate and operate on the results of zero or more asynchronous
    subtasks.

    Coroutines are scheduled for execution by just calling them. In that
    regard, they behave very similar to normal functions. The difference is,
    that they return an Future object rather than a result. This object can
    then be used to add result handler callbacks. The coroutine's code block
    will first be entered in a separate main loop iteration.

    Coroutines are implemented as generators using `yield` expressions to
    transfer control flow when performing asynchronous tasks. Coroutines may
    yield zero or more `Future` tasks and one final `Return` value.

    The code after a `yield` expression is executed only after the yielded
    `Future` has finished. In case of successful completion, the result of the
    asynchronous operation is returned. In case of an error, the exception is
    raised inside the generator. For example:

    >>> @Coroutine.from_generator_function
    ... def foo(*args):
    ...     # perform synchronous calculations here:
    ...     other_args = f(args)
    ...     try:
    ...         # Invoke another asynchronous routine. Potentialy passes
    ...         # control flow to main loop:
    ...         result = yield subroutine(other_args)
    ...     except ValueError:
    ...         # Handle errors raised by the asynchronous subroutine. These
    ...         # are sent here from the callback function.
    ...         pass
    ...     # `result` now contains the `Return` value of the sub-routine and
    ...     # can be used for further calculations:
    ...     value = g(result)
    ...     # Set our own `Return` value. This must be the last statement:
    ...     yield Return(value)
    """

    @classmethod
    def from_generator_function(cls, generator_function):
        """Turn a generator function into a coroutine function."""
        @wraps(generator_function)
        def coroutine_function(*args, **kwargs):
            return cls(generator_function(*args, **kwargs))
        coroutine_function.__func__ = generator_function
        return coroutine_function

    def __init__(self, generator):
        """
        Create and start a `Coroutine` task from the specified generator.
        """
        super().__init__()
        self._generator = generator
        # TODO: cancellable tasks (generator.close() -> GeneratorExit)?
        run_soon(self._interact, next, self._generator)

    # TODO: shorten stack traces by inlining _recv / _interact ?

    def _recv(self, thing):
        """
        Handle a value received from (yielded by) the generator.

        This function is called immediately after the generator suspends its
        own control flow by yielding a value.
        """
        if isinstance(thing, Future):
            thing.callbacks.append(self._send)
            thing.errbacks.append(self._throw)
        elif isinstance(thing, Return):
            self._generator.close()
            # self.set_result(thing.value)
            # to shorten stack trace use instead:
            run_soon(self.set_result, thing.value)
        else:
            # the protocol is easy to do wrong, therefore we better do not
            # silently ignore any errors!
            raise NotImplementedError(
                ("Unexpected return value from function {!r}: {!r}.\n"
                 "Expecting either an Future or a Return.")
                .format(self._generator, thing))

    def _send(self, value):
        """
        Interact with the coroutine by sending a value.

        Set the return value of the current `yield` expression to the
        specified value and resume control flow inside the coroutine.
        """
        self._interact(self._generator.send, value)

    def _throw(self, exc):
        """
        Interact with the coroutine by raising an exception.

        Transfer the control flow back to the coroutine by raising an
        exception from the `yield` expression.
        """
        self._interact(self._generator.throw, exc)
        return True

    def _interact(self, func, *args):
        """
        Interact with the coroutine by performing the specified operation.
        """
        try:
            value = func(*args)
        except StopIteration:
            self._generator.close()
            self.set_result(None)
        except Exception as e:
            self._generator.close()
            self.set_exception(e)
        else:
            self._recv(value)


def gio_callback(proxy, result, future):
    future.set_result(result)


async def exec_subprocess(argv):
    """
    An Future task that represents a subprocess. If successful, the task's
    result is set to the collected STDOUT of the subprocess.

    :raises subprocess.CalledProcessError: if the subprocess returns a non-zero
                                           exit code
    """
    future = Future()
    process = Gio.Subprocess.new(
        argv,
        Gio.SubprocessFlags.STDOUT_PIPE |
        Gio.SubprocessFlags.STDIN_INHERIT)
    stdin_buf = None
    cancellable = None
    process.communicate_utf8_async(
        stdin_buf, cancellable, gio_callback, future)
    result = await future
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
