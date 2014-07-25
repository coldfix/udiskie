"""
Tray icon for udiskie.
"""

from collections import namedtuple
from functools import partial
from itertools import chain

from gi.repository import Gtk
from gi.repository import Gio

from udiskie.common import setdefault
from udiskie.locale import _


__all__ = ['UdiskieMenu', 'SmartUdiskieMenu', 'TrayIcon']


# data structs containing the menu hierarchy:
Node = namedtuple('Node', ['root', 'branches', 'device', 'label', 'methods'])
Action = namedtuple('Action', ['label', 'device', 'method'])
Branch = namedtuple('Branch', ['label', 'groups'])


class Icons(object):

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
        'mount': ['udiskie-mount'],
        'unmount': ['udiskie-unmount'],
        'unlock': ['udiskie-unlock'],
        'lock': ['udiskie-lock'],
        'eject': ['udiskie-eject', 'media-eject'],
        'detach': ['udiskie-detach'],
        'quit': ['application-exit'],
    }

    def get_icon(self, icon_id, size):
        """
        Load icon dynamically.

        :param str icon_id: udiskie internal icon id
        :param GtkIconSize size: requested size
        :returns: the loaded icon
        :rtype: Gtk.Image
        """
        return Gtk.Image.new_from_gicon(self.get_gicon(icon_id), size)

    def get_gicon(self, icon_id):
        """
        Lookup the GTK icon name corresponding to the specified internal id.

        :param str icon_id: udiskie internal icon id
        :param GtkIconSize size: requested size
        :returns: the loaded icon
        :rtype: Gio.Icon
        """
        return Gio.ThemedIcon.new_from_names(self._icon_names[icon_id])


class UdiskieMenu(object):

    """
    Builder for udiskie menus.

    Objects of this class generate action menus when being called.
    """

    _menu_labels = {
        'browse': _('Browse {0}'),
        'mount': _('Mount {0}'),
        'unmount': _('Unmount {0}'),
        'unlock': _('Unlock {0}'),
        'lock': _('Lock {0}'),
        'eject': _('Eject {0}'),
        'detach': _('Unpower {0}'),
        'quit': _('Quit'), }

    def __init__(self, mounter, icons, actions={}):
        """
        Initialize a new menu maker.

        :param object mounter: mount operation provider
        :param Icons icons: icon provider
        :param dict actions: actions for menu items
        :returns: a new menu maker
        :rtype: cls

        Required keys for the ``_menu_labels``, ``_menu_icons`` and
        ``actions`` dictionaries are:

            - browse    Open mount location
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
        self._mounter = mounter
        setdefault(actions, {
            'browse': mounter.browse,
            'mount': mounter.mount,
            'unmount': mounter.unmount,
            'unlock': mounter.unlock,
            'lock': partial(mounter.remove, force=True),
            'eject': partial(mounter.eject, force=True),
            'detach': partial(mounter.detach, force=True),
            'quit': Gtk.main_quit, })
        self._actions = actions

    def __call__(self):
        """
        Create menu for udiskie mount operations.

        :returns: a new menu
        :rtype: Gtk.Menu
        """
        # create actions items
        menu = self._branchmenu(self._prepare_menu(self.detect()).groups)
        # append menu item for closing the application
        if self._actions.get('quit'):
            if len(menu) > 0:
                menu.append(Gtk.SeparatorMenuItem())
            menu.append(self._actionitem('quit'))
        return menu

    def detect(self):
        """
        Detect all currently known devices.

        :returns: root of device hierarchy
        :rtype: Node
        """
        root = Node(None, [], None, "", [])
        device_nodes = dict(map(self._device_node,
                                self._mounter.get_all_handleable()))
        # insert child devices as branches into their roots:
        for object_path, node in device_nodes.items():
            device_nodes.get(node.root, root).branches.append(node)
        return root

    def _branchmenu(self, groups):
        """
        Create a menu from the given node.

        :param Branch groups: contains information about the menu
        :returns: a new menu object holding all groups of the node
        :rtype: Gtk.Menu
        """
        menu = Gtk.Menu()
        separate = False
        for group in groups:
            if len(group) > 0:
                if separate:
                    menu.append(Gtk.SeparatorMenuItem())
                separate = True
            for node in group:
                if isinstance(node, Action):
                    menu.append(self._actionitem(
                        node.method,
                        feed=[node.label],
                        bind=[node.device]))
                elif isinstance(node, Branch):
                    menu.append(self._menuitem(
                        node.label,
                        icon=None,
                        onclick=self._branchmenu(node.groups)))
                else:
                    raise ValueError(_("Invalid node!"))
        return menu

    def _menuitem(self, label, icon, onclick):
        """
        Create a generic menu item.

        :param str label: text
        :param Gtk.Image icon: icon (may be ``None``)
        :param onclick: onclick handler, either a callable or Gtk.Menu
        :returns: the menu item object
        :rtype: Gtk.MenuItem
        """
        if icon is None:
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
        else:
            item.connect('activate', onclick)
        return item

    def _actionitem(self, action, feed=(), bind=()):
        """
        Create a menu item for the specified action.

        :param str action: name of the action
        :param tuple feed: parameters for the label text
        :param tuple bind: parameters for the onclick handler
        :returns: the menu item object
        :rtype: Gtk.MenuItem
        """
        return self._menuitem(
            self._menu_labels[action].format(*feed),
            self._icons.get_icon(action, Gtk.IconSize.MENU),
            lambda _: self._actions[action](*bind))

    def _device_node(self, device):
        """Create an empty menu node for the specified device."""
        label = device.id_label or device.device_presentation
        # determine available methods
        methods = []
        def append(method):
            if self._actions[method]:
                methods.append(method)
        if device.is_filesystem:
            if device.is_mounted:
                append('browse')
                append('unmount')
            else:
                append('mount')
        elif device.is_crypto:
            if device.is_unlocked:
                append('lock')
            else:
                append('unlock')
        if device.is_ejectable and device.has_media:
            append('eject')
        if device.is_detachable:
            append('detach')
        # find the root device:
        if device.is_partition:
            root = device.partition_slave.object_path
        elif device.is_luks_cleartext:
            root = device.luks_cleartext_slave.object_path
        else:
            root = None
        # in this first step leave branches empty
        return device.object_path, Node(root, [], device, label, methods)

    def _prepare_menu(self, node):
        """
        Prepare the menu hierarchy from the given device tree.

        :param Node node: root node of device hierarchy
        :returns: menu hierarchy
        :rtype: Branch
        """
        return Branch(
            label=node.label,
            groups=[
                [self._prepare_menu(branch)
                 for branch in node.branches],
                [Action(node.label, node.device, method)
                 for method in node.methods],
            ])


class SmartUdiskieMenu(UdiskieMenu):

    def _actions_group(self, node, presentation):
        """
        Create the actions group for the specified device node.

        :param Node node: device
        :param str presentation: node label
        """
        return [Action(presentation, node.device, method)
                for method in node.methods]

    def _leaves_group(self, node, outer_methods, presentation):
        """
        Create groups for the specified node.

        :param Node node: device
        :param list outer_methods: mix-in methods of root device
        :param str presentation: node label
        """
        if not presentation or (node.device.is_mounted or
                                not node.device.is_luks_cleartext):
            presentation = node.label
        if node.branches:
            return chain.from_iterable(
                self._leaves_group(
                    branch,
                    self._actions_group(node, presentation) + outer_methods,
                    presentation)
                for branch in node.branches)
        elif len(node.methods) + len(outer_methods) > 0:
            return Branch(
                label=presentation,
                groups=[list(chain(self._actions_group(node, presentation),
                                   outer_methods))]),
        else:
            return ()

    def _prepare_menu(self, node):
        """Overrides UdiskieMenu._prepare_menu."""
        return Branch(
            label=node.label,
            groups=[list(self._leaves_group(node, [], ""))])


class TrayIcon(object):

    """Default TrayIcon class."""

    def __init__(self, menumaker, icons, statusicon=None):
        """
        Create and show a simple Gtk.StatusIcon.

        :param UdiskieMenu menumaker: menu factory
        :param Gtk.StatusIcon statusicon: status icon
        """
        self._icons = icons
        self._icon = statusicon or self._create_statusicon()
        self._menu = menumaker
        self._conn_left = None
        self._conn_right = None
        self.show()

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
        if show:
            if not self.visible:
                self._show()
        else:
            self.hide()

    def hide(self):
        """Hide the tray icon."""
        if self.visible:
            self._hide()

    def _show(self):
        """Show the tray icon."""
        self._icon.set_visible(True)
        self._conn_left = self._icon.connect("activate", self._left_click_event)
        self._conn_right = self._icon.connect("popup-menu", self._right_click_event)

    def _hide(self):
        """Hide the tray icon."""
        self._icon.set_visible(False)
        self._icon.disconnect(self._conn_left)
        self._icon.disconnect(self._conn_right)
        self._conn_left = None
        self._conn_right = None

    def create_context_menu(self):
        """Create the context menu."""
        return self._menu()

    def _left_click_event(self, icon):
        """Handle a left click event (show the menu)."""
        m = self.create_context_menu()
        m.show_all()
        m.popup(parent_menu_shell=None,
                parent_menu_item=None,
                func=icon.position_menu,
                data=icon,
                button=0,
                activate_time=Gtk.get_current_event_time())
        # need to store reference or menu will be destroyed before showing:
        self._m = m

    def _right_click_event(self, icon, button, time):
        """Handle a right click event (show the menu)."""
        m = self.create_context_menu()
        m.show_all()
        m.popup(parent_menu_shell=None,
                parent_menu_item=None,
                func=icon.position_menu,
                data=icon,
                button=button,
                activate_time=time)
        # need to store reference or menu will be destroyed before showing:
        self._m = m


class AutoTray(TrayIcon):

    """
    TrayIcon that automatically hides.

    The menu has no 'Quit' item, and the tray icon will automatically hide
    if there is no action available.
    """

    def __init__(self, menumaker, icons):
        """
        Create and automatically set visibility of a new status icon.

        Overrides TrayIcon.__init__.
        """
        # The reason to overwrite TrayIcon.__init__ is that the AutoTray
        # icon may need to be hidden at initialization time. When creating a
        # Gtk.StatusIcon, it will initially be visible, creating a minor
        # nuisance.
        self._icons = icons
        self._icon = None
        self._menu = menumaker
        self._conn_left = None
        self._conn_right = None
        # Okay, the following is BAD:
        menumaker._actions['quit'] = None
        menumaker._mounter.udisks.connect_all(self)
        self.show(self.has_menu())

    def _show(self):
        """Extends TrayIcon._show: create a new status icon."""
        self._icon = self._create_statusicon()
        super(AutoTray, self)._show()

    def _hide(self):
        """Extends TrayIcon._hide: forget the status icon."""
        super(AutoTray, self)._hide()
        self._icon = None

    def has_menu(self):
        """Check if a menu action is available."""
        return any(self._menu._prepare_menu(self._menu.detect()).groups)

    def device_changed(self, old_state, new_state):
        """Update visibility."""
        self.show(self.has_menu())

    def device_added(self, device):
        """Update visibility."""
        self.show(self.has_menu())

    def device_removed(self, device):
        """Update visibility."""
        self.show(self.has_menu())
