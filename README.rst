=======
udiskie
=======

|Version| |License|

*udiskie* is a UDisks_ front-end that allows to manage removeable media such
as CDs or flash drives from userspace. Its features include:

- automount removable media
- notifications
- tray icon
- command line tools for manual un-/mounting
- LUKS encrypted devices
- unlocking with keyfiles (requires udisks 2.6.4)
- loop devices (mounting iso archives, requires UDisks2)
- password caching (requires python keyutils 0.3)

All features can be indidually enabled or disabled.

.. _UDisks: http://www.freedesktop.org/wiki/Software/udisks


Documentation
-------------

- Usage_
- Installation_
- `Debug Info`_
- Troubleshooting_
- FAQ_
- Roadmap_

.. _Usage: https://github.com/coldfix/udiskie/wiki/Usage
.. _Installation: https://github.com/coldfix/udiskie/wiki/Installation
.. _Debug Info: https://github.com/coldfix/udiskie/wiki/Debug-Info
.. _Troubleshooting: https://github.com/coldfix/udiskie/wiki/Troubleshooting
.. _FAQ: https://github.com/coldfix/udiskie/wiki/FAQ
.. _Roadmap: https://github.com/coldfix/udiskie/blob/master/HACKING.rst#roadmap


Links
-----

- `Wiki`_
- `Man page`_
- `Source Code`_
- `Latest Release`_
- `Issue Tracker`_

.. _Wiki: https://github.com/coldfix/udiskie/wiki
.. _Man Page: https://raw.githubusercontent.com/coldfix/udiskie/master/doc/udiskie.8.txt
.. _Source Code: https://github.com/coldfix/udiskie
.. _Latest Release: https://pypi.python.org/pypi/udiskie/
.. _Issue Tracker: https://github.com/coldfix/udiskie/issues


.. Badges:

.. |Version| image::   https://img.shields.io/pypi/v/udiskie.svg
   :target:            https://pypi.python.org/pypi/udiskie
   :alt:               Version

.. |License| image::   https://img.shields.io/pypi/l/udiskie.svg
   :target:            https://github.com/coldfix/udiskie/blob/master/COPYING
   :alt:               License: MIT
