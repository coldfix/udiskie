=======
udiskie
=======

udiskie is a simple daemon that uses udisks_ to automatically mount removable
storage devices. It also provides a user level CLI for mount and unmount
operations.

.. _udisks: http://www.freedesktop.org/wiki/Software/udisks


Dependencies
------------

- dbus-python_ required for all operation modes
- pygobject_ to run the automount/notification daemon (provides the main loop)
- notify-python_ or notify2_ for mount notifications
- zenity_ to unlock LUKS devices
- pygtk_ to show the system tray icon

.. _dbus-python: http://dbus.freedesktop.org/releases/dbus-python/
.. _pygobject: http://ftp.gnome.org/pub/gnome/sources/pygobject/
.. _notify-python: http://www.galago-project.org/files/releases/source/notify-python/
.. _notify2: https://pypi.python.org/pypi/notify2
.. _zenity: http://freecode.com/projects/zenity
.. _pygtk: http://www.pygtk.org


Permissions
-----------

udiskie requires permission for the following PolicyKit_ actions:

.. _PolicyKit: http://www.freedesktop.org/wiki/Software/PolicyKit

- ``org.freedesktop.udisks.filesystem-mount`` for mounting and unmounting
- ``org.freedesktop.udisks.luks-unlock`` to unlock LUKS devices
- ``org.freedesktop.udisks.drive-eject`` to eject drives
- ``org.freedesktop.udisks.drive-detach`` to detach drives

These are usually granted when using a desktop environment. If your login
session is not properly activated you may need to customize your PolicyKit
settings.

::

    [udiskie]
    Identity=unix-group:storage
    Action=org.freedesktop.udisks.filesystem-mount;org.freedesktop.udisks.luks-unlock;org.freedesktop.udisks.drive-eject;org.freedesktop.udisks.drive-detach
    ResultAny=yes

This configuration allows all members of the storage group to run udiskie.

Alternatively, change the setting for ``allow_inactive`` to *yes* in the
file ``/usr/share/polkit-1/actions/org.freedesktop.udisks.policy``:

::

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

Try to be consistent with `PEP 8` guidelines as far as possible and test
everything. Furthermore, your commit messages should start with a
capitalized verb for consistency. Unless your modification is completely
trivial, also add a message body to your commit.

.. _`PEP 8`: http://www.python.org/dev/peps/pep-0008/

Where possible dependency injection should be used to keep the module
easily testable.

