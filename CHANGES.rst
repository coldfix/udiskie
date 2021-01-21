CHANGELOG
---------

2.3.0
~~~~~
Date: 07.05.2020

- don't swallow STDOUT for notify-commands
- default to appindicator if tray is requested under wayland
- don't auto-disable tray when running in "pure" wayland session
- set window role on the password dialog


2.2.0
~~~~~
Date: 07.05.2020

- add Italian translation
- remove unneeded ``xdg`` from optional dependencies
- fix a typo in Spanish translation and update russian translation files


2.1.1
~~~~~
Date: 17.04.2020

- handle XDG_CONFIG_HOME variable without external pyxdg dependency
- silence warning when using AppIndicator
- make ``--appindicator`` sufficient to show icon (previously additionally
  required ``--tray``)
- improve wording in password dialog "Remember" -> "Cache"
- make some of the logging more concise
- fix recursive adding/removing of some child devices:
    - fix incorrect root device detection for devices without Drive property
      (e.g. children of loop devices)
    - fix ``--detach`` option when applied to partitions of loop devices


2.1.0
~~~~~
Date: 02.02.2020

- fix some typos (thanks @torstehu, #197)
- change how device rules are evaluated: lookup undecided rules on parent
  device (fixes issue with filters not applying to subdevices of a matched
  device, see #198)
- change builtin rules to not show loop devices with ``HintIgnore``, see #181
- change how is_external attribute is compute: use the value from udisks
  directly (fixes issue with is_external property not behaving as expected,
  see #185)
- add 'skip' keyword for rules to skip evaluation of further rules on this
  device, and continue directly on the parent


2.0.4
~~~~~
Date: 21.01.2020

- fix user commands that output non-utf8 data


2.0.3
~~~~~
Date: 20.01.2020

- fix exception when using non-device parameters with DeviceCommand
  (e.g. in --notify-command)


2.0.2
~~~~~
Date: 30.12.2019

- hotfix for automounting being broken since 2.0.0


2.0.1
~~~~~
Date: 28.12.2019

- use ``importlib.resources`` directly on py3.7 and above, rather than
  requiring ``importlib_resources`` as additional dependency


2.0.0
~~~~~
Date: 26.12.2019

- require python >= 3.5
- drop python2 support
- drop udisks1 support
- drop command line options corresponding to udisks version selection (-1, -2)
- use py35's ``async def`` functions -- improving stack traces upon exception
- internal refactoring and simplifications
- add "show password" checkbox in password dialog


1.7.7
~~~~~
Date: 17.02.2019

- keep password dialog always on top
- fix stdin-based password prompts


1.7.6
~~~~~
Date: 17.02.2019

- add russian translations (thanks @mr-GreyWolf)
- fixed deprecation warnings in setup.py (thanks @sealj553)


1.7.5
~~~~~
Date: 24.05.2018

- fix "NameError: 'Async' is not defined" when starting without tray icon


1.7.4
~~~~~
Date: 17.05.2018

- fix attribute error when using options in udiskie-mount (#159)
- fix tray in appindicator mode (#156)
- possibly fix non-deterministic bugs (due to garbage collection) by keeping
  global reference to all active asyncs


1.7.3
~~~~~
Date: 13.12.2017

- temporary workaround for udisks2.7 requiring ``filesystem-mount-system``
  when trying to mount a LUKS cleartext device diretcly after unlocking


1.7.2
~~~~~
Date: 18.10.2017

- officially deprecate udisks1
- officially deprecate python2 (want python >= 3.5)
- fix startup crash on py2
- fix exception when inserting LUKS device if ``--password-prompt`` or udisks1 is used
- fix minor problem with zsh autocompletion


1.7.1
~~~~~
Date: 02.10.2017

- add an "open keyfile" button to the password dialog
- add warning if mounting device without ntfs-3g (#143)
- fix problem with LVM devices


1.7.0
~~~~~
Date: 26.03.2017

- add joined ``device_config`` list in the config file
- deprecate ``mount_options`` and ``ignore_device`` in favor of
  ``device_config``
- can configure ``automount`` per device using the new ``device_config`` [#107]
- can configure keyfiles (requires udisks 2.6.4) [#66]
- remove mailing list


1.6.2
~~~~~
Date: 06.03.2017

- Show losetup/quit actions only in ex-menu
- Show note in menu if no devices are found


1.6.1
~~~~~
Date: 24.02.2017

- add format strings for the undocumented ``udiskie-info`` utility
- speed up autocompletion times, for ``udiskie-mount`` by about a factor
  three, for ``udiskie-umount`` by about a factor 10


1.6.0
~~~~~
Date: 22.02.2017

- fix crash on startup if config file is empty
- add ``--notify-command`` to notify external programs (@jgraef) [#127]
- can enable/disable automounting via special right-click menu [#98]
- do not explicitly specify filesystem when mounting [#131]


1.5.1
~~~~~
Date: 03.06.2016

- fix unicode issue that occurs on python2 when stdout is redirected (in
  particular for zsh autocompletion)


1.5.0
~~~~~
Date: 03.06.2016

- make systray menu flat (use ``udiskie --tray --menu smart`` to request the
  old menu) [#119]
- extend support for loop devices (requires UDisks2) [#101]
- support ubuntu/unity AppIndicator backend for status icon [#59]
- add basic utility to obtain info on block devices [#122]
- add zsh completions [#26]
- improve UI menu labels for devices
- fix error when force-ejecting device [#121]
- respect configured ignore-rules in ``udiskie-umount``
- fix error message for empty task lists [#123]


1.4.12
~~~~~~
Date: 15.05.2016

- log INFO events to STDOUT (#112)
- fix exception in notifications when action is not available. This concerns
  the retry button in the ``job_failed`` notification, as well as the browse
  action in the ``device_mounted`` notification (#117)
- don't show 'browse' action in tray menu if unavailable


1.4.11
~~~~~~
Date: 13.05.2016

- protect password dialog against garbage collection (which makes the invoking
  coroutine hang up and not unlock the device)
- fix add_all/remove_all operations: only consider leaf/root devices within
  the handleable devices hierarchy:
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

