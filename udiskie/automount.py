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

