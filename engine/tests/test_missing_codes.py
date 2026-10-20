"""A configured missing corpus must not silently select a different database."""
from fastapi.testclient import TestClient

from engine import codes
from engine.api import create_app
from engine.store import CaseStore


def test_configured_missing_database_returns_503_without_using_repo_fallback(tmp_path, monkeypatch):
    missing = tmp_path / 'configured-but-missing.sqlite'
    fallback = tmp_path / 'unrelated-repo.sqlite'
    fallback.touch()
    monkeypatch.setenv('BATATIS_CODEDB', str(missing))
    monkeypatch.setattr(codes, 'repo_codedb_candidates', lambda: (fallback,))
    client = TestClient(create_app(CaseStore(tmp_path / 'cases.sqlite')),
                        raise_server_exceptions=False)

    response = client.get('/code/search', params={'q': 'firestop'})

    assert response.status_code == 503
    assert response.json() == {'detail': 'code database not found'}
    assert str(tmp_path) not in response.text
