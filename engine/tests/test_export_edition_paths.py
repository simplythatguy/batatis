from contextlib import closing
import json
import os
import sqlite3
from types import SimpleNamespace

import pytest

from engine.export.edition import EDITION_PLAIN, EDITION_PROVEN, edition_label


@pytest.mark.parametrize('name', ['code data', 'règles 中文', '100% build #2', *(['query?mode=rw'] if os.name != 'nt' else [])])
@pytest.mark.parametrize('label, expected', [('NBC(AE) 2023 p2', EDITION_PROVEN), ('NBC(AE) 2023 p1', EDITION_PLAIN)])
def test_printing_is_read_from_the_selected_database_in_uri_sensitive_paths(tmp_path, monkeypatch, name, label, expected):
    folder = tmp_path / name
    folder.mkdir()
    path = folder / 'code #100%.sqlite'
    with closing(sqlite3.connect(path)) as db:
        db.execute('CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)')
        db.execute("INSERT INTO meta VALUES ('stats', ?)", (json.dumps({'sources': {'NBC-AE': {'label': label}}}),))
        db.commit()
    monkeypatch.chdir(tmp_path)

    assert edition_label(SimpleNamespace(db_path=path.relative_to(tmp_path))) == expected
