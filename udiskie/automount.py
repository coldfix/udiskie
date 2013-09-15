"""
Udiskie automounter daemon.
"""
__all__ = ['AutoMounter']

class AutoMounter:
    """
    Automatically mount newly added media.
    """
    def __init__(self, mounter):
        self.mounter = mounter

    def device_added(self, udevice):
        self.mounter.add_device(udevice)

    def media_added(self, udevice):
        self.mounter.add_device(udevice)

