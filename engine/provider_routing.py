"""Composition seam for shared workflows. Hosted startup never imports a desktop runtime."""
from __future__ import annotations

import os
import sys

LOCAL_MODEL, LOCAL_EFFORT = 'gpt-6-luna', 'medium'


def local_active() -> bool:
    bridge = sys.modules.get('engine.desktop.bridge')
    return getattr(bridge, 'ACTIVE', None) is not None or os.environ.get('BATATIS_DESKTOP_WORKSPACE') in ('local', 'dev')


def local_profile(slot: str = 'workflow'):
    from .desktop.composition import profile
    return profile(slot)


def local_transport(*args, **kwargs):
    from .desktop.host_provider import host_transport
    return host_transport(*args, **kwargs)


def local_review_transport():
    from .desktop.composition import review_transport
    return review_transport()


def local_identify_transports(**kwargs):
    from .desktop.identify import transports
    return transports(**kwargs)
