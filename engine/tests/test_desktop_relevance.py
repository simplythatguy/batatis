"""The Code Library uses desktop selection without opening hosted credentials."""
import pytest

from engine import relevance
from engine.desktop import bridge
from engine.tests.test_desktop_provider_routing import Host, bind_host


def test_relevance_uses_selected_desktop_screening_with_web_live_off(monkeypatch):
    class ScreenHost(Host):
        def call_host(self, op, args, timeout, *, request_id):
            reply = super().call_host(op, args, timeout, request_id=request_id)
            if op == 'provider.profile':
                reply['value']['screening'] = True
            return reply

    host = ScreenHost()
    bind_host(monkeypatch, host)
    monkeypatch.setenv('BATATIS_LIVE', '0')
    monkeypatch.delenv('BATATIS_PROVIDER', raising=False)
    judge = relevance.live_judge()
    assert judge.method == 'jev' and judge.model == 'jev-1.13.0'
    assert [op for op, _ in host.calls] == ['provider.profile']


@pytest.mark.parametrize('lost_bridge', [False, True])
def test_off_or_lost_desktop_cannot_open_ambient_relevance(monkeypatch, lost_bridge):
    from engine.identify.jevkit import keystore
    monkeypatch.setattr(bridge, 'ACTIVE', None if lost_bridge else Host(generation='off'))
    monkeypatch.setenv('BATATIS_DESKTOP_WORKSPACE', 'dev')
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('BATATIS_PROVIDER', 'fake')
    monkeypatch.setattr(keystore, 'resolve', lambda *args: pytest.fail('ambient credentials accessed'))
    with pytest.raises(relevance.RelevanceUnavailable):
        relevance.live_judge()
