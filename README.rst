=======
udiskie
=======

|Version| |Downloads| |License|

*udiskie* is a UDisks_ front-end that allows to manage removeable media such
as CDs or flash drives from userspace. Its features include:

- automount removable media when inserted
- notifications (on insertion, mount, unmount, …)
- GTK tray icon to manage all available devices
- command line tools for manual un-/mounting
- support for LUKS encrypted devices
- password caching
- works with either udisks1 or udisks2
- an extensible code base (python)
- a maintainer who is open for suggestions;)

All features can be indidually enabled or disabled (yes, you can submit
unmaintainable code and make me salty!)

.. _UDisks: http://www.freedesktop.org/wiki/Software/udisks


Documentation
~~~~~~~~~~~~~

- Usage_
- Permissions_
- Installation_

Miscellaneous:

- `Custom mount paths`_
- `Acquiring debug information`_
- `Miscellaneous`_

.. _Usage: https://github.com/coldfix/udiskie/wiki/Usage
.. _Permissions: https://github.com/coldfix/udiskie/wiki/Permissions
.. _Installation: https://github.com/coldfix/udiskie/wiki/Installation
.. _Custom mount paths: https://github.com/coldfix/udiskie/wiki/Custom-mount-paths
.. _Acquiring debug information: https://github.com/coldfix/udiskie/wiki/Debugging-a-problem
.. _Miscellaneous: https://github.com/coldfix/udiskie/wiki/Miscellaneous


Project pages
~~~~~~~~~~~~~

The…

- `Wiki`_ contains installation instructions and additional information.
- `Man page`_ describes the command line options
- `Source Code`_ is hosted on github.
- `Latest Release`_ is available for download on PyPI.
- `Issue Tracker`_ is the right place to report any issues you encounter,
  ask general questions or suggest new features. There is also a public
  `Mailing List`_ if you prefer email.


.. _Wiki: https://github.com/coldfix/udiskie/wiki
.. _Man Page: https://raw.githubusercontent.com/coldfix/udiskie/master/doc/udiskie.8.txt
.. _Source Code: https://github.com/coldfix/udiskie
.. _Latest Release: https://pypi.python.org/pypi/udiskie/
.. _Issue Tracker: https://github.com/coldfix/udiskie/issues
.. _Mailing List: https://lists.coldfix.de/mailman/listinfo/udiskie


Roadmap
~~~~~~~

For the next udiskie versions, I am mainly concerned with quality assurance
and stability. For one this means reducing the number of supported runtime
configurations and make the remaining easier to test, i.e.:

- **drop support for python2** to avoid unicode issues and make use of the new
  asyncio module which provides better error handling (stack traces!) than the
  current solution.
- **drop support for udisks1**. The udisks1 API is rather unfit for the
  asynchronous nature of the problem which has led to numerous bugs and
  problems (plenty more probably waiting to be discovered as we speak)
- **add automated tests**. needed desperately…


.. |Version| image:: http://coldfix.de:8080/v/udiskie/badge.svg
   :target: https://pypi.python.org/pypi/udiskie/
   :alt: Latest Version

.. |Downloads| image:: http://coldfix.de:8080/d/udiskie/badge.svg
   :target: https://pypi.python.org/pypi/udiskie#downloads
   :alt: Downloads

.. |License| image:: http://coldfix.de:8080/license/udiskie/badge.svg
   :target: https://github.com/coldfix/udiskie/blob/master/COPYING
   :alt: License
