"""Retired voice routes cannot open a transport; typed help still authenticates."""
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.store import CaseStore
from engine.tests.test_voice_context import synthetic_codes


def test_voice_endpoints_are_removed_and_typed_help_keeps_its_authentication(tmp_path):
    app = create_app(store=CaseStore(tmp_path / 'cases.sqlite'),
                     codes=synthetic_codes(tmp_path / 'codes.sqlite'))
    with TestClient(app) as client:
        assert client.get('/voice/session').status_code == 404
        assert client.get('/api/voice/session').status_code == 404
        assert not any('voice' in getattr(route, 'path', '') for route in app.routes)
        assert client.post('/assist', json={'screen': 'app', 'question': 'Explain this field.'}).status_code == 401
