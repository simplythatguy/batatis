"""J08/A10: mounted applicant/officer callers, disposable SQLite and no provider access.

Uses existing PLAYWRIGHT_MODULE/Chromium. Starts unique loopback ports and stops
both processes on exit. No package installation, shared data writes or captures.
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


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 3000))
        return 3000


def serve(directory):
    sys.path.insert(0, str(ROOT))
    from fastapi.testclient import TestClient
    from engine.api import create_app
    from engine.models import Jurisdiction
    from engine.store import CaseStore
    from engine.tests.case_builder_fixtures import complete_case, fact, store_with_synthetic_files
    from engine.tests.test_accounts import onboard, signup
    import uvicorn

    connect = socket.socket.connect

    def local_connect(self, address):
        if isinstance(address, tuple) and address[0] not in ('127.0.0.1', 'localhost', '::1'):
            raise RuntimeError('External network disabled in review continuity regressions')
        return connect(self, address)

    socket.socket.connect = local_connect
    store = CaseStore(directory / 'cases.sqlite')
    app = create_app(store=store)
    people = {}
    for name, role, authority in [('applicant', 'applicant', 'edmonton'), ('reviewer', 'reviewer', 'edmonton'),
                                   ('second', 'reviewer', 'edmonton'), ('foreign', 'reviewer', 'calgary')]:
        with TestClient(app, base_url='http://localhost') as client:
            assert signup(client, f'continuity-{name}@example.test', f'Synthetic {name}').status_code == 201
            people[name] = {'user': onboard(client, role, authority), 'cookie': client.cookies.get('batatis_session')}
    ids = []
    for index in range(8):
        case = complete_case()
        case.owner_id, case.authority = people['applicant']['user']['id'], 'edmonton'
        case.jurisdiction = Jurisdiction(id='edmonton', name='Edmonton')
        case.title = f'SYNTHETIC continuity application {index}'
        values = {entry.field: entry.value for entry in case.facts}
        case.facts += [fact('date', values['application_date']), fact('municipalAddress', values['civic_address'])]
        case.facts += [fact('process.' + key, values[key]) for key in (
            'rationale', 'risk_assessment', 'mitigating_measures', 'assumptions_and_limits',
            'maintenance_operation', 'qualifications')]
        case.facts += [fact('project.description', 'SYNTHETIC continuity proposal.'),
                       fact('legalDescription', 'REVISION A — synthetic saved lot')]
        ids.append(store_with_synthetic_files(store, case).id)
    (directory / 'fixtures.json').write_text(json.dumps({'ids': ids, **people}))
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
    raise RuntimeError('Local regression server did not start')


if len(sys.argv) > 1 and sys.argv[1] == '--serve':
    serve(Path(sys.argv[2]))
else:
    env = {k: os.environ[k] for k in ('PATH', 'HOME', 'LANG', 'CHROME_PATH', 'PLAYWRIGHT_MODULE') if k in os.environ}
    env.update(BATATIS_LIVE='0', PYTHONDONTWRITEBYTECODE='1', BATATIS_AUTH_RATE_LIMIT='100',
               BATATIS_REVIEWER_CODES='{"edmonton":"officer-secret","calgary":"calgary-secret"}',
               BATATIS_CODEDB=str(ROOT / 'codedb/build/codedb.sqlite'))
    with tempfile.TemporaryDirectory(prefix='batatis-review-continuity-') as temporary:
        directory, processes = Path(temporary), []
        try:
            with (directory / 'engine.log').open('w') as log:
                server = subprocess.Popen([sys.executable, __file__, '--serve', temporary], env=env,
                                          stdout=log, stderr=subprocess.STDOUT)
                processes.append(server)
            for _ in range(150):
                if (directory / 'port').exists():
                    break
                if server.poll() is not None:
                    raise RuntimeError((directory / 'engine.log').read_text())
                time.sleep(.1)
            base = 'http://127.0.0.1:' + (directory / 'port').read_text()
            wait_ready(base + '/openapi.json', server, directory / 'engine.log')
            web = f'http://127.0.0.1:{port()}'
            with (directory / 'web.log').open('w') as log:
                frontend = subprocess.Popen(['node', str(WEB / 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1',
                    '--port', web.rsplit(':', 1)[1], '--strictPort', '--configLoader', 'runner'],
                    cwd=WEB, env=env, stdout=log, stderr=subprocess.STDOUT)
                processes.append(frontend)
            wait_ready(web + '/tests/check.html', frontend, directory / 'web.log')
            env.update(SYNC_TEST_BASE=base, SYNC_WEB_BASE=web, CONTINUITY_FIXTURES=str(directory / 'fixtures.json'))
            result = subprocess.run(['node', 'tests/review-continuity.integration.mjs'], cwd=WEB, env=env, timeout=180)
            sys.exit(result.returncode)
        finally:
            for process in reversed(processes):
                process.terminate()
                process.wait(timeout=10)
