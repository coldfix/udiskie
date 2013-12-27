"""
Udiskie automounter daemon.
"""
__all__ = ['AutoMounter']

class AutoMounter(object):
    """
    Automatically mount newly added media.
    """
    def __init__(self, mounter):
        self.mounter = mounter

    def device_added(self, udevice):
        self.mounter.add_device(udevice)

    def media_added(self, udevice):
        self.mounter.add_device(udevice)

    # Automount LUKS cleartext holders after they have been unlocked.
    # Why doesn't this work in device_added?
    def device_unlocked(self, udevice):
        self.mounter.add_device(udevice.luks_cleartext_holder)

