"""Shared metadata and integrity operations for the portable prompt corpus."""

import hashlib
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def child(root, relative):
    """Resolve only paths contained by the selected corpus directory."""
    relative = Path(relative)
    target = (root / relative).resolve()
    if relative.is_absolute() or not target.is_relative_to(root.resolve()):
        raise ValueError(f"path outside corpus directory: {relative}")
    return target


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def cases(base=BASE, numbers=None):
    index = json.loads((base / "index.json").read_text())
    requested = set(numbers or [])
    unknown = requested - {row["prompt"] for row in index}
    if unknown:
        raise ValueError(f"unknown prompt numbers: {sorted(unknown)}")
    for row in index:
        if requested and row["prompt"] not in requested:
            continue
        folder = child(base, row["folder"])
        source = json.loads((folder / "source.json").read_text())
        yield row, folder, source


def attachment_files(source, include_evaluation=True):
    for attachment in source["attachments"]:
        if not include_evaluation and not attachment["included_in_default_input"]:
            continue
        yield attachment, attachment, False
        if attachment.get("derived_text"):
            yield attachment["derived_text"], attachment, True


def check_file(path, expected):
    if not re.fullmatch(r"[0-9a-f]{64}", expected["sha256"]):
        raise ValueError("invalid SHA-256")
    if "bytes" in expected and path.stat().st_size != expected["bytes"]:
        raise ValueError(f"size mismatch: {path.name}")
    if digest(path) != expected["sha256"]:
        raise ValueError(f"SHA-256 mismatch: {path.name}")
