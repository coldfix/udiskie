"""
Automount utility.
"""

__all__ = ['AutoMounter']


class AutoMounter(object):

    """
    Automount utility.

    Being connected to the udiskie daemon, this component automatically
    mounts newly discovered external devices. Instances are constructed with
    a Mounter object, like so:

    >>> AutoMounter(Mounter(udisks=Daemon()))
    """

    def __init__(self, mounter):
        """
        Store mounter as member variable and connect to the underlying udisks.

        :param Mounter mounter: mounter object
        """
        self._mounter = mounter
        mounter.udisks.connect_all(self)

    def device_added(self, device):
        """
        Mount newly added devices.

        :param Device device: newly added device
        """
        if self._mounter.is_handleable(device):
            self._mounter.add(device)

    def media_added(self, device):
        """
        Mount newly added media.

        :param Device device: device with newly added media
        """
        if self._mounter.is_handleable(device):
            self._mounter.add(device)

    def device_changed(self, old_state, new_state):
        """
        Mount newly mountable devices.

        :param Device old_state: before change
        :param Device new_state: after change
        """
        # udisks2 sometimes adds empty devices and later updates them which
        # makes is_external become true not at device_added time:
        if (self._mounter.is_handleable(new_state)
                and not self._mounter.is_handleable(old_state)):
            self._mounter.add(new_state)
