"""
Utility for temporarily caching passwords.
"""

import keyutils

# This import fails in python-keyring-keyutils, which is a not (yet) supported
# alternative for the python-keyring package. This lets us distinguish between
# the two identically named python packages (=keyring).
from keyutils import KEY_SPEC_PROCESS_KEYRING


class PasswordCache:

    def __init__(self, timeout):
        self.timeout = timeout
        self.keyring = KEY_SPEC_PROCESS_KEYRING

    def _key(self, device):
        return device.id_uuid.encode('utf-8')

    def _key_id(self, device):
        key = self._key(device)
        try:
            key_id = keyutils.request_key(key, self.keyring)
        except keyutils.Error:
            raise KeyError("Key has been revoked!") from None
        if key_id is None:
            raise KeyError("Key not cached!")
        return key_id

    def __contains__(self, device):
        try:
            self._key_id(device)
            return True
        except KeyError:
            return False

    def __getitem__(self, device):
        key_id = self._key_id(device)
        self._touch(key_id)
        try:
            return keyutils.read_key(key_id)
        except keyutils.Error:
            raise KeyError("Key not cached!") from None

    def __setitem__(self, device, value):
        key = self._key(device)
        if isinstance(value, str):
            value = value.encode('utf-8')
        key_id = keyutils.add_key(key, value, self.keyring)
        self._touch(key_id)

    def __delitem__(self, device):
        key_id = self._key_id(device)
        keyutils.revoke(key_id)

    def _touch(self, key_id):
        if self.timeout > 0:
            keyutils.set_timeout(key_id, self.timeout)
