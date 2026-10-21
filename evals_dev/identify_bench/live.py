"""Build the live run context: corpus, ledgers, OpenAI transport and the Jev client, with keys loaded from the .env.

Keys come from the git-ignored ``.env`` (this checkout or the main checkout of the repository) or the environment, are
set only in this process, and are never printed. ``SSL_CERT_FILE`` defaults to ``/etc/ssl/cert.pem`` because the
python.org Python on this Mac has no CA bundle. ``JEV_API_KEY`` is exposed to the vendored client as ``TYPESAFE_API_KEY``.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from evals_dev import envfile

from .ledger import Ledger
from .methods.base import RunContext
from .methods.jev import live_jev_ask
from .rows import RowStore
from .transports import OpenAIChat

HERE = Path(__file__).resolve().parent
LEDGER_DIR = HERE / 'ledger'
OPENAI_STOP_USD = '10.00'            # the user's decision: the benchmark may spend at most US$10.00 of OpenAI credit


def db_path() -> Path:
    from engine.codes import default_db
    return default_db()


def codedb_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def build_context(*, need_openai: bool, need_jev: bool, store: RowStore | None = None,
                  openai_stop: str = OPENAI_STOP_USD, env_file: str | None = None) -> tuple[RunContext, str]:
    envfile.load_env_file(env_file, names=envfile.KEY_NAMES)
    envfile.apply_defaults()
    from engine.identify.corpus import articles
    db = db_path()
    if not db.is_file():
        raise SystemExit('code database not found; build codedb or set BATATIS_CODEDB')
    arts = articles(db)
    if len(arts) != 2080:
        raise SystemExit(f'expected 2,080 Division B articles in the code database, found {len(arts)}')
    ctx = RunContext(arts=arts, store=store or RowStore(), db_path=db)
    if need_openai:
        if not os.environ.get('OPENAI_API_KEY'):
            raise SystemExit('OPENAI_API_KEY is not set (put it in the git-ignored .env)')
        ledger = Ledger(LEDGER_DIR / 'openai.jsonl', 'openai', openai_stop)
        ctx.openai = OpenAIChat(ledger)
    if need_jev:
        if not (os.environ.get('TYPESAFE_API_KEY') or os.environ.get('JEV_API_KEY')):
            from engine.identify.jevkit import keystore
            if not keystore.resolve('typesafe'):
                raise SystemExit('no Jev key: JEV_API_KEY in the .env, or the macOS keychain entry')
        ctx.jev_ledger = Ledger(LEDGER_DIR / 'jev.jsonl', 'jev', None)
        ctx.jev_ask = live_jev_ask
    return ctx, codedb_sha256(db)
