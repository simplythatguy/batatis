"""J01/J11: mounted applicant submission against an isolated, offline SQLite engine.

Run with the repository's Python environment. PLAYWRIGHT_MODULE optionally names
an existing playwright-core module; this runner never installs dependencies.
Pass --isolation for the cross-application/account submit regressions (J11).
Run only after coordinating exclusive localhost ports 3000 (web) and 8000 (engine).
Both local servers and all synthetic cases are removed on exit.
"""
import json
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


def require_free_ports():
    for number in (3000, 8000):
        listener = subprocess.run(['lsof', '-nP', f'-iTCP:{number}', '-sTCP:LISTEN'], capture_output=True, text=True)
        if listener.stdout:
            raise RuntimeError(f'Port {number} is occupied. Wait for its owner and coordinate before retrying.\n{listener.stdout}')


def serve(directory):
    sys.path.insert(0, str(ROOT))
    from fastapi.testclient import TestClient
    from engine.api import create_app
    from engine.models import Jurisdiction
    from engine.store import CaseStore
    from engine.tests.case_builder_fixtures import complete_case, fact, store_with_synthetic_files
    from engine.tests.test_accounts import onboard, signup
    import uvicorn

    original_connect = socket.socket.connect

    def local_connect(self, address):
        if isinstance(address, tuple) and address[0] not in ('127.0.0.1', 'localhost', '::1'):
            raise RuntimeError('External network disabled in submit regressions')
        return original_connect(self, address)

    socket.socket.connect = local_connect
    store = CaseStore(directory / 'cases.sqlite')
    app = create_app(store=store)
    with TestClient(app, base_url='http://localhost') as client:
        assert signup(client, 'submit@example.test', 'Synthetic applicant').status_code == 201
        user = onboard(client)
        ids = []
        for index in range(50):
            case = complete_case()
            case.owner_id, case.authority = user['id'], 'edmonton'
            case.jurisdiction = Jurisdiction(id='edmonton', name='Edmonton')
            case.title, case.status = f'SYNTHETIC submit regression {index}', 'returned'
            if index == 15:
                case.status = 'draft'
            values = {entry.field: entry.value for entry in case.facts}
            # The public UI's field names, alongside the fixture's engine/export names.
            case.facts += [fact('date', values['application_date']), fact('municipalAddress', values['civic_address'])]
            case.facts += [fact('process.' + key, values[key]) for key in (
                'rationale', 'risk_assessment', 'mitigating_measures', 'assumptions_and_limits',
                'maintenance_operation', 'qualifications')]
            case.facts += [fact('project.description', 'SYNTHETIC applicant proposal.'),
                           fact('legalDescription', 'REVISION B — synthetic saved lot')]
            ids.append(store_with_synthetic_files(store, case).id)
        # Private test session, kept only in the disposable directory; never printed.
        (directory / 'fixtures.json').write_text(json.dumps({
            'ids': ids, 'cookie': client.cookies.get('batatis_session'),
        }))
    with TestClient(app, base_url='http://localhost') as replacement:
        assert signup(replacement, 'submit-replacement@example.test', 'Synthetic replacement').status_code == 201
        onboard(replacement)
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('127.0.0.1', 8000))
    sock.listen(128)
    (directory / 'port').write_text(str(sock.getsockname()[1]))
    uvicorn.Server(uvicorn.Config(app, log_level='warning', access_log=False)).run(sockets=[sock])


def wait_ready(url, process, log):
    for _ in range(150):
        if process.poll() is not None:
            raise RuntimeError(log.read_text())
        try:
            urllib.request.urlopen(url, timeout=.3).close()
            return
        except OSError:
            time.sleep(.1)
    raise RuntimeError(f'Local test server did not start: {url}')


if len(sys.argv) > 1 and sys.argv[1] == '--serve':
    serve(Path(sys.argv[2]))
else:
    env = {k: os.environ[k] for k in ('PATH', 'HOME', 'LANG', 'CHROME_PATH', 'PLAYWRIGHT_MODULE') if k in os.environ}
    env.update(BATATIS_LIVE='0', PYTHONDONTWRITEBYTECODE='1', BATATIS_AUTH_RATE_LIMIT='100',
               BATATIS_CODEDB=str(ROOT / 'codedb/build/codedb.sqlite'))
    with tempfile.TemporaryDirectory(prefix='batatis-submit-') as temporary:
        directory = Path(temporary)
        processes = []
        try:
            require_free_ports()
            with (directory / 'engine.log').open('w') as log:
                server = subprocess.Popen([sys.executable, __file__, '--serve', temporary], env=env,
                                          stdout=log, stderr=subprocess.STDOUT)
                processes.append(server)
            for _ in range(100):
                if (directory / 'port').exists():
                    break
                if server.poll() is not None:
                    raise RuntimeError((directory / 'engine.log').read_text())
                time.sleep(.1)
            base = 'http://localhost:8000'
            wait_ready(base + '/openapi.json', server, directory / 'engine.log')
            web = 'http://localhost:3000'
            vite = WEB / 'node_modules/vite/bin/vite.js'
            with (directory / 'web.log').open('w') as log:
                frontend = subprocess.Popen(['node', str(vite), '--host', '127.0.0.1', '--port', web.rsplit(':', 1)[1],
                                             '--strictPort', '--configLoader', 'runner'], cwd=WEB, env=env,
                                            stdout=log, stderr=subprocess.STDOUT)
                processes.append(frontend)
            wait_ready(web + '/tests/check.html', frontend, directory / 'web.log')
            env.update(SYNC_TEST_BASE=base, SYNC_WEB_BASE=web, SUBMIT_FIXTURES=str(directory / 'fixtures.json'))
            suite = 'tests/submit-isolation.integration.mjs' if '--isolation' in sys.argv else 'tests/submit.integration.mjs'
            result = subprocess.run(['node', suite], cwd=WEB, env=env, timeout=150)
            sys.exit(result.returncode)
        finally:
            for process in reversed(processes):
                process.terminate()
                process.wait(timeout=10)
