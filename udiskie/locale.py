"""
Internationalization utilities.
"""

def _(msg, *args, **kwargs):
    """
    Format the string with ``str.format``.

    Future versions of this function may translate the message to language
    defined in the current locale.
    """
    return msg.format(*args, **kwargs)
