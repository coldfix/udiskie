"""
I18n utilities.
"""

import gettext


__all__ = ['_']


class Translator:

    """
    Simple translation and message formatting utility.
    """

    @classmethod
    def create(cls, domain, localedir=None, languages=None):
        """
        Create a new translator for the given domain.

        Arguments are as in ``gettext.translation``.
        """
        t = gettext.translation(domain, localedir, languages, fallback=True)
        g = t.gettext
        return cls(g)

    def __init__(self, gettext):
        """Initialize a translator with the given gettext function."""
        self._gettext = gettext

    def __call__(self, text, *args, **kwargs):
        """Translate and then and format the text with ``str.format``."""
        msg = self._gettext(text)
        if args or kwargs:
            return msg.format(*args, **kwargs)
        else:
            return msg


_ = Translator.create('udiskie')
