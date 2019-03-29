"""
Tray icon for udiskie.
"""

from gi.repository import Gio
from gi.repository import Gtk

from .async_ import run_bg, Future
from .common import setdefault, DaemonBase
from .locale import _
from .mount import Action, prune_empty_node
from .prompt import Dialog


__all__ = ['UdiskieMenu', 'TrayIcon']


class MenuFolder:

    def __init__(self, label, items):
        self.label = label
        self.items = items

    def __bool__(self):
        return bool(self.items)

    __nonzero__ = __bool__


class MenuSection(MenuFolder):
    pass


class SubMenu(MenuFolder):
    pass


class Icons:

    """Encapsulates the responsibility to load icons."""

    _icon_names = {
        'media': [
            'drive-removable-media-usb-pendrive',
            'drive-removable-media-usb',
            'drive-removable-media',
            'media-optical',
            'media-flash',
        ],
        'browse': ['document-open', 'folder-open'],
        'terminal': ['terminal', 'utilities-terminal'],
        'mount': ['udiskie-mount'],
        'unmount': ['udiskie-unmount'],
        'unlock': ['udiskie-unlock'],
        'lock': ['udiskie-lock'],
        'eject': ['udiskie-eject', 'media-eject'],
        'detach': ['udiskie-detach'],
        'quit': ['application-exit'],
        'forget_password': ['edit-delete'],
        'delete': ['udiskie-eject'],
        'losetup': ['udiskie-mount'],
    }

    def __init__(self, icon_names={}):
        """Merge ``icon_names`` into default icon names."""
        _icon_names = icon_names.copy()
        setdefault(_icon_names, self.__class__._icon_names)
        self._icon_names = _icon_names
        for k, v in _icon_names.items():
            if isinstance(v, str):
                self._icon_names[k] = [v]

    def get_icon_name(self, icon_id: str) -> str:
        """Lookup the system icon name from udisie-internal id."""
        icon_theme = Gtk.IconTheme.get_default()
        for name in self._icon_names[icon_id]:
            if icon_theme.has_icon(name):
                return name
        return 'not-available'

    def get_icon(self, icon_id: str, size: "Gtk.IconSize") -> "Gtk.Image":
        """Load Gtk.Image from udiskie-internal id."""
        return Gtk.Image.new_from_gicon(self.get_gicon(icon_id), size)

    def get_gicon(self, icon_id: str) -> "Gio.Icon":
        """Lookup Gio.Icon from udiskie-internal id."""
        return Gio.ThemedIcon.new_from_names(self._icon_names[icon_id])


class UdiskieMenu:

    """
    Builder for udiskie menus.

    Objects of this class generate action menus when being called.
    """

    def __init__(self, daemon, icons, actions, flat=True,
                 quickmenu_actions=None):
        """
        Initialize a new menu maker.

        :param object mounter: mount operation provider
        :param Icons icons: icon provider
        :param DeviceActions actions: device actions discovery
        :returns: a new menu maker
        :rtype: cls

        Required keys for the ``_labels``, ``_menu_icons`` and
        ``actions`` dictionaries are:

            - browse    Open mount location
            - terminal  Open mount location in terminal
            - mount     Mount a device
            - unmount   Unmount a device
            - unlock    Unlock a LUKS device
            - lock      Lock a LUKS device
            - eject     Eject a drive
            - detach    Detach (power down) a drive
            - quit      Exit the application

        NOTE: If using a main loop other than ``Gtk.main`` the 'quit' action
        must be customized.
        """
        self._icons = icons
        self._daemon = daemon
        self._mounter = daemon.mounter
        self._actions = actions
        self._quit_action = daemon.mainloop.quit
        self.flat = flat
        # actions shown in the quick-menu ("flat", left-click):
        self._quickmenu_actions = quickmenu_actions or [
            'mount',
            'browse',
            'terminal',
            'unlock',
            'detach',
            'delete',
            # suppressed:
            # 'unmount',
            # 'lock',
            # 'eject',
            # 'forget_password',
        ]

    def __call__(self, menu, extended=True):
        """Populate the Gtk.Menu with udiskie mount operations."""
        # create actions items
        flat = self.flat and not extended
        self._create_menu_items(menu, self._prepare_menu(self.detect(), flat))
        if extended:
            self._insert_options(menu)
        return menu

    def _insert_options(self, menu):
        """Add configuration options to menu."""
        menu.append(Gtk.SeparatorMenuItem())
        menu.append(self._menuitem(
            _('Mount disc image'),
            self._icons.get_icon('losetup', Gtk.IconSize.MENU),
            run_bg(lambda _: self._losetup())
        ))
        menu.append(Gtk.SeparatorMenuItem())
        menu.append(self._menuitem(
            _("Enable automounting"),
            icon=None,
            onclick=lambda _: self._daemon.automounter.toggle_on(),
            checked=self._daemon.automounter.is_on(),
        ))
        menu.append(self._menuitem(
            _("Enable notifications"),
            icon=None,
            onclick=lambda _: self._daemon.notify.toggle(),
            checked=self._daemon.notify.active,
        ))
        # append menu item for closing the application
        if self._quit_action:
            menu.append(Gtk.SeparatorMenuItem())
            menu.append(self._menuitem(
                _('Quit'),
                self._icons.get_icon('quit', Gtk.IconSize.MENU),
                lambda _: self._quit_action()
            ))

    async def _losetup(self):
        gtk_dialog = Gtk.FileChooserDialog(
            _('Open disc image'), None,
            Gtk.FileChooserAction.OPEN,
            (_('Open'), Gtk.ResponseType.OK,
             _('Cancel'), Gtk.ResponseType.CANCEL))
        with Dialog(gtk_dialog) as dialog:
            response = await dialog
            if response == Gtk.ResponseType.OK:
                await self._mounter.losetup(dialog.window.get_filename())

    def detect(self):
        """Detect all currently known devices. Returns the root device."""
        root = self._actions.detect()
        prune_empty_node(root, set())
        return root

    def _create_menu(self, items):
        """
        Create a menu from the given node.

        :param list items: list of menu items
        :returns: a new Gtk.Menu object holding all items of the node
        """
        menu = Gtk.Menu()
        self._create_menu_items(menu, items)
        return menu

    def _create_menu_items(self, menu, items):
        def make_action_callback(node):
            return run_bg(lambda _: node.action())
        for node in items:
            if isinstance(node, Action):
                menu.append(self._menuitem(
                    node.label,
                    self._icons.get_icon(node.method, Gtk.IconSize.MENU),
                    make_action_callback(node)))
            elif isinstance(node, SubMenu):
                menu.append(self._menuitem(
                    node.label,
                    icon=None,
                    onclick=self._create_menu(node.items)))
            elif isinstance(node, MenuSection):
                self._create_menu_section(menu, node)
            else:
                raise ValueError(_("Invalid node!"))
        if len(menu) == 0:
            mi = self._menuitem(_("No external devices"), None, None)
            mi.set_sensitive(False)
            menu.append(mi)

    def _create_menu_section(self, menu, section):
        if len(menu) > 0:
            menu.append(Gtk.SeparatorMenuItem())
        if section.label:
            mi = self._menuitem(section.label, None, None)
            mi.set_sensitive(False)
            menu.append(mi)
        self._create_menu_items(menu, section.items)

    def _menuitem(self, label, icon, onclick, checked=None):
        """
        Create a generic menu item.

        :param str label: text
        :param Gtk.Image icon: icon (may be ``None``)
        :param onclick: onclick handler, either a callable or Gtk.Menu
        :returns: the menu item object
        :rtype: Gtk.MenuItem
        """
        if checked is not None:
            item = Gtk.CheckMenuItem()
            item.set_active(checked)
        elif icon is None:
            item = Gtk.MenuItem()
        else:
            item = Gtk.ImageMenuItem()
            item.set_image(icon)
            # I don't really care for the "show icons only for nouns, not
            # for verbs" policy:
            item.set_always_show_image(True)
        if label is not None:
            item.set_label(label)
        if isinstance(onclick, Gtk.Menu):
            item.set_submenu(onclick)
        elif onclick is not None:
            item.connect('activate', onclick)
        return item

    def _prepare_menu(self, node, flat=None):
        """
        Prepare the menu hierarchy from the given device tree.

        :param Device node: root node of device hierarchy
        :returns: menu hierarchy as list
        """
        if flat is None:
            flat = self.flat
        ItemGroup = MenuSection if flat else SubMenu
        return [
            ItemGroup(branch.label, self._collapse_device(branch, flat))
            for branch in node.branches
            if branch.methods or branch.branches
        ]

    def _collapse_device(self, node, flat):
        """Collapse device hierarchy into a flat folder."""
        items = [item
                 for branch in node.branches
                 for item in self._collapse_device(branch, flat)
                 if item]
        show_all = not flat or self._quickmenu_actions == 'all'
        methods = node.methods if show_all else [
            method
            for method in node.methods
            if method.method in self._quickmenu_actions
        ]
        if flat:
            items.extend(methods)
        else:
            items.append(MenuSection(None, methods))
        return items


class TrayIcon:

    """Default TrayIcon class."""

    def __init__(self, menumaker, icons, statusicon=None):
        """
        Create an object managing a tray icon.

        The actual Gtk.StatusIcon is only created as soon as you call show()
        for the first time. The reason to delay its creation is that the GTK
        icon will be initially visible, which results in a perceptable
        flickering.

        :param UdiskieMenu menumaker: menu factory
        :param Gtk.StatusIcon statusicon: status icon
        """
        self._icons = icons
        self._icon = statusicon
        self._menu = menumaker
        self._conn_left = None
        self._conn_right = None
        self.task = Future()
        menumaker._quit_action = self.destroy

    def destroy(self):
        self.show(False)
        self.task.set_result(True)

    def _create_statusicon(self):
        """Return a new Gtk.StatusIcon."""
        statusicon = Gtk.StatusIcon()
        statusicon.set_from_gicon(self._icons.get_gicon('media'))
        statusicon.set_tooltip_text(_("udiskie"))
        return statusicon

    @property
    def visible(self):
        """Return visibility state of icon."""
        return bool(self._conn_left)

    def show(self, show=True):
        """Show or hide the tray icon."""
        if show and not self.visible:
            self._show()
        if not show and self.visible:
            self._hide()

    def _show(self):
        """Show the tray icon."""
        if not self._icon:
            self._icon = self._create_statusicon()
        widget = self._icon
        widget.set_visible(True)
        self._conn_left = widget.connect("activate", self._activate)
        self._conn_right = widget.connect("popup-menu", self._popup_menu)

    def _hide(self):
        """Hide the tray icon."""
        self._icon.set_visible(False)
        self._icon.disconnect(self._conn_left)
        self._icon.disconnect(self._conn_right)
        self._conn_left = None
        self._conn_right = None

    def create_context_menu(self, extended):
        """Create the context menu."""
        menu = Gtk.Menu()
        self._menu(menu, extended)
        return menu

    def _activate(self, icon):
        """Handle a left click event (show the menu)."""
        self._popup_menu(icon, button=0, time=Gtk.get_current_event_time(),
                         extended=False)

    def _popup_menu(self, icon, button, time, extended=True):
        """Handle a right click event (show the menu)."""
        m = self.create_context_menu(extended)
        m.show_all()
        m.popup(parent_menu_shell=None,
                parent_menu_item=None,
                func=icon.position_menu,
                data=icon,
                button=button,
                activate_time=time)
        # need to store reference or menu will be destroyed before showing:
        self._m = m


class UdiskieStatusIcon(DaemonBase):

    """
    Manage a status icon.

    When `smart` is on, the icon will automatically hide if there is no action
    available and the menu will have no 'Quit' item.
    """

    def __init__(self, icon, menumaker, smart=False):
        self._icon = icon
        self._menumaker = menumaker
        self._mounter = menumaker._mounter
        self._quit_action = menumaker._quit_action
        self.smart = smart
        self.active = False
        self.events = {
            'device_changed': self.update,
            'device_added': self.update,
            'device_removed': self.update,
        }

    def activate(self):
        super().activate()
        self.update()

    def deactivate(self):
        super().deactivate()
        self._icon.show(False)

    @property
    def smart(self):
        return getattr(self, '_smart', None)

    @smart.setter
    def smart(self, smart):
        if smart == self.smart:
            return
        if smart:
            self._menumaker._quit_action = None
        else:
            self._menumaker._quit_action = self._quit_action
        self._smart = smart
        self.update()

    def has_menu(self):
        """Check if a menu action is available."""
        return any(self._menumaker._prepare_menu(self._menumaker.detect()))

    def update(self, *args):
        """Show/hide icon depending on whether there are devices."""
        if self.smart:
            self._icon.show(self.has_menu())
        else:
            self._icon.show(True)
