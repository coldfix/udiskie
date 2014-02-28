=======
udiskie
=======

*udiskie* is a simple daemon that uses UDisks_ to automatically mount
removable storage devices. This daemon comes with optional mount
notifications and gtk tray icon. It also provides a user level CLI for
mount and unmount operations.

.. _UDisks: http://www.freedesktop.org/wiki/Software/udisks


Dependencies
------------

- UDisks_ required for all operation modes. UDisks2 support is experimental
  and has to be requested explicitly via command line parameter.
- dbus-python_ required for all operation modes
- PyGObject_ to run the automount/notification daemon (provides the main loop)
- notify-python_ or notify2_ for mount notifications
- Zenity_ to unlock LUKS devices
- PyGTK_ to show the system tray icon

.. _UDisks: http://www.freedesktop.org/wiki/Software/udisks
.. _dbus-python: http://dbus.freedesktop.org/doc/dbus-python/
.. _PyGObject: http://ftp.gnome.org/pub/gnome/sources/pygobject/
.. _notify-python: http://www.galago-project.org/files/releases/source/notify-python/
.. _notify2: https://pypi.python.org/pypi/notify2
.. _Zenity: http://freecode.com/projects/zenity
.. _PyGTK: http://www.pygtk.org


Permissions
-----------

*udiskie* requires permission for the following PolicyKit_ actions:

.. _PolicyKit: http://www.freedesktop.org/wiki/Software/PolicyKit

- ``org.freedesktop.udisks.filesystem-mount`` for mounting and unmounting
- ``org.freedesktop.udisks.luks-unlock`` to unlock LUKS devices
- ``org.freedesktop.udisks.drive-eject`` to eject drives
- ``org.freedesktop.udisks.drive-detach`` to detach drives

These are usually granted when using a desktop environment. If your login
session is not properly activated you may need to customize your PolicyKit
settings. Create the file
``/etc/polkit-1/localauthority/50-local.d/10-udiskie.pkla`` with the
following contents:

::

    [udiskie]
    Identity=unix-group:storage
    Action=org.freedesktop.udisks.filesystem-mount;org.freedesktop.udisks.luks-unlock;org.freedesktop.udisks.drive-eject;org.freedesktop.udisks.drive-detach
    ResultAny=yes

This configuration allows all members of the storage group to run udiskie.

Alternatively, change the setting for ``allow_inactive`` to *yes* in the
file ``/usr/share/polkit-1/actions/org.freedesktop.udisks.policy``:

.. code-block:: xml

    <action id="org.freedesktop.udisks.filesystem-mount">
        ...
        <allow_inactive>yes</allow_inactive>
        ...
    </action>

    ...

    <action id="org.freedesktop.udisks.luks-unlock">
        ...
        <allow_inactive>yes</allow_inactive>
        ...
    </action>

    ...

    <action id="org.freedesktop.udisks.drive-eject">
        ...
        <allow_inactive>yes</allow_inactive>
        ...
    </action>

    ...

    <action id="org.freedesktop.udisks.drive-detach">
        ...
        <allow_inactive>yes</allow_inactive>
        ...
    </action>

Note that UDisks2 uses another set of permissions, see ``/usr/share/polkit-1/actions/org.freedesktop.udisks2.policy``.


GTK icons
---------

*udiskie* comes with a set of themeable custom Tango-style GTK icons for its
tray icon menu. The installer tries to install the icons into GTK's default
hicolor theme. Typically this is located in ``/usr/share/icons/hicolor``. If
you have any problems with this or you need a custom path you can manually do
it like so:

.. code-block:: bash

    cp ./icons/scalable /usr/share/icons/hicolor -r
    gtk-update-icon-cache /usr/share/icons/hicolor

The icons roughly follow the `Tango style guidelines`_. Some icons incorporate
the CDROM icon of the base icon theme of the `Tango desktop project`_
(released into the public domain).

.. _`Tango style guidelines`: http://tango.freedesktop.org/Tango_Icon_Theme_Guidelines
.. _`Tango desktop project`: http://tango.freedesktop.org/Tango_Desktop_Project


Usage
-----

The following entry points are defined:

- ``udiskie`` to run the automount/notification daemon
- ``udiskie-mount`` user level mount/unlock operations
- ``udiskie-umount`` user level unmount/lock/eject/detach operations

See the man pages for further instructions


Contributing
------------

*udiskie* is developed on github_. Feel free to contribute patches as pull
requests as you see fit.

.. _github: https://github.com/coldfix/udiskie

Try to be consistent with `PEP 8`_ guidelines as far as possible and test
everything. Furthermore, your commit messages should start with a
capitalized verb for consistency. Unless your modification is completely
trivial, also add a message body to your commit.

.. _`PEP 8`: http://www.python.org/dev/peps/pep-0008/

Where possible dependency injection should be used to keep the module
easily testable.

Contact
-------

You can use the `github issues`_ to report any issues you encounter, ask
general questions or suggest new features. There is also a public `mailing
list`_ on sourceforge if you prefer email.

.. _`github issues`: https://github.com/coldfix/udiskie/issues
.. _`mailing list`: https://lists.sourceforge.net/lists/listinfo/udiskie-users

