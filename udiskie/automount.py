"""
Udiskie automounter daemon.
"""
__all__ = ['AutoMounter']

import logging

class AutoMounter:
    """
    Automatically mount newly added media.
    """
    def __init__(self, mounter):
        self.log = logging.getLogger('udiskie.mount.AutoMounter')
        self.mounter = mounter

    def connect(self, daemon):
        daemon.connect('device_added', self.device_added)
        daemon.connect('media_added', self.media_added)

    def disconnect(self, daemon):
        daemon.disconnect('device_added', self.device_added)
        daemon.disconnect('media_added', self.media_added)

    def device_added(self, udevice):
        self.mounter.add_device(udevice)

    def media_added(self, udevice):
        self.mounter.add_device(udevice)

