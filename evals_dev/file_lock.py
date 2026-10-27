"""Blocking locks on existing file handles for offline evaluation tools."""
from __future__ import annotations

import errno
import os
from contextlib import contextmanager

if os.name == 'nt':
    from portalocker import LockFlags
    from portalocker.exceptions import LockException
    from portalocker.portalocker import Win32Locker
else:
    import fcntl


@contextmanager
def file_lock(handle, *, shared=False):
    """Hold a shared or exclusive lock without closing the caller's handle."""
    if os.name == 'nt':
        # Both modes must use LockFileEx, with no msvcrt retry limit or mixed backends.
        locker = Win32Locker()
        try:
            locker.lock(handle, LockFlags.SHARED if shared else LockFlags.EXCLUSIVE)
        except LockException as error:
            raise OSError(errno.EIO, 'file_lock_failed') from error
        try:
            yield
        finally:
            try:
                locker.unlock(handle)
            except LockException as error:
                raise OSError(errno.EIO, 'file_unlock_failed') from error
    else:
        fcntl.flock(handle, fcntl.LOCK_SH if shared else fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
