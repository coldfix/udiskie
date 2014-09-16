=======
udiskie
=======

|Version| |Downloads| |License|

*udiskie* is a python front-end for UDisks. Its main purpose is
automatically mounting removable media, such as CDs or flash drives. It has
optional mount notifications, a GTK tray icon and user level CLIs for manual
mount and unmount operations. The media will be mounted in a new directory
under ``/media`` or ``/run/media/USER/``, using the device name if possible.


Usage
-----

Start the automount and notification daemon and show a system tray icon:

.. code-block:: bash

    udiskie --tray

Mount or unlock a specific device manually:

.. code-block:: bash

    udiskie-mount /dev/sdb1

Unmount or remove a specific device manually:

.. code-block:: bash

    udiskie-umount /media/<device-name>
    # or with udisks2
    udiskie-umount -2 /run/media/<user>/<device>

See the man page for further instructions


Installation
------------

If not installing *udiskie* via your distribution's repositories, you should
use pip:

.. code-block:: bash

    # from PyPI:
    pip install udiskie

    # from a local checkout:
    pip install .

Before doing this, however, take care to install all needed dependencies:

- setuptools_
- UDisks_ (either UDisks1 or UDisks2 is fine)
- PyGObject_ (GTK3+)
- PyYAML_ (can automatically be installed by pip)
- docopt_ (can automatically be installed by pip)
- gettext_ (optional)
- libnotify and a notification daemon (optional)

Access to system resources is implemented using PyGObject_. Therefore, some
typelibs need to be installed in ``/usr/lib/girepository-1.0/``. For this,
you have to enable introspection when building the corresponding packages.
*udiskie* is tested with the following versions:

- Gio-2.0
- GLib-2.0
- GObject-2.0
- Gtk-2.0
- Notify-0.7

Most of these dependencies are best installed from your distribution's
package repositories.

.. _setuptools: https://pypi.python.org/pypi/setuptools/
.. _UDisks: http://www.freedesktop.org/wiki/Software/udisks
.. _PyGObject: https://wiki.gnome.org/Projects/PyGObject
.. _PyYAML: https://pypi.python.org/pypi/PyYAML
.. _docopt: http://docopt.org/
.. _gettext: http://www.gnu.org/software/gettext/


Permissions
-----------

*udiskie* requires permission for some polkit_ actions which are usually
granted when using a desktop environment. If your login session is not
properly activated you may need to customize your polkit settings. Create the
file ``/etc/polkit-1/rules.d/50-udiskie.rules`` with the following contents:

.. code-block:: javascript

    polkit.addRule(function(action, subject) {
      var YES = polkit.Result.YES;
      var permission = {
        // required for udisks1:
        "org.freedesktop.udisks.filesystem-mount": YES,
        "org.freedesktop.udisks.luks-unlock": YES,
        "org.freedesktop.udisks.drive-eject": YES,
        "org.freedesktop.udisks.drive-detach": YES,
        // required for udisks2:
        "org.freedesktop.udisks2.filesystem-mount": YES,
        "org.freedesktop.udisks2.encrypted-unlock": YES,
        "org.freedesktop.udisks2.eject-media": YES,
        "org.freedesktop.udisks2.power-off-drive": YES
      };
      if (subject.isInGroup("storage")) {
        return permission[action.id];
      }
    });

This configuration allows all members of the *storage* group to run
udiskie.

.. _polkit: http://www.freedesktop.org/wiki/Software/polkit/


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

When doing a local installation, for example in a virtualenv, you can
manually change the installation prefix for the icon data files like so:

.. code-block:: bash

    python setup.py install --install-data ~/.local

The icons roughly follow the `Tango style guidelines`_. Some icons incorporate
the CDROM icon of the base icon theme of the `Tango desktop project`_
(released into the public domain).

.. _`Tango style guidelines`: http://tango.freedesktop.org/Tango_Icon_Theme_Guidelines
.. _`Tango desktop project`: http://tango.freedesktop.org/Tango_Desktop_Project


Contributing
------------

*udiskie* is developed on github_. Feel free to contribute patches as pull
requests here.

Try to be consistent with the PEP8_ guidelines. Add `unit tests`_ for all
non-trivial functionality if possible. `Dependency injection`_ is a great
pattern to keep modules flexible and testable.

Commits should be reversible, independent units if possible. Use descriptive
titles and also add an explaining commit message unless the modification is
trivial. See also: `A Note About Git Commit Messages`_.

Further resources:

- `UDisks1 API`_
- `UDisks2 API`_
- `PyGObject APIs`
- `Icon naming`_
- `Icon lookup`_

.. _github: https://github.com/coldfix/udiskie
.. _PEP8: http://www.python.org/dev/peps/pep-0008/
.. _`unit tests`: http://docs.python.org/2/library/unittest.html
.. _`Dependency injection`: http://www.youtube.com/watch?v=RlfLCWKxHJ0
.. _`A Note About Git Commit Messages`: http://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html

.. _`UDisks1 API`: http://udisks.freedesktop.org/docs/1.0.5/
.. _`UDisks2 API`: http://udisks.freedesktop.org/docs/latest/
.. _`PyGObject APIs`: http://lazka.github.io/pgi-docs/index.html
.. _`Icon naming`: http://standards.freedesktop.org/icon-naming-spec/icon-naming-spec-latest.html
.. _`Icon lookup`: http://standards.freedesktop.org/icon-theme-spec/icon-theme-spec-latest.html


Contact
-------

You can use the `github issues`_ to report any issues you encounter, ask
general questions or suggest new features. There is also a public `mailing
list`_ on sourceforge if you prefer email.

.. _`github issues`: https://github.com/coldfix/udiskie/issues
.. _`mailing list`: https://lists.sourceforge.net/lists/listinfo/udiskie-users


.. |Version| image:: https://pypip.in/v/udiskie/badge.png
   :target: https://pypi.python.org/pypi/udiskie/
   :alt: Latest Version

.. |Downloads| image:: https://pypip.in/d/udiskie/badge.png
   :target: https://pypi.python.org/pypi/udiskie/
   :alt: Downloads

.. |License| image:: https://pypip.in/license/udiskie/badge.png
   :target: https://pypi.python.org/pypi/udiskie/
   :alt: License
