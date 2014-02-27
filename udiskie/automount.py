"""
Udiskie automounter daemon.
"""
__all__ = ['AutoMounter']

class AutoMounter(object):
    """
    Automatically mount newly added media.
    """
    def __init__(self, mounter):
        self._mounter = mounter

    def device_added(self, udevice):
        self._mounter.add_device(udevice)

    def media_added(self, udevice):
        self._mounter.add_device(udevice)

    def device_changed(self, old_state, new_state):
        """
        Check whether is_external changed, then mount
        """
        # fixes usecase: mount luks-cleartext when opened by
        # non-udiskie-software problem: in this case the device is not seen as
        # external from the beginning and thus not mounted
        if not old_state.is_external and new_state.is_external:
            self._mounter.add_device(new_state)

