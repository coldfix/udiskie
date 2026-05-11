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


def _errcheck(result, func, arguments):
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
    func.errcheck = _errcheck
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
    return _add_key(b"user", key, value, len(value), keyring)


def read_key(key_id: int) -> bytes:
    """
    Read key content.

    :param int key_id: key ID
    :returns: secret content
    :raises: KeyutilsError
    """
    buflen = 0
    buffer = None
    while True:
        ret = _keyctl_read(key_id, buffer, buflen)
        if 0 <= ret <= buflen:
            return buffer.value
        buflen = ret
        buffer = ctypes.create_string_buffer(buflen)


def request_key(key: bytes, keyring: int = KEY_SPEC_PROCESS_KEYRING) -> int:
    """
    Find key ID by name.

    :param bytes key: key name
    :param int keyring: key ring ID
    :returns: key ID
    :raises: KeyutilsError
    """
    return _request_key(b"user", key, c_char_p(), keyring)


def revoke(key: int):
    """
    Revoke the specified key.

    :param int key: key ID
    :raises: KeyutilsError
    """
    _keyctl_revoke(key)


def set_timeout(key: int, timeout: int):
    """
    Set timeout in seconds for the specified key.

    :param int key: key ID
    :param int timeout: timeout in seconds
    :raises: KeyutilsError
    """
    _keyctl_set_timeout(key, timeout)
