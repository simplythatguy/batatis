"""Server .env parsing acceptance without reading any real .env or starting a server."""
import os

import uvicorn


def test_uvicorn_parses_synthetic_configuration_without_executing_shell_or_overriding_process(tmp_path, monkeypatch):
    marker = tmp_path / 'must-not-exist'
    env = tmp_path / 'synthetic.env'
    # as_posix(): a double-quoted .env value is escape-processed, so a Windows path
    # containing \t would arrive with a tab in it. Forward slashes keep the value
    # literal on every platform and still prove it was never executed.
    shell_looking = f'$(touch {marker.as_posix()})'
    env.write_text(f'OPENROUTER_API_KEY="synthetic fixture"\nBATATIS_LIVE=1\n'
                   f'BATATIS_LIVE_ELEPHANT=1\nUNEXECUTED="{shell_looking}"\n')
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    monkeypatch.delenv('BATATIS_LIVE_ELEPHANT', raising=False)
    monkeypatch.delenv('UNEXECUTED', raising=False)
    monkeypatch.setenv('BATATIS_LIVE', '0')
    # Config parses only; it does not import the application or bind a port.
    uvicorn.Config('engine.api:app', env_file=env)
    try:
        assert os.environ['OPENROUTER_API_KEY'] == 'synthetic fixture'
        assert os.environ['BATATIS_LIVE'] == '0' and os.environ['BATATIS_LIVE_ELEPHANT'] == '1'
        assert os.environ['UNEXECUTED'] == shell_looking and not marker.exists()
        assert not any(k.startswith('VITE_') and 'OPENROUTER' in k for k in os.environ)
    finally:
        for name in ('OPENROUTER_API_KEY', 'BATATIS_LIVE_ELEPHANT', 'UNEXECUTED'):
            os.environ.pop(name, None)
