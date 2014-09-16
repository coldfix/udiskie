"""
Common DBus utilities.
"""

import os.path


__all__ = [
    'wraps',
    'Emitter',
    'samefile',
    'setdefault',
    'extend',
]


try:
    from black_magic.decorator import wraps
except ImportError:
    from functools import wraps


class Emitter(object):

    """
    Event emitter class.

    Provides a simple event engine featuring a known finite set of events.
    """

    def __init__(self, event_names=(), *args, **kwargs):
        """
        Initialize with empty lists of event handlers.

        :param iterable event_names: names of known events.
        """
        super(Emitter, self).__init__(*args, **kwargs)
        self._event_handlers = {}
        for evt in event_names:
            self._event_handlers[evt] = []

    def trigger(self, event, *args):
        """
        Trigger event handlers.

        :param str event: event name
        :param *args: event parameters
        """
        for handler in self._event_handlers[event]:
            handler(*args)

    def connect_all(self, obj):
        """
        Connect all handlers of a multi-slot object.

        :param obj: multi-slot
        """
        for event in self._event_handlers:
            if hasattr(obj, event):
                self.connect(event, getattr(obj, event))

    def disconnect_all(self, obj):
        """
        Disconnect all handlers of a multi-slot object.

        :param obj: multi-slot
        """
        for event in self._event_handlers:
            if hasattr(obj, event):
                self.disconnect(event, getattr(obj, event))

    def connect(self, event, handler):
        """
        Connect an event handler.

        :param str event: event name
        :param callable handler: event handler
        """
        self._event_handlers[event].append(handler)

    def disconnect(self, event, handler):
        """
        Disconnect an event handler.

        :param str event: event name
        :param callable handler: event handler
        """
        self._event_handlers[event].remove(handler)


def samefile(a, b):
    """Check if two pathes represent the same file."""
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.normpath(a) == os.path.normpath(b)


def setdefault(self, other):
    """
    Merge two dictionaries like .update() but don't overwrite values.

    :param dict self: updated dict
    :param dict other: default values to be inserted
    """
    for k, v in other.items():
        self.setdefault(k, v)


def extend(a, b):
    """Merge two dicts and return a new dict. Much like subclassing works."""
    res = a.copy()
    res.update(b)
    return res
