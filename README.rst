=======
udiskie
=======

|Version| |Downloads| |License|

*udiskie* is a front-end for UDisks written in python. Its main purpose is
automatically mounting removable media, such as CDs or flash drives. It has
optional mount notifications, a GTK tray icon and user level CLIs for manual
mount and unmount operations. The media will be mounted in a new directory
under ``/media`` or ``/run/media/USER/``, using the device name if possible.


Project pages
-------------

The `source code`_ is hosted on github.

Check out the `wiki`_ for installation instructions and general questions.
Feel free to edit.

You can use the github `issue tracker`_ to report any issues you encounter,
ask general questions or suggest new features.

There is also a public `mailing list`_ if you prefer email.

The `latest release`_ can be downloaded from PyPI.

.. _source code: https://github.com/coldfix/udiskie
.. _wiki: https://github.com/coldfix/udiskie/wiki
.. _issue tracker: https://github.com/coldfix/udiskie/issues
.. _mailing list: http://lists.coldfix.de/mailman/listinfo/udiskie
.. _latest release: https://pypi.python.org/pypi/udiskie/


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

0. benefit from others' work

   - *udiskie* may be in your distribution's official repositories
   - check out the wiki_ for guidance

   If neither of this helps, here are some general hints:

1. install dependencies:

   Required:

   - setuptools_
   - PyGObject_
   - UDisks_ (UDisks1 or UDisks2)
   - GTK3 (+introspection). GTK2 also works if not using the tray icon.
   - docopt_ (can automatically be installed by pip)

   Optional:

   - libnotify (+introspection)
   - the notification daemon of your choice
   - gettext_ to build translation files (during setup step)
   - PyYAML_ for config file (can automatically be installed by pip)

   Access to system resources is mediated using PyGObject_, which is why some
   packages need to be built with *+introspection*. Check the contents of the
   folder ``/usr/lib/girepository-1.0/`` (or similar). There should be the
   following typelibs:

   - Gio-2.0
   - GLib-2.0
   - GObject-2.0
   - Gtk-3.0
   - Notify-0.7

   If you installed the above dependencies, but some of the typelibs are
   missing they might be distributed in separate packages. Note that the
   version numbers just indicate what udiskie is tested with, but it may
   work with other versions as well.

2. use pip to download and install *udiskie* itself:

   .. code-block:: bash

       # from PyPI:
       pip install udiskie

       # from a local checkout:
       pip install .

3. go back to the wiki_ and edit. ;)


.. _wiki: https://github.com/coldfix/udiskie/wiki
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
      // NOTE: there must be a comma at the end of each line except for the last:
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
        "org.freedesktop.udisks2.power-off-drive": YES,
        // required for udisks2 if using udiskie from another seat (e.g. systemd):
        "org.freedesktop.udisks2.filesystem-mount-other-seat": YES,
        "org.freedesktop.udisks2.encrypted-unlock-other-seat": YES,
        "org.freedesktop.udisks2.eject-media-other-seat": YES,
        "org.freedesktop.udisks2.power-off-drive-other-seat": YES
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
- `PyGObject APIs`_
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


.. |Version| image:: http://coldfix.de:8080/v/udiskie/badge.svg
   :target: https://pypi.python.org/pypi/udiskie/
   :alt: Latest Version

.. |Downloads| image:: http://coldfix.de:8080/d/udiskie/badge.svg
   :target: https://pypi.python.org/pypi/udiskie#downloads
   :alt: Downloads

.. |License| image:: http://coldfix.de:8080/license/udiskie/badge.svg
   :target: https://github.com/coldfix/udiskie/blob/master/COPYING
   :alt: License
