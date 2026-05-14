"""
ctypes wrapper for keyutils functionality used in udiskie.
"""

__all__ = [
    "add_key",
    "read_key",
    "request_key",
    "revoke",
    "set_timeout",
]

import ctypes
import ctypes.util
import errno
import os
from array import array
from ctypes import (
    c_char_p,
    c_int32 as key_serial_t,
    c_long,
    c_size_t,
    c_uint,
    c_void_p,
)

KEY_SPEC_PROCESS_KEYRING = -2


class KeyutilsError(OSError):

    def __init__(self, code):
        self.code = code
        self.name = errno.errorcode.get(code, code)
        self.text = os.strerror(code)
        super().__init__(self.code, self.name, self.text)


class KeyNotAvailable(KeyutilsError):
    pass


class KeyExpired(KeyutilsError):
    pass


class KeyRevoked(KeyutilsError):
    pass


class KeyRejected(KeyutilsError):
    pass


_errno_map = {
    errno.ENOKEY: KeyNotAvailable,
    errno.EKEYEXPIRED: KeyExpired,
    errno.EKEYREVOKED: KeyRevoked,
    errno.EKEYREJECTED: KeyRejected,
}


def _errcheck(result):
    if result < 0:
        err_code = ctypes.get_errno()
        exc_type = _errno_map.get(err_code, KeyutilsError)
        raise exc_type(err_code)
    return result


def _declare(lib, name, restype, argtypes):
    try:
        func = lib[name]
    except (AttributeError, KeyError) as e:
        raise ImportError("Missing symbol in library 'keyutils.so'.") from e
    func.restype = restype
    func.argtypes = argtypes
    return func


_lib_name = ctypes.util.find_library("keyutils")
if _lib_name is None:
    raise ImportError("Library 'keyutils.so' not found")

_keyutils = ctypes.CDLL(_lib_name, use_errno=True)

_add_key = _declare(_keyutils, "add_key", key_serial_t, [
    c_char_p,       # [in] type
    c_char_p,       # [in] description
    c_void_p,       # [in] payload
    c_size_t,       # [in] plen
    key_serial_t,   # [in] ringid
])

_request_key = _declare(_keyutils, "request_key", key_serial_t, [
    c_char_p,       # [in] type
    c_char_p,       # [in] description
    c_char_p,       # [in] callout_info
    key_serial_t,   # [in] destringid
])

_keyctl_read = _declare(_keyutils, "keyctl_read", c_long, [
    key_serial_t,   # [in] id
    c_char_p,       # [out] buffer
    c_size_t,       # [in] buflen
])

_keyctl_revoke = _declare(_keyutils, "keyctl_revoke", c_long, [
    key_serial_t,   # [in] id
])

_keyctl_set_timeout = _declare(_keyutils, "keyctl_set_timeout", c_long, [
    key_serial_t,   # [in] id
    c_uint,         # [in] timeout
])

_keyctl_clear = _declare(_keyutils, "keyctl_clear", c_long, [
    key_serial_t,   # [in] ringid
])


def add_key(
    key: bytes,
    value: bytes,
    keyring: int = KEY_SPEC_PROCESS_KEYRING
) -> int:
    """
    Store secret with content.

    :param bytes key: key name
    :param bytes value: secret content
    :param int keyring: key ring ID
    :returns: ID of the inserted key
    :raises: KeyutilsError
    """
    return _errcheck(_add_key(b"user", key, value, len(value), keyring))


def is_valid(key: int) -> bool:
    """
    Check if the given key is available and valid.

    :param int key: key ID
    :returns: whether the key is accessible
    """
    return _keyctl_read(key, None, 0) >= 0


def read_key(key_id: int) -> bytes:
    """
    Read key content.

    :param int key_id: key ID
    :returns: secret content
    :raises: KeyutilsError
    """
    buflen = _errcheck(_keyctl_read(key_id, None, 0))
    while True:
        buffer = ctypes.create_string_buffer(buflen)
        ret = _errcheck(_keyctl_read(key_id, buffer, buflen))
        if 0 <= ret <= buflen:
            return buffer.value
        buflen = ret


def request_key(key: bytes, keyring: int = KEY_SPEC_PROCESS_KEYRING) -> int:
    """
    Find key ID by name.

    :param bytes key: key name
    :param int keyring: key ring ID
    :returns: key ID
    :raises: KeyutilsError
    """
    return _errcheck(_request_key(b"user", key, c_char_p(), keyring))


def revoke(key: int):
    """
    Revoke the specified key.

    :param int key: key ID
    :raises: KeyutilsError
    """
    _errcheck(_keyctl_revoke(key))


def set_timeout(key: int, timeout: int):
    """
    Set timeout in seconds for the specified key.

    :param int key: key ID
    :param int timeout: timeout in seconds
    :raises: KeyutilsError
    """
    _errcheck(_keyctl_set_timeout(key, timeout))


def clear(keyring: int = KEY_SPEC_PROCESS_KEYRING):
    """
    Clear all keys in the specified keyring.

    :param int keyring: keyring ID
    :raises: KeyutilsError
    """
    _errcheck(_keyctl_clear(keyring))


def list_keys(keyring: int = KEY_SPEC_PROCESS_KEYRING) -> [int]:
    """
    List key IDs in the specified keyring.

    :param int keyring: keyring ID
    :returns: list of key IDs
    :raises: keyutilsError
    """
    try:
        content = read_key(keyring)
    except KeyNotAvailable:
        return []
    return array('I', content).tolist()
