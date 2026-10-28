#!/usr/bin/env python3
"""Delete every Batatis account (users, sessions, sign-ins, access-code installs) from one database.

Reads the same settings the engine does: BATATIS_STORE=postgres with DATABASE_URL for the hosted site, or a
file store (BATATIS_CASES, default .data/cases.sqlite). It prints which database it will change and how many
rows it holds, then does nothing unless --yes is given. Applications are not deleted; with no account to
open them they simply stay unreachable.

  DATABASE_URL=... BATATIS_STORE=postgres python scripts/delete_all_accounts.py          # look first
  DATABASE_URL=... BATATIS_STORE=postgres python scripts/delete_all_accounts.py --yes    # delete
"""
from __future__ import annotations

import os
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.store import open_store  # noqa: E402


def target() -> str:
    if (os.environ.get('BATATIS_STORE') or '').strip().lower() == 'postgres':
        url = urllib.parse.urlparse(os.environ.get('DATABASE_URL') or '')
        return f'Postgres {url.hostname or "?"}{url.path}'
    return f'file store {os.environ.get("BATATIS_CASES") or ".data/cases.sqlite"}'


def main() -> int:
    yes = '--yes' in sys.argv[1:]
    if (os.environ.get('BATATIS_STORE') or '').strip().lower() == 'postgres' and not os.environ.get('DATABASE_URL'):
        print('BATATIS_STORE=postgres needs DATABASE_URL.', file=sys.stderr)
        return 2
    store = open_store()
    print(f'Database: {target()}')
    if not yes:
        with store.account_db() as db:
            count = db.execute('SELECT COUNT(*) FROM account_users').fetchone()[0]
        print(f'{count} account(s). Nothing was deleted. Run again with --yes to delete them all.')
        return 0
    print('Deleted:', store.delete_all_accounts())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
