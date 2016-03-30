"""
Tray icon for udiskie.
"""

from __future__ import absolute_import
from __future__ import unicode_literals

from gi.repository import Gio
from gi.repository import Gtk

from .async_ import Async
from .common import setdefault
from .compat import basestring
from .locale import _
from .mount import Action, Branch, prune_empty_node


__all__ = ['UdiskieMenu', 'SmartUdiskieMenu', 'TrayIcon']


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
        'forget_password': ['edit-delete'],
    }

    def __init__(self, icon_names={}):
        """Merge ``icon_names`` into default icon names."""
        _icon_names = icon_names.copy()
        setdefault(_icon_names, self.__class__._icon_names)
        self._icon_names = _icon_names
        for k, v in _icon_names.items():
            if isinstance(v, basestring):
                self._icon_names[k] = [v]

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

    _quit_label = _('Quit')

    def __init__(self, mounter, icons, actions, quit_action=None):
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
        self._actions = actions
        self._quit_action = quit_action

    def __call__(self):
        """
        Create menu for udiskie mount operations.

        :returns: a new menu
        :rtype: Gtk.Menu
        """
        # create actions items
        menu = self._branchmenu(self._prepare_menu(self.detect()).groups)
        # append menu item for closing the application
        if self._quit_action:
            if len(menu) > 0:
                menu.append(Gtk.SeparatorMenuItem())
            menu.append(self._menuitem(
                self._quit_label,
                self._icons.get_icon('quit', Gtk.IconSize.MENU),
                lambda _: self._quit_action()
            ))
        return menu

    def detect(self):
        """
        Detect all currently known devices.

        :returns: root of device hierarchy
        :rtype: Device
        """
        root = self._actions.detect()
        prune_empty_node(root, set())
        return root

    def _branchmenu(self, groups):
        """
        Create a menu from the given node.

        :param Branch groups: contains information about the menu
        :returns: a new menu object holding all groups of the node
        :rtype: Gtk.Menu
        """
        def make_action_callback(node):
            return lambda _: node.action()
        menu = Gtk.Menu()
        separate = False
        for group in groups:
            if len(group) > 0:
                if separate:
                    menu.append(Gtk.SeparatorMenuItem())
                separate = True
            for node in group:
                if isinstance(node, Action):
                    menu.append(self._menuitem(
                        node.label,
                        self._icons.get_icon(node.method, Gtk.IconSize.MENU),
                        make_action_callback(node)))
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

    def _prepare_menu(self, node):
        """
        Prepare the menu hierarchy from the given device tree.

        :param Device node: root node of device hierarchy
        :returns: menu hierarchy
        :rtype: Branch
        """
        return Branch(
            label=node.label,
            groups=[
                [self._prepare_menu(branch)
                 for branch in node.branches
                 if branch.methods or branch.branches],
                node.methods,
            ])


class SmartUdiskieMenu(UdiskieMenu):

    def _actions_group(self, node, presentation):
        """
        Create the actions group for the specified device node.

        :param Device node: device
        :param str presentation: node label
        """
        labels = self._actions._labels
        return [Action(action.method,
                       action.device,
                       labels[action.method].format(presentation),
                       action.action)
                for action in node.methods]

    def _collapse_device(self, node, presentation=""):
        """Collapse device hierarchy into a flat folder."""
        if (not presentation
                or node.device.is_mounted
                or not node.device.is_luks_cleartext):
            presentation = node.label
        groups = [group
                  for branch in node.branches
                  for group in self._collapse_device(branch, presentation)
                  if group]
        groups.append(self._actions_group(node, presentation))
        return groups

    def _prepare_menu(self, node):
        """Overrides UdiskieMenu._prepare_menu."""
        return Branch(
            label=node.label,
            groups=[
                [Branch(branch.label, self._collapse_device(branch))
                 for branch in node.branches
                 if branch.methods or branch.branches],
            ])


class TrayIcon(object):

    """Default TrayIcon class."""

    def __init__(self, menumaker, icons, statusicon=None, show=True):
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
        self.task = Async()
        menumaker._quit_action = self.destroy
        if show:
            self.show()

    def destroy(self):
        self.show(False)
        self.task.callback()

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

    def create_context_menu(self):
        """Create the context menu."""
        return self._menu()

    def _activate(self, icon):
        """Handle a left click event (show the menu)."""
        self._popup_menu(icon, button=0, time=Gtk.get_current_event_time())

    def _popup_menu(self, icon, button, time):
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
        super(AutoTray, self).__init__(menumaker, icons, show=False)
        # Okay, the following is BAD:
        menumaker._quit_action = None
        udisks = menumaker._mounter.udisks
        udisks.connect('device_changed', self.update)
        udisks.connect('device_added', self.update)
        udisks.connect('device_removed', self.update)
        self.update()

    def has_menu(self):
        """Check if a menu action is available."""
        return any(self._menu._prepare_menu(self._menu.detect()).groups)

    def update(self, *args):
        """Show/hide icon depending on whether there are devices."""
        self.show(self.has_menu())
