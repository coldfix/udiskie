"""
Make sure that the correct versions of gobject introspection dependencies
are installed.
"""

from __future__ import absolute_import
from __future__ import unicode_literals

import os
import logging

from gi import require_version

from .common import check_call
from .locale import _

require_version('Gio', '2.0')
require_version('GLib', '2.0')


def check_version(package, version):
    return check_call(ValueError, require_version, package, version)


_in_X = bool(os.environ.get('DISPLAY'))

_has_Gtk = (3 if check_version('Gtk', '3.0') else
            2 if check_version('Gtk', '2.0') else
            0)

_has_Notify = check_version('Notify', '0.7')


def require_Gtk(min_version=2):
    """
    Make sure Gtk is properly initialized.

    :raises RuntimeError: if Gtk can not be properly initialized
    """
    if not _in_X:
        raise RuntimeError('Not in X session.')
    if _has_Gtk < min_version:
        raise RuntimeError('Module gi.repository.Gtk not available!')
    if _has_Gtk == 2:
        logging.getLogger(__name__).warn(
            _("Missing runtime dependency GTK 3. Falling back to GTK 2 "
              "for password prompt"))
    from gi.repository import Gtk
    # if we attempt to create any GUI elements with no X server running the
    # program will just crash, so let's make a way to catch this case:
    if not Gtk.init_check(None)[0]:
        raise RuntimeError(_("X server not connected!"))
    return Gtk


def require_Notify():
    if not _has_Notify:
        raise RuntimeError('Module gi.repository.Notify not available!')
    from gi.repository import Notify
    return Notify


def has_Notify():
    return check_call((RuntimeError, ImportError), require_Notify)


def has_Gtk(min_version=2):
    return check_call((RuntimeError, ImportError), require_Gtk, min_version)
