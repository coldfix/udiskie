CHANGELOG
---------

0.6.1 (bug fix)
~~~~~~~~~~~~~~~

- fix udisks2 external device detection bug: all devices were considered
  external when using ``Sniffer`` (as done in the udiskie-mount and
  udiskie-umount tools)


0.6.0 (udisks2 support, bug fix)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- cache device states to avoid some race conditions
- show filesystem label in mount/unmount notifications
- retry to unlock LUKS devices when wrong password was entered twice
- show 'eject' only if media is available (udisks1 ejects only in this case)
- (un-) mount/lock notifications shown even when operations failed
- refactor internal API
- experimental support for udisks2


0.5.3 (feature, bug fix)
~~~~~~~~~~~~~~~~~~~~~~~~

- add '__ignore__' config file option to prevent handling specific devices
- delay notifications until termination of long operations


0.5.2 (tray icon)
~~~~~~~~~~~~~~~~~

- add tray icon (pygtk based)
- eject / detach drives from command line


0.5.1 (mainly internal changes)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- use setuptools entry points to create the executables
- make udiskie a namespace package


0.5.0 (LUKS support)
~~~~~~~~~~~~~~~~~~~~

- support for LUKS devices (using zenity for password prompt)
- major refactoring
- use setuptools as installer

