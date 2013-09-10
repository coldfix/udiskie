=======
udiskie
=======

udiskie is a simple daemon that uses udisks_ to automatically mount removable
storage devices.

.. _udisks: http://www.freedesktop.org/wiki/Software/udisks

Maintainer Wanted
-----------------

I'm not longer using udiskie on my systems. The code still works, but it's been
neglected for a while.

Dependencies
------------

- dbus-python_
- pygobject_
- notify-python_
- zenity_

.. _dbus-python: http://dbus.freedesktop.org/releases/dbus-python/
.. _pygobject: http://ftp.gnome.org/pub/gnome/sources/pygobject/
.. _notify-python: http://www.galago-project.org/files/releases/source/notify-python/
.. _zenity: http://freecode.com/projects/zenity

Permissions
-----------

udiskie requires permission for the ``org.freedesktop.udisks.filesystem-mount``
as well as the ``org.freedesktop.udisks.luks-unlock`` action.  This is usually
granted in sessions launched with ConsoleKit_ support.  If run outside a
desktop manager with ConsoleKit_ support, the permission can be granted using
PolicyKit_ by creating a file called ``10-udiskie.pkla`` in
``/etc/polkit-1/localauthority/50-local.d`` with these contents:

.. _ConsoleKit: http://www.freedesktop.org/wiki/Software/ConsoleKit
.. _PolicyKit: http://www.freedesktop.org/wiki/Software/PolicyKit

::

    [udiskie]
    Identity=unix-group:storage
    Action=org.freedesktop.udisks.filesystem-mount
    ResultAny=yes

This configuration allows all members of the storage group to run udiskie.

Alternatively, to allow these actions to be executed for inactive sessions,
modify the file ``/usr/share/polkit-1/actions/org.freedesktop.udisks.policy``.
Make sure to change the setting for ``allow_inactive`` to 'yes':

::

    <action id="org.freedesktop.udisks.filesystem-mount">
      <description>Mount a device</description>
      <message>Authentication is required to mount the device</message>
      <defaults>
        <allow_any>yes</allow_any>
        <allow_inactive>yes</allow_inactive>
        <allow_active>yes</allow_active>
      </defaults>
    </action>

    ...

    <action id="org.freedesktop.udisks.luks-unlock">
      <description>Unlock an encrypted device</description>
      <message>Authentication is required to unlock an encrypted device</message>
      <defaults>
        <allow_any>no</allow_any>
        <allow_inactive>yes</allow_inactive>
        <allow_active>yes</allow_active>
      </defaults>
    </action>



