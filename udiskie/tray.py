"""
Tray icon for udiskie.
"""
import gtk


def setdefault(self, other):
    """Merge two dictionaries like .update() but don't overwrite values."""
    for k,v in other.items():
        self.setdefault(k, v)


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
        mounter = Mounter(prompt=password, udisks=udisks)

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
        'lock': mounter.lock_device,
        'eject': mounter.eject_device,
        'detach': mounter.detach_device,
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

    # create menu items for these actions
    menu = gtk.Menu()
    for device in udisks.get_all_handleable():
        submenu = gtk.Menu()

        # primary operation:
        display = device.device_file
        if device.is_filesystem:
            if device.is_mounted:
                action = 'unmount'
                display = device.mount_paths[0]
            else:
                action = 'mount'
        elif device.is_crypto:
            if device.is_unlocked:
                action = 'lock'
            else:
                action = 'unlock'
        submenu.append(item(
            action, 
            feed=[display],
            bind=[device]))

        # additional operations
        if actions['eject'] and device.is_ejectable:
            submenu.append(item(
                'eject',
                feed=[device.drive.device_file],
                bind=[device.drive]))

        if actions['detach'] and device.is_detachable:
            submenu.append(item(
                'detach',
                feed=[device.drive.device_file],
                bind=[device.drive]))

        # append the submenu
        menu.append(create_menuitem(
            display,
            icons[action],
            onclick=submenu))

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

