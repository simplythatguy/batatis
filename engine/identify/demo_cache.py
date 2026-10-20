"""Optional cached identify payloads for demo descriptions.

The cache file is added when quotes have been taken from codedb. Until then, nothing matches.
"""
from __future__ import annotations


def match_demo(prose: str) -> dict | None:
    del prose
    return None
