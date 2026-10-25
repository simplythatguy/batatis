"""Refuse outbound connections in a test, without refusing the event loop's own socket.

On Windows, `asyncio.run()` builds its event loop on a socketpair that connects to
127.0.0.1. A blanket ban on `socket.socket.connect` therefore fails every test that
opens a loop, with `Failed: unexpected network`, even when nothing leaves the machine.

Provider traffic goes to a public host, so loopback stays allowed and everything else
still fails loudly. The returned list holds the addresses that were refused, so a
caller can keep asserting that nothing was attempted.
"""
from __future__ import annotations

import socket

import pytest

LOOPBACK = ('127.0.0.1', '::1', 'localhost')


def _is_loopback(address) -> bool:
    if isinstance(address, tuple) and address:
        host = address[0]
        return isinstance(host, str) and (host in LOOPBACK or host.startswith('127.'))
    return False


def block_network(monkeypatch, *, message: str = 'unexpected network') -> list:
    """Fail any connection that is not loopback, for the duration of the test."""
    blocked = []
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def guarded(self, address, *args, **kwargs):
        if _is_loopback(address):
            return real_connect(self, address, *args, **kwargs)
        blocked.append(address)
        pytest.fail(message)

    def guarded_ex(self, address, *args, **kwargs):
        if _is_loopback(address):
            return real_connect_ex(self, address, *args, **kwargs)
        blocked.append(address)
        pytest.fail(message)

    monkeypatch.setattr(socket.socket, 'connect', guarded)
    monkeypatch.setattr(socket.socket, 'connect_ex', guarded_ex)
    return blocked
