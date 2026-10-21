"""Run web sync regressions against the real engine and a disposable SQLite store.

Use an engine-ready Python environment and set BATATIS_CODEDB to a built code DB.
No provider credentials are inherited. Optional --browser runs the CaseProvider
regressions too (requires Playwright and a running Vite server in SYNC_WEB_BASE).
"""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

WEB = Path(__file__).resolve().parents[1]
ROOT = WEB.parent

if len(sys.argv) > 1 and sys.argv[1] == '--serve':
    sys.path.insert(0, str(ROOT))
    from engine.api import create_app
    from engine.store import CaseStore
    import uvicorn

    # The test engine may only connect to loopback, even if future code adds I/O.
    original_connect = socket.socket.connect
    def local_connect(self, address):
        if isinstance(address, tuple) and address[0] not in ('127.0.0.1', 'localhost', '::1'):
            raise RuntimeError('External network disabled in sync regressions')
        return original_connect(self, address)
    socket.socket.connect = local_connect
    directory = Path(sys.argv[2])
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # SYNC_ENGINE_PORT pins the loopback port for runs that must stay on an assigned port.
    sock.bind(('127.0.0.1', int(os.environ.get('SYNC_ENGINE_PORT', '0'))))
    sock.listen(128)
    (directory / 'port').write_text(str(sock.getsockname()[1]))
    app = create_app(store=CaseStore(directory / 'cases.sqlite'))
    uvicorn.Server(uvicorn.Config(app, log_level='warning', access_log=False)).run(sockets=[sock])
    sys.exit(0)

env = {k: os.environ[k] for k in ('PATH', 'HOME', 'LANG', 'BATATIS_CODEDB', 'BATATIS_SCC_FORM', 'SYNC_WEB_BASE', 'CHROME_PATH', 'SYNC_ENGINE_PORT') if k in os.environ}
env.update(BATATIS_LIVE='0', PYTHONDONTWRITEBYTECODE='1')
with tempfile.TemporaryDirectory(prefix='batatis-web-sync-') as tmp:
    directory = Path(tmp)
    with (directory / 'server.log').open('w') as log:
        server = subprocess.Popen([sys.executable, __file__, '--serve', tmp], env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(100):
                if (directory / 'port').exists():
                    base = 'http://127.0.0.1:' + (directory / 'port').read_text()
                    try:
                        urllib.request.urlopen(base + '/openapi.json', timeout=.5).close()
                        break
                    except OSError:
                        pass
                if server.poll() is not None:
                    raise RuntimeError((directory / 'server.log').read_text())
                time.sleep(.1)
            else:
                raise RuntimeError('Local engine did not start')
            env['SYNC_TEST_BASE'] = base
            env['SYNC_TEST_DB'] = str(directory / 'cases.sqlite')
            result = subprocess.run(['node', '--experimental-strip-types', '--import', './scripts/register-ts.mjs', 'tests/sync.integration.mts'], cwd=WEB, env=env, timeout=120)
            if result.returncode == 0 and '--browser' in sys.argv:
                result = subprocess.run(['node', 'tests/provider.integration.mjs'], cwd=WEB, env=env, timeout=120)
            if result.returncode == 0 and '--repair' in sys.argv:
                result = subprocess.run(['node', '--experimental-strip-types', '--import', './scripts/register-ts.mjs', 'tests/repair.integration.mts'], cwd=WEB, env=env, timeout=120)
                if result.returncode == 0:
                    result = subprocess.run(['node', 'tests/repair.integration.mjs'], cwd=WEB, env=env, timeout=120)
                if result.returncode == 0:
                    result = subprocess.run(['node', 'tests/repair-r6.integration.mjs'], cwd=WEB, env=env, timeout=120)
                if result.returncode == 0:
                    result = subprocess.run(['node', '--experimental-strip-types', '--import', './scripts/register-ts.mjs', 'tests/contract-r7.integration.mts'], cwd=WEB, env=env, timeout=120)
                if result.returncode == 0:
                    result = subprocess.run(['node', 'tests/contract-r7.integration.mjs'], cwd=WEB, env=env, timeout=180)
                if result.returncode == 0:
                    result = subprocess.run(['node', '--experimental-strip-types', '--import', './scripts/register-ts.mjs', 'tests/evidence-r8.integration.mts'], cwd=WEB, env=env, timeout=120)
                if result.returncode == 0:
                    result = subprocess.run(['node', 'tests/evidence-r8.integration.mjs'], cwd=WEB, env=env, timeout=180)
            sys.exit(result.returncode)
        finally:
            server.terminate()
            server.wait(timeout=10)
