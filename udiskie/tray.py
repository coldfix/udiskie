"""
Tray icon for udiskie.
"""
__all__ = ['create_menu',
           'create_statusicon',
           'connect_statusicon',
           'main']

import gtk
from functools import partial
from collections import namedtuple


def setdefault(self, other):
    """Merge two dictionaries like .update() but don't overwrite values."""
    for k,v in other.items():
        self.setdefault(k, v)


TreeNode = namedtuple('TreeNode',
                      ['root', 'branches',
                       'device', 'label', 'methods'])


def device_tree(udisks):
    """
    Return the device hierarchy as list of TreeNodes
    """
    devices = {}

    def find_node(object_path):
        if object_path in devices:
            return devices[object_path]
        else:
            return mknode(udisks.create_device(object_path))

    def mknode(device):
        # methods
        methods = []
        label = device.device_file
        if device.is_filesystem:
            if device.is_mounted:
                methods.append('unmount')
                label = device.mount_paths[0]
            else:
                methods.append('mount')
        elif device.is_crypto:
            if device.is_unlocked:
                methods.append('lock')
            else:
                methods.append('unlock')
        if device.is_ejectable:
            methods.append('eject')
        if device.is_detachable:
            methods.append('detach')

        # root
        if device.is_partition:
            root = find_node(device.partition_slave)
        elif device.is_luks_cleartext:
            root = find_node(device.luks_cleartext_slave)
        else:
            root = None

        node = TreeNode(root, [], device, label, methods)
        devices[device.object_path] = node
        if root:
            root.branches.append(node)
        return node

    for device in udisks.get_all_handleable():
        if device.object_path not in devices:
            mknode(device)

    return list(dev for _,dev in devices.items() if dev.root is None)


def create_menu(udisks=None,
                mounter=None,
                labels={},
                icons={},
                actions={}):
    """
    Create menu for udiskie mount operations.

    :param object udisks: Interface to udisks used to iterate external devices
    :param object mounter: Mount operation provider
    :param dict labels: Labels for menu items
    :param dict icons: Icons for menu items
    :param dict actions: Actions for menu items

    If either ``udisks`` and or ``mounter`` is ``None`` default versions
    will be imported from the udiskie package.

    Valid keys for the ``labels``, ``icons`` and ``actions`` dictionaries are:

        - mount     Mount a device
        - unmount   Unmount a device
        - unlock    Unlock a LUKS device
        - lock      Lock a LUKS device
        - eject     Eject a drive
        - detach    Detach (power down) a drive
        - quit      Exit the application

    NOTE: If using a main loop other than ``gtk.main`` the 'quit' action
    must be customized.

    To prevent a certain action from being displayed its ``action`` must be
    set to ``None``.

    """
    if udisks is None:
        from dbus import SystemBus
        from udiskie.udisks import Udisks
        udisks = Udisks.create(SystemBus())
    if mounter is None:
        from udiskie.mount import Mounter
        from udiskie.prompt import password
        mounter = Mounter(prompt=password(), udisks=udisks)

    setdefault(icons, {
        'mount': gtk.STOCK_APPLY,
        'unmount': gtk.STOCK_CANCEL,
        'unlock': gtk.STOCK_APPLY,
        'lock': gtk.STOCK_CANCEL,
        'eject': gtk.STOCK_CANCEL,
        'detach': gtk.STOCK_CANCEL,
        'quit': gtk.STOCK_QUIT, })

    setdefault(labels, {
        'mount': 'Mount %s',
        'unmount': 'Unmount %s',
        'unlock': 'Unlock %s',
        'lock': 'Lock %s',
        'eject': 'Eject %s',
        'detach': 'Detach %s',
        'quit': 'Quit', })

    setdefault(actions, {
        'mount': mounter.mount_device,
        'unmount': mounter.unmount_device,
        'unlock': mounter.unlock_device,
        'lock': partial(mounter.remove_device, force=True),
        'eject': partial(mounter.eject_device, force=True),
        'detach': partial(mounter.detach_device, force=True),
        'quit': gtk.main_quit, })

    def create_menuitem(label, icon, onclick):
        if icon is None:
            item = gtk.MenuItem()
        else:
            try:
                item = gtk.ImageMenuItem(stock_id=icon)
            except TypeError:
                item = gtk.ImageMenuItem()
                item.set_icon(icon)
        if label is not None:
            item.set_label(label)
        if isinstance(onclick, gtk.Menu):
            item.set_submenu(onclick)
        else:
            item.connect('activate', onclick)
        return item

    def item(action, feed=(), bind=()):
        return create_menuitem(
            labels[action] % tuple(feed),
            icons[action],
            lambda _: actions[action](*bind))

    def insert_submenu(menu, node):
        if len(node.branches) + len(node.methods) > 1:
            submenu = gtk.Menu()
        else:
            submenu = menu
        for branch in node.branches:
            insert_submenu(submenu, branch)
        if len(node.branches) > 0 and len(node.methods) > 0:
            submenu.append(gtk.SeparatorMenuItem())
        for method in node.methods:
            submenu.append(item(
                method,
                feed=[node.label],
                bind=[node.device]))
        if submenu is not menu:
            menu.append(create_menuitem(
                node.label,
                icon=None,
                onclick=submenu))

    # create menu items for these actions
    menu = gtk.Menu()
    for root in device_tree(udisks):
        insert_submenu(menu, root)

    # append menu item for closing the application
    if actions['quit']:
        if len(menu) > 0:
            menu.append(gtk.SeparatorMenuItem())
        menu.append(item('quit'))

    return menu


def create_statusicon():
    """Create a simple gtk.StatusIcon"""
    statusicon = gtk.StatusIcon()
    statusicon.set_from_stock(gtk.STOCK_CDROM)
    statusicon.set_tooltip("udiskie")
    return statusicon


def connect_statusicon(statusicon, menu=create_menu):
    """Connect a popup menu event handler, return the connection identifier."""
    def right_click_event(icon, button, time):
        m = menu()
        m.show_all()
        m.popup(parent_menu_shell=None,
                parent_menu_item=None,
                func=gtk.status_icon_position_menu,
                button=button,
                activate_time=time,
                data=icon)
    return statusicon.connect("popup-menu", right_click_event)


def main():
    """Run udiskie tray icon in a main loop."""
    statusicon = create_statusicon()
    connection = connect_statusicon(statusicon)
    gtk.main()
    statusicon.disconnect(connection)
    statusicon.set_visible(False)


if __name__ == '__main__':
    main()

