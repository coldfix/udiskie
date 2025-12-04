=======
udiskie
=======

|Version| |License| |Translations|

*udiskie* is a udisks2_ front-end that allows to manage removable media such
as CDs or flash drives from userspace.

|Screenshot|

Its features include:

- automount removable media
- notifications
- tray icon
- command line tools for manual un-/mounting
- LUKS encrypted devices
- unlocking with keyfiles (requires udisks 2.6.4)
- loop devices (mounting iso archives)
- password caching (requires python keyutils 0.3)

All features can be individually enabled or disabled.

**NOTE:** support for python2 and udisks1 have been removed. If you need a
version of udiskie that supports python2, please check out the ``1.7.X``
releases or the ``maint-1.7`` branch.

.. _udisks2: https://www.freedesktop.org/wiki/Software/udisks

Links
-----

- `Documentation`_

  - Usage_
  - Installation_
  - `Debug Info`_
  - Troubleshooting_
  - FAQ_

- `Man page`_
- `Source Code`_
- `Latest Release`_
- `Issue Tracker`_

.. _Documentation:      https://github.com/coldfix/udiskie/wiki
.. _Usage:              https://github.com/coldfix/udiskie/wiki/Usage
.. _Installation:       https://github.com/coldfix/udiskie/wiki/Installation
.. _Debug Info:         https://github.com/coldfix/udiskie/wiki/Debug-Info
.. _Troubleshooting:    https://github.com/coldfix/udiskie/wiki/Troubleshooting
.. _FAQ:                https://github.com/coldfix/udiskie/wiki/FAQ

.. _Man Page:       https://raw.githubusercontent.com/coldfix/udiskie/master/doc/udiskie.8.txt
.. _Source Code:    https://github.com/coldfix/udiskie
.. _Latest Release: https://pypi.python.org/pypi/udiskie/
.. _Issue Tracker:  https://github.com/coldfix/udiskie/issues


.. Badges:

.. |Version| image::   https://img.shields.io/pypi/v/udiskie.svg
   :target:            https://pypi.python.org/pypi/udiskie
   :alt:               Version

.. |License| image::   https://img.shields.io/pypi/l/udiskie.svg
   :target:            https://github.com/coldfix/udiskie/blob/master/COPYING
   :alt:               License: MIT

.. |Translations| image:: http://weblate.coldfix.de/widgets/udiskie/-/udiskie/svg-badge.svg
   :target:               http://weblate.coldfix.de/engage/udiskie/
   :alt:                  Translations

.. |Screenshot| image:: https://raw.githubusercontent.com/coldfix/udiskie/master/screenshot.png
   :target:             https://raw.githubusercontent.com/coldfix/udiskie/master/screenshot.png
   :alt:                Screenshot


Contributing
------------

*udiskie* is developed on github_. Feel free to contribute patches as pull
requests here. If you don't have nor want a github account, you can send me
the relevant files via email.

Further resources:

- `UDisks1 API`_
- `UDisks2 API`_
- `PyGObject APIs`_

.. _github: https://github.com/coldfix/udiskie
.. _PEP8: http://www.python.org/dev/peps/pep-0008/
.. _`unit tests`: http://docs.python.org/2/library/unittest.html

.. _`UDisks1 API`: http://udisks.freedesktop.org/docs/1.0.5/
.. _`UDisks2 API`: http://udisks.freedesktop.org/docs/latest/
.. _`PyGObject APIs`: http://lazka.github.io/pgi-docs/index.html


Translations
------------

Translations by users are always welcome. There are currently two main ways
to edit translations:

Weblate
~~~~~~~

I have setup a Weblate_ UI to make translation editing more convenient. This
is so far experimental. Please let me know if you encounter any issues. I may
decide remove this interface in the future because it sucks the RAM out of my
server.

Manually
~~~~~~~~

The corresponding files are in the
`lang`_ subfolder. In order to create a new translation, find out the locale
name for your language, e.g. ``es_ES`` for Spanish, and create a translation
file in the ``lang`` folder as follows::

    cd lang
    make es_ES.po

or simply copy the `udiskie.pot`_ to a ``.po`` file with the name of the
target locale and start editing. It's also best to fill in your name and email
address.

The translations may become outdated as udiskie changes. If you notice an
outdated translation, please edit the corresponding ``.po`` file in submit a
patch, even for very small changes.

In order to test udiskie with your locally edited translation files, type
(still from the ``lang`` folder)::

    export TEXTDOMAINDIR=$PWD/../build/locale
    export LANG=es_ES.UTF-8

    make mo

    udiskie

.. _lang: https://github.com/coldfix/udiskie/tree/master/lang
.. _udiskie.pot: https://raw.githubusercontent.com/coldfix/udiskie/master/lang/udiskie.pot
