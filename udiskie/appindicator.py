"""
Status icon using AppIndicator3.
"""

from gi.repository import Gtk
from gi.repository import AppIndicator3

from .async_ import Future


class AppIndicatorIcon:

    """
    Show status icon using AppIndicator as backend. Replaces
    `udiskie.tray.StatusIcon` on ubuntu/unity.
    """

    def __init__(self, menumaker, _icons):
        self._maker = menumaker
        self._menu = Gtk.Menu()
        self._indicator = AppIndicator3.Indicator.new(
            'udiskie',
            _icons.get_icon_name('media'),
            AppIndicator3.IndicatorCategory.HARDWARE)
        self._indicator.set_status(AppIndicator3.IndicatorStatus.PASSIVE)
        self._indicator.set_menu(self._menu)
        # Get notified before menu is shown, see:
        # https://bugs.launchpad.net/screenlets/+bug/522152/comments/15
        dbusmenuserver = self._indicator.get_property('dbus-menu-server')
        self._dbusmenuitem = dbusmenuserver.get_property('root-node')
        self._conn = self._dbusmenuitem.connect('about-to-show', self._on_show)
        self.task = Future()
        menumaker._quit_action = self.destroy
        # Populate menu initially, so libdbusmenu does not ignore the
        # 'about-to-show':
        self._maker(self._menu)

    def destroy(self):
        self.show(False)
        self._dbusmenuitem.disconnect(self._conn)
        self.task.set_result(True)

    @property
    def visible(self):
        status = self._indicator.get_status()
        return status == AppIndicator3.IndicatorStatus.ACTIVE

    def show(self, show=True):
        if show == self.visible:
            return
        status = (AppIndicator3.IndicatorStatus.ACTIVE if show else
                  AppIndicator3.IndicatorStatus.PASSIVE)
        self._indicator.set_status(status)

    def _on_show(self, menu):
        # clear menu:
        for item in self._menu.get_children():
            self._menu.remove(item)
        # repopulate:
        self._maker(self._menu)
        self._menu.show_all()
