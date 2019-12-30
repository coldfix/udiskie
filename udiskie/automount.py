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

    def __init__(self, mounter, automount=True):
        """Store mounter as member variable."""
        self._mounter = mounter
        self._automount = automount
        self.events = {
            'device_changed': self.device_changed,
            'device_added': self.auto_add,
            'media_added': self.auto_add,
        }

    def is_on(self):
        return self._automount

    def toggle_on(self):
        self._automount = not self._automount

    def device_changed(self, old_state, new_state):
        """Mount newly mountable devices."""
        # udisks2 sometimes adds empty devices and later updates them - which
        # makes is_external become true at a time later than device_added:
        if (self._mounter.is_addable(new_state)
                and not self._mounter.is_addable(old_state)
                and not self._mounter.is_removable(old_state)):
            self.auto_add(new_state)

    @run_bg
    def auto_add(self, device):
        return self._mounter.auto_add(device, automount=self._automount)
