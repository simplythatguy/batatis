#!/usr/bin/env python3
"""Check cited-provisions.txt against the repo code database.

Reads provision ids from cited-provisions.txt (one per line) and looks each
one up through engine.codes.Codes.

Exit codes:
  0  every id is present; prints "N/N present (presence only)"
  1  the database was read and at least one id is MISSING
  2  SKIPPED: the database file is absent, or the loader failed to import
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


def skipped(message: str) -> int:
    print("SKIPPED")
    print(message)
    return 2


def report(codes, pid: str, ambiguous: type[Exception]) -> bool:
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
            return False
        for row in hits:
            print(f"FOUND {pid} Div {row['division']} p.{row.get('pdf_page')}")
        return True
    if not row:
        print(f"MISSING {pid}")
        return False
    print(f"FOUND {pid} Div {row['division']} p.{row.get('pdf_page')}")
    return True


def main() -> int:
    path = db_path()
    if not path.is_file():
        return skipped("code database not found")
    sys.path.insert(0, str(REPO))
    try:
        from codedb import AmbiguousProvisionError
        from engine.codes import CodeDbMissing, Codes
    except Exception as exc:
        return skipped(f"{type(exc).__name__}: {exc}")
    try:
        codes = Codes(path)
    except CodeDbMissing as exc:
        return skipped(str(exc))
    ids = provision_ids()
    if not ids:
        print("MISSING cited-provisions.txt has no ids")
        return 1
    found = sum(1 for pid in ids if report(codes, pid, AmbiguousProvisionError))
    if found != len(ids):
        return 1
    print(f"{found}/{len(ids)} present (presence only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
