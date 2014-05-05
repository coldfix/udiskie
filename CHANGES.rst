CHANGELOG
---------

0.8.0 (in preparation)
~~~~~~~~~~~~~~~~~~~~~~

- remove the '--filters' parameter for good
- change config format to YAML
- change default config path to $XDG_CONFIG_HOME/udiskie/config.yml
- separate ignore filters from mount option filters
- allow to match multiple attributes against a device (AND-wise)
- allow to overwrite udiskies default handleability settings
- raise exception if --config file doesn't exist


0.7.0
~~~~~

There are some backward incompatible changes, hence the version break:

- command line parameter '-f'/'--filters' renamed to '-C'/'--config'
- add sections in config file to disable individual mount notifications and
  set defaults for some program options (udisks version, prompt, etc)
- refactor ``udiskie.cli``, ``udiskie.config`` and ``udiskie.tray``
- revert 'make udiskie a namespace package'
- add 'Browse folder' action to tray menu
- add 'Browse folder' action button to mount notifications
- add '--no-automounter' command line option to disable automounting
- add '--auto-tray' command line option to use a tray icon that
  automatically disappears when no actions are available
- show notifications when devices dis-/appear (can be disabled via config
  file)
- show 'id_label' in tray menu, if available (instead of mount path or
  device path)
- add 'Job failed' notifications
- add 'Retry' button to failed notifications
- remove automatic retries to unlock LUKS partitions
- pass only device name to external password prompt
- add '--quiet' command line option
- ignore devices ignored by udev rules


0.6.4
~~~~~

- fix logging in setup.py
- more verbose log messages (with time) when having -v on
- fix mounting devices that are added as 'external' and later changed to
  'internal' [udisks1] (applies to LUKS devices that are opened by an udev
  rule for example)


0.6.3 (bug fix)
~~~~~~~~~~~~~~~

- fix exception in Mounter.detach_device if unable to detach
- fix force-detach for UDisks2 backend
- automatically use UDisks2 if UDisks1 is not available
- mount unlocked devices only once, removes error message on UDisks2
- mention __ignore__ in man page

0.6.2 (aesthetic)
~~~~~~~~~~~~~~~~~

- add custom icons for the context menu of the system tray widget


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

