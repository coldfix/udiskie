"""
Utility for temporarily caching passwords.
"""

import keyutils


class PasswordCache(object):

    def __init__(self, timeout):
        self.timeout = timeout
        self.keyring = keyutils.KEY_SPEC_PROCESS_KEYRING

    def _key(self, device):
        return device.id_uuid.encode('utf-8')

    def __getitem__(self, device):
        key = self._key(device)
        key_id = keyutils.request_key(key, self.keyring)
        if key_id is None:
            raise KeyError("Key not cached!")
        self._touch(key_id)
        return keyutils.read_key(key_id).decode('utf-8')

    def __setitem__(self, device, value):
        key = self._key(device)
        key_id = keyutils.add_key(key, value.encode('utf-8'), self.keyring)
        self._touch(key_id)

    def _touch(self, key_id):
        if self.timeout > 0:
            keyutils.set_timeout(key_id, self.timeout)
