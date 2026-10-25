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


def source_groups(records):
    """Keep every shared default-input original in one evaluation split."""
    parents = list(range(len(records)))

    def root(number):
        while parents[number] != number:
            parents[number] = parents[parents[number]]
            number = parents[number]
        return number

    owners = {}
    for number, record in enumerate(records):
        attachments = record["attachments"]
        has_non_outcome = any(a.get("role") != "outcome_reference" for a in attachments)
        for attachment in attachments:
            default = attachment.get("included_in_default_input",
                                     attachment.get("role") != "outcome_reference" or not has_non_outcome)
            if not default:
                continue
            value = attachment["sha256"]
            if value in owners:
                parents[root(number)] = root(owners[value])
            else:
                owners[value] = number
    members = {}
    for number, record in enumerate(records):
        members.setdefault(root(number), []).append(record["id"])
    identifiers = {group: hashlib.sha256("|".join(sorted(ids)).encode()).hexdigest()[:16]
                   for group, ids in members.items()}
    return {record["id"]: identifiers[root(number)] for number, record in enumerate(records)}


def check_file(path, expected):
    if not re.fullmatch(r"[0-9a-f]{64}", expected["sha256"]):
        raise ValueError("invalid SHA-256")
    if "bytes" in expected and path.stat().st_size != expected["bytes"]:
        raise ValueError(f"size mismatch: {path.name}")
    if digest(path) != expected["sha256"]:
        raise ValueError(f"SHA-256 mismatch: {path.name}")
