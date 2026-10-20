"""SQLite schema. One file, rebuilt from scratch on every build (idempotent)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .sources import BUILD_DIR

DB_PATH = BUILD_DIR / "codedb.sqlite"

SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE docs (doc TEXT PRIMARY KEY, label TEXT, kind TEXT, citable INTEGER, pdf TEXT, text_jsonl TEXT, sha256 TEXT);

-- every section/subsection/article/sentence/clause/subclause of a code
CREATE TABLE provisions (
  doc TEXT, division TEXT, id TEXT, level TEXT,
  part INTEGER, section TEXT, subsection TEXT, article TEXT,
  sentence INTEGER, clause TEXT, subclause TEXT, parent_id TEXT,
  article_title TEXT, title TEXT,
  text TEXT, text_raw TEXT, clauses TEXT,           -- clauses: JSON list of clause letters (sentences)
  pdf_page INTEGER, pdf_page_end INTEGER, volume INTEGER, sort_key TEXT,
  PRIMARY KEY (doc, division, id));
CREATE INDEX provisions_by_id ON provisions(id);
CREATE INDEX provisions_by_parent ON provisions(doc, division, parent_id);

CREATE TABLE notes (doc TEXT, division TEXT, note_id TEXT, title TEXT, text TEXT, text_raw TEXT,
  pdf_page INTEGER, pdf_page_end INTEGER, volume INTEGER, PRIMARY KEY (doc, division, note_id));
-- note <-> provision links; source = 'note_id' (the note's own id names the provision)
-- or 'see_reference' (the provision text says "(See Note A-...)")
CREATE TABLE note_links (doc TEXT, division TEXT, note_id TEXT, provision_id TEXT, source TEXT);
CREATE INDEX note_links_by_prov ON note_links(doc, division, provision_id);

CREATE TABLE code_tables (doc TEXT, division TEXT, table_id TEXT, pdf_page INTEGER, PRIMARY KEY (doc, division, table_id));

-- objectives (OS, OS1, OS1.1 ...) and functional statements (F01 ...) from Division A
CREATE TABLE definitions (doc TEXT, code TEXT, kind TEXT, title TEXT, text TEXT, parent TEXT, pdf_page INTEGER,
  PRIMARY KEY (doc, code));

-- one row per bracket in the Div B attribution tables
CREATE TABLE attributions (doc TEXT, table_id TEXT, provision_id TEXT, article_id TEXT, sentence INTEGER,
  clauses TEXT, seq INTEGER, bracket TEXT, fs TEXT, objectives TEXT, application_note TEXT, pdf_page INTEGER);
CREATE INDEX attributions_by_prov ON attributions(doc, provision_id);
CREATE INDEX attributions_by_article ON attributions(doc, article_id);

-- per Div B sentence/clause: direct | clause_level | none ; root = provision whose attribution applies (heuristic)
CREATE TABLE attribution_status (doc TEXT, provision_id TEXT, status TEXT, root_provision TEXT, root_method TEXT,
  PRIMARY KEY (doc, provision_id));

-- intent supplement entries (national 2020 code), one row per objective block
CREATE TABLE intents (source TEXT, code_doc TEXT, provision_id TEXT, block_seq INTEGER, objective TEXT,
  brackets TEXT, attribution_notes TEXT, intents TEXT, pdf_page INTEGER, pdf_page_end INTEGER);
CREATE INDEX intents_by_prov ON intents(code_doc, provision_id);
-- per intent entry: comparison against the Alberta Edition
CREATE TABLE intent_comparison (source TEXT, code_doc TEXT, provision_id TEXT, ae_exists INTEGER,
  status TEXT, only_in_intent TEXT, only_in_ae TEXT, PRIMARY KEY (source, provision_id));

CREATE VIRTUAL TABLE provisions_fts USING fts5(doc UNINDEXED, division UNINDEXED, id UNINDEXED, title, text,
  tokenize = 'porter unicode61');
CREATE VIRTUAL TABLE notes_fts USING fts5(doc UNINDEXED, division UNINDEXED, note_id UNINDEXED, title, text,
  tokenize = 'porter unicode61');
"""


def create(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    if tmp.exists():
        tmp.unlink()
    con = sqlite3.connect(tmp)
    con.executescript(SCHEMA)
    return con


def finalize(con: sqlite3.Connection, path: Path = DB_PATH):
    con.commit()
    con.close()
    path.with_suffix(".tmp").replace(path)


def connect(path: Path | None = None) -> sqlite3.Connection:
    p = Path(path) if path else DB_PATH
    if not p.exists():
        raise FileNotFoundError(f"{p} not built. Run: .venv/bin/python -m codedb build")
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con
