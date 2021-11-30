"""
I18n utilities.
"""

import os
import sys
from gettext import translation


testdirs = [
    # manual override:
    os.environ.get('TEXTDOMAINDIR'),
    # editable installation:
    os.path.join(os.path.dirname(__file__), '../build/locale'),
    # user or virtualenv installation:
    os.path.join(sys.prefix, 'share/locale'),
]
testfile = 'en_US/LC_MESSAGES/udiskie.mo'
localedir = next(
    (d for d in testdirs if d and os.path.exists(os.path.join(d, testfile))),
    None)

_t = translation('udiskie', localedir, languages=None, fallback=True)


def _(text, *args, **kwargs):
    """Translate and then and format the text with ``str.format``."""
    msg = _t.gettext(text)
    if args or kwargs:
        return msg.format(*args, **kwargs)
    else:
        return msg
