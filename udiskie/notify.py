import pynotify
import gio

class Notify:
    def __init__(self, name):
        pynotify.init(name)

    def mount(self, device, path):
        try:
            pynotify.Notification('Device mounted',
                                  '%s mounted on %s' % (device, path),
                                  'drive-removable-media').show()
        except gio.Error:
            pass

    def umount(self, device):
        try:
            pynotify.Notification('Device unmounted',
                                  '%s unmounted' % (device,),
                                  'drive-removable-media').show()
        except gio.Error:
            pass
