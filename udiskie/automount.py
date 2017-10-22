"""
Automount utility.
"""

from .common import DaemonBase
from .async_ import run_bg


__all__ = ['AutoMounter']


class AutoMounter(DaemonBase):

    """
    Automount utility.

    Being connected to the udiskie daemon, this component automatically
    mounts newly discovered external devices. Instances are constructed with
    a Mounter object, like so:

    >>> automounter = AutoMounter(Mounter(udisks=Daemon()))
    >>> automounter.activate()
    """

    def __init__(self, mounter):
        """Store mounter as member variable."""
        self._mounter = mounter
        self.events = {
            'device_changed': self.device_changed,
            'device_added': run_bg(self._mounter.auto_add),
            'media_added': run_bg(self._mounter.auto_add),
        }

    def device_changed(self, old_state, new_state):
        """Mount newly mountable devices."""
        # udisks2 sometimes adds empty devices and later updates them - which
        # makes is_external become true at a time later than device_added:
        if (self._mounter.is_addable(new_state)
                and not self._mounter.is_addable(old_state)
                and not self._mounter.is_removable(old_state)):
            run_bg(self._mounter.auto_add)(new_state)
