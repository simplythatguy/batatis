"""Configured prerequisites must run or fail explicitly instead of silently skipping."""
import pytest

from engine.tests import _db_skip


@pytest.mark.parametrize('configured', [False, True])
@pytest.mark.parametrize('repo_exists', [False, True])
def test_available_database_satisfies_prerequisite(tmp_path, monkeypatch, configured, repo_exists):
    repo_db = tmp_path / 'repo.sqlite'
    monkeypatch.setattr(_db_skip, 'REPO_DB', repo_db)
    monkeypatch.delenv('BATATIS_CODEDB', raising=False)
    if repo_exists:
        repo_db.touch()
    if configured:
        custom_db = tmp_path / 'configured.sqlite'
        custom_db.touch()
        monkeypatch.setenv('BATATIS_CODEDB', str(custom_db))
    if not configured and not repo_exists:
        with pytest.raises(pytest.skip.Exception, match='code database not built'):
            _db_skip.require_repo_db()
    else:
        _db_skip.require_repo_db()


@pytest.mark.parametrize('repo_exists', [False, True])
def test_missing_configured_database_fails_even_if_repo_database_exists(tmp_path, monkeypatch, repo_exists):
    repo_db = tmp_path / 'repo.sqlite'
    if repo_exists:
        repo_db.touch()
    monkeypatch.setattr(_db_skip, 'REPO_DB', repo_db)
    monkeypatch.setenv('BATATIS_CODEDB', str(tmp_path / 'missing.sqlite'))
    with pytest.raises(pytest.fail.Exception, match='BATATIS_CODEDB is set but the file is missing'):
        _db_skip.require_repo_db()
