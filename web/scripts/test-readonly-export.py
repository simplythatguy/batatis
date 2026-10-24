"""J09: real locked-case screens -> read-only completeness -> official PDF, offline.

Uses disposable SQLite and the fixed local ports 3000/8000. No dependencies are installed and
no shared reference data is modified. The parent owns PDF/browser visual review.
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

    original_connect = socket.socket.connect

    def local_connect(self, address):
        if isinstance(address, tuple) and address[0] not in ('127.0.0.1', 'localhost', '::1'):
            raise RuntimeError('External network disabled in read-only export regressions')
        return original_connect(self, address)

    socket.socket.connect = local_connect
    store = CaseStore(directory / 'cases.sqlite')
    app = create_app(store=store)
    with TestClient(app, base_url='http://localhost') as owner, TestClient(app, base_url='http://localhost') as officer:
        assert signup(owner, 'readonly-owner@example.test', 'SYNTHETIC applicant').status_code == 201
        user = onboard(owner)
        assert signup(officer, 'readonly-officer@example.test', 'SYNTHETIC officer').status_code == 201
        onboard(officer, 'reviewer', 'edmonton')
        ids = {}
        for status in ('accepted', 'submitted', 'in_review', 'returned', 'legacy-incomplete', 'professional-pending', 'professional-pending-draft'):
            case = complete_case()
            case.owner_id, case.authority = user['id'], 'edmonton'
            case.jurisdiction = Jurisdiction(id='edmonton', name='Edmonton')
            case.title = f'SYNTHETIC J09 {status}'
            case.facts.append(fact('project.description', 'SYNTHETIC applicant insulation alternative.'))
            if status.startswith('professional-pending'):
                case.facts = [f for f in case.facts if f.field not in {'professional.role', 'professional.registration_number'}]
                case.facts.append(fact('professional.role', 'not_engaged_yet'))
            case = store_with_synthetic_files(store, case)
            if status != 'professional-pending-draft':
                assert owner.post(f'/cases/{case.id}/submit', json={}).status_code == 200
            if status not in {'submitted', 'professional-pending', 'professional-pending-draft'}:
                assert officer.post(f'/review/{case.id}/claim', json={}).status_code == 200
            if status in {'accepted', 'legacy-incomplete'}:
                assert officer.post(f'/review/{case.id}/decision', json={'outcome': 'accept'}).status_code == 200
            if status == 'returned':
                assert officer.post(f'/review/{case.id}/decision', json={
                    'outcome': 'return', 'message': 'SYNTHETIC: correct the legal description before resubmitting.'}).status_code == 200
            if status == 'legacy-incomplete':
                # Simulate a record accepted before the current administrative gates.
                # Status alone must never waive the real PDF requirements.
                case = store.get(case.id)
                case.facts = [f for f in case.facts if f.field not in {'risk_assessment', 'process.risk_assessment'}]
                store.put(case, expected_version=case.version)
            ids[status] = case.id
        (directory / 'fixtures.json').write_text(json.dumps({
            'ids': ids, 'cookie': owner.cookies.get('batatis_session'),
        }))
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
               BATATIS_REVIEWER_CODES='{"edmonton":"officer-secret"}',
               BATATIS_CODEDB=str(ROOT / 'codedb/build/codedb.sqlite'))
    with tempfile.TemporaryDirectory(prefix='batatis-readonly-export-') as temporary:
        directory = Path(temporary)
        processes = []
        try:
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
            base = 'http://127.0.0.1:' + (directory / 'port').read_text()
            wait_ready(base + '/openapi.json', server, directory / 'engine.log')
            web = f'http://127.0.0.1:{port()}'
            vite = WEB / 'node_modules/vite/bin/vite.js'
            with (directory / 'web.log').open('w') as log:
                frontend = subprocess.Popen(['node', str(vite), '--host', '127.0.0.1', '--port', web.rsplit(':', 1)[1],
                                             '--strictPort', '--configLoader', 'runner'], cwd=WEB, env=env,
                                            stdout=log, stderr=subprocess.STDOUT)
                processes.append(frontend)
            wait_ready(web + '/tests/check.html', frontend, directory / 'web.log')
            env.update(SYNC_TEST_BASE=base, SYNC_WEB_BASE=web, READONLY_FIXTURES=str(directory / 'fixtures.json'))
            result = subprocess.run(['node', 'tests/readonly-export.integration.mjs'], cwd=WEB, env=env, timeout=150)
            sys.exit(result.returncode)
        finally:
            for process in reversed(processes):
                process.terminate()
                process.wait(timeout=10)
