#!/usr/bin/env python3
"""Check cited-provisions.txt against the repo code database.

Reads provision ids from cited-provisions.txt (one per line). When
codedb/build/codedb.sqlite or BATATIS_CODEDB is present, looks each id up
through engine.codes.Codes. When that database file is absent, prints
SKIPPED and does not invent FOUND or MISSING rows.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
LIST = HERE / "cited-provisions.txt"


def db_path() -> Path:
    env = os.environ.get("BATATIS_CODEDB")
    if env:
        return Path(env)
    return REPO / "codedb" / "build" / "codedb.sqlite"


def provision_ids() -> list[str]:
    return [
        line.strip()
        for line in LIST.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def report(codes, pid: str, ambiguous: type[Exception]) -> None:
    try:
        row = codes.provision(pid, division=None)
    except ambiguous:
        hits = []
        for division in ("A", "B", "C"):
            row = codes.provision(pid, division=division)
            if row:
                hits.append(row)
        if not hits:
            print(f"MISSING {pid}")
            return
        for row in hits:
            print(f"FOUND {pid} Div {row['division']} p.{row.get('pdf_page')}")
        return
    if not row:
        print(f"MISSING {pid}")
        return
    print(f"FOUND {pid} Div {row['division']} p.{row.get('pdf_page')}")


def main() -> int:
    path = db_path()
    if not path.is_file():
        print("SKIPPED")
        return 0
    sys.path.insert(0, str(REPO))
    try:
        from codedb import AmbiguousProvisionError
        from engine.codes import CodeDbMissing, Codes
    except Exception as exc:
        print(
            f"{type(exc).__name__}: code database loader could not be imported",
            file=sys.stderr,
        )
        print("SKIPPED")
        return 0
    try:
        codes = Codes(path)
    except CodeDbMissing:
        print("SKIPPED")
        return 0
    for pid in provision_ids():
        report(codes, pid, AmbiguousProvisionError)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
