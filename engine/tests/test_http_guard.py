"""Response notices and purge failures at the HTTP boundary."""
import logging

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from fastapi.testclient import TestClient

from engine.http_guard import HttpGuard
from engine.privacy import PRIVACY_NOTICE


@pytest.mark.parametrize('status', [200, 204, 503])
def test_route_notice_is_preserved_without_duplicates(status):
    app = FastAPI()
    app.add_middleware(HttpGuard)
    route_notice = 'This route has a more specific notice.'

    @app.get('/notice')
    def notice():
        headers = {'X-Batatis-Notice': route_notice}
        if status == 204:
            return Response(status_code=status, headers=headers)
        return JSONResponse({'detail': 'route result'}, status_code=status, headers=headers)

    response = TestClient(app).get('/notice')
    assert response.status_code == status
    assert response.headers.get_list('x-batatis-notice') == [route_notice]
    assert response.headers['x-robots-tag'] == 'noindex, nofollow'
    if status == 204:
        assert response.content == b''
    else:
        assert response.json()['meta']['notice'] == PRIVACY_NOTICE


def test_default_notice_is_added_when_the_route_has_none():
    app = FastAPI()
    app.add_middleware(HttpGuard)
    response = TestClient(app).get('/missing')
    assert response.status_code == 404
    assert response.headers.get_list('x-batatis-notice') == [PRIVACY_NOTICE]
    assert response.json()['meta']['notice'] == PRIVACY_NOTICE


def test_failed_purge_refuses_the_request_without_leaking_exception_text(caplog):
    app = FastAPI()
    called = []

    def broken_sweep():
        raise RuntimeError('postgresql://private-user:private-password@private-host/cases')

    app.add_middleware(HttpGuard, sweep=broken_sweep)

    @app.get('/case')
    def case():
        called.append(True)
        return {'title': 'sensitive case'}

    with caplog.at_level(logging.WARNING, logger='engine.access'):
        response = TestClient(app).get('/case')
    assert response.status_code == 503
    assert response.json() == {'detail': 'case purge failed', 'meta': {'notice': PRIVACY_NOTICE}}
    assert response.headers['x-batatis-notice'] == PRIVACY_NOTICE
    assert response.headers['x-robots-tag'] == 'noindex, nofollow'
    assert called == []
    assert 'case purge failed: RuntimeError' in caplog.text
    assert 'private-' not in response.text + caplog.text
