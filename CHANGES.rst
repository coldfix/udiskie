CHANGELOG
---------

1.4.11
~~~~~~
Date: 13.05.2016

- protect password dialog against garbage collection (which makes the invoking
  coroutine hang up and not unlock the device)
- fix add_all/remove_all operations: only consider leaf/root devices within
  the handleable devices hierarchy
    - avoid considering the same device twice (#114)
    - makes sure every handleable device is considered at all in remove_all


1.4.10
~~~~~~
Date: 11.05.2016

- signal failing mount/unmount operations with non-zero exit codes (#110)
- suppress notifications for unhandled devices
- add rules for docker devices marking them unhandled to avoid excessive
  notifications (#113)
- allow mounting/unmounting using UUID (#90)
- prevent warning when starting without X session (#102)
- can now match against wildcards in config rules (#49)


1.4.9
~~~~~
Date: 02.04.2016

- add is_loop and loop_file properties for devices
- fix recursive mounting of crypto devices (udiskie-mount)
- prevent empty submenus from showing


1.4.8
~~~~~
Date: 09.02.2016

- fix problem with setupscript if utf8 is not the default encoding
- fix crash when starting without X
- basic support for loop devices (must be enabled explicitly at this time)
- fix handling of 2 more error cases


1.4.7
~~~~~
Date: 04.01.2016

- fix typo that prevents the yaml config file from being used
- fix problem with glib/gio gir API on slackware (olders versions?)
- fix bug when changing device state (e.g. when formatting existing device or
  burning ISO file to device)
- improve handling of race conditions with udisks1 backend
- fix notifications for devices without labels


1.4.6
~~~~~
Date: 28.12.2015

- cleanup recent bugfixes
- close some gates for more py2/unicode related bugs


1.4.5
~~~~~
Date: 24.12.2015

- fix another bug with unicode data on command line (py2)
- slightly improve stack traces in async code
- further decrease verbosity while removing devices


1.4.4
~~~~~
Date: 24.12.2015

- fix too narrow dependency enforcement
- make udiskie slightly less verbose in default mode


1.4.3
~~~~~
Date: 24.12.2015

- fix bug with unicode data on python2
- fix bug due to event ordering in udisks1
- fix bug due to inavailability of device data at specific time


1.4.2
~~~~~
Date: 22.12.2015

- fix regression in get_password_tty


1.4.1
~~~~~
Date: 19.12.2015

- fix problem in SmartTray due to recent transition to async


1.4.0
~~~~~
Date: 19.12.2015

- go async (with self-made async module for now, until gbulb becomes ready)
- specify GTK/Notify versions to be imported (hence fix warnings and a problem
  for the tray icon resulting from accidentally importing GTK2)
- add optional password caching


1.3.2
~~~~~

- revert "respect the automount flag for devices"
- make dependency on Gtk optional


1.3.1
~~~~~

- use icon hints from udev settings in notifications
- respect the automount flag for devices
- don't fail if libnotify is not available


1.3.0
~~~~~

- add actions to "Device added" notification
- allow to configure which actions should be added to notifications


1.2.1
~~~~~

- fix unicode issue in setup script
- update license/copyright notices


1.2.0
~~~~~

- use UDisks2 by default
- add --password-prompt command line argument and config file entry


1.1.3
~~~~~

- fix password prompt for GTK2 (tray is still broken for GTK2)
- fix minor documentation issues


1.1.2
~~~~~

- add key ``device_id`` for matching devices rather than only file systems
- improve documentation regarding dependencies


1.1.1
~~~~~

- fix careless error in man page


1.1.0
~~~~~

- implemented internationalization
- added spanish translation
- allow to choose icons from a configurable list


1.0.4
~~~~~

- compatibility with older version of pygobject (e.g. in Slackware 14.1)


1.0.3
~~~~~

- handle exception if no notification service is installed


1.0.2
~~~~~

- fix crash when calling udiskie mount/unmount utilites without udisks1
  installed


1.0.1
~~~~~

- fix crash when calling udiskie without having udisks1 installed
  (regression)


1.0.0
~~~~~

- port to PyGObject, removing dependencies on pygtk, zenity, dbus-python,
  python-notify
- use a PyGObject based password dialog
- remove --password-prompt parameter
- rename command line parameters
- add negations for all command line parameters


0.8.0
~~~~~

- remove the '--filters' parameter for good
- change config format to YAML
- change default config path to $XDG_CONFIG_HOME/udiskie/config.yml
- separate ignore filters from mount option filters
- allow to match multiple attributes against a device (AND-wise)
- allow to overwrite udiskies default handleability settings
- raise exception if --config file doesn't exist
- add --options parameter for udiskie-mount
- simplify local installations


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

