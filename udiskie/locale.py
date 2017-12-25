"""
I18n utilities.
"""

from gettext import translation


_t = translation('udiskie', localedir=None, languages=None, fallback=True)


def _(text, *args, **kwargs):
    """Translate and then and format the text with ``str.format``."""
    msg = _t.gettext(text)
    if args or kwargs:
        return msg.format(*args, **kwargs)
    else:
        return msg
