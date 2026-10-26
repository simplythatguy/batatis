from contextlib import closing
import os
import sqlite3

import pytest

from codedb.store import connect


@pytest.mark.parametrize('name', ['code data', 'règles 中文', '100% build #2', *(['query?mode=rw'] if os.name != 'nt' else [])])
def test_readonly_database_paths_preserve_literal_filename(tmp_path, monkeypatch, name):
    folder = tmp_path / name
    folder.mkdir()
    path = folder / 'code #100%.sqlite'
    with closing(sqlite3.connect(path)) as db:
        db.execute('CREATE TABLE marker (value TEXT)')
        db.execute("INSERT INTO marker VALUES ('the selected database')")
        db.commit()
    monkeypatch.chdir(tmp_path)

    with closing(connect(path.relative_to(tmp_path))) as db:
        assert db.execute('SELECT value FROM marker').fetchone()['value'] == 'the selected database'
        with pytest.raises(sqlite3.OperationalError, match='readonly'):
            db.execute("INSERT INTO marker VALUES ('must not write')")
