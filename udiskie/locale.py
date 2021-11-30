"""
I18n utilities.
"""

import os
from gettext import translation


localedir = os.environ.get('TEXTDOMAINDIR')
_t = translation('udiskie', localedir, languages=None, fallback=True)


def _(text, *args, **kwargs):
    """Translate and then and format the text with ``str.format``."""
    msg = _t.gettext(text)
    if args or kwargs:
        return msg.format(*args, **kwargs)
    else:
        return msg
