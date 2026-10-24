"""Mounted source inventory against an authenticated, disposable real HTTP engine.

Optional --engine-root reads another checkout's engine (never its database) to exercise
terminal statuses absent from this worker's older base. All writes stay in the temp directory.
"""
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from typing import get_args
import urllib.request

from reportlab.pdfgen import canvas

WEB = Path(__file__).resolve().parents[1]
ROOT = WEB.parent


def serve(directory, engine_root):
    sys.path.insert(0, str(engine_root))
    from fastapi.testclient import TestClient
    import uvicorn
    from engine.api import create_app
    from engine.account_models import ApplicationStatus
    from engine.store import CaseStore
    from engine.tests.test_accounts import signup, onboard

    os.environ['BATATIS_REVIEWER_CODES'] = json.dumps({'edmonton': 'officer-secret', 'calgary': 'calgary-secret'})
    os.environ['BATATIS_AUTH_RATE_LIMIT'] = '1000'
    store = CaseStore(directory / 'cases.sqlite')
    app = create_app(store=store)
    users = {}
    with ExitStack() as stack:
        clients = {}
        for name, role, authority in [('applicant', 'applicant', 'edmonton'), ('officer', 'reviewer', 'edmonton'),
                                     ('other', 'applicant', 'edmonton'), ('foreign', 'reviewer', 'calgary')]:
            client = stack.enter_context(TestClient(app, base_url='http://localhost'))
            assert signup(client, name + '@synthetic.test', 'SYNTHETIC ' + name).status_code == 201
            user = onboard(client, role, authority)
            clients[name] = client
            users[name] = {'user': user, 'cookie': client.cookies.get('batatis_session')}

        def make(status, tag):
            client = clients['applicant']
            response = client.post('/cases', json={'title': 'SYNTHETIC retained sources ' + tag, 'authority': 'edmonton'})
            assert response.status_code == 201, response.text
            case = response.json()
            files = []
            for revision in ('A', 'B'):
                name = f'SYNTHETIC {tag} source {revision}.pdf'
                response = client.post(f'/cases/{case["id"]}/files', files={'file': (name, (directory / f'synthetic-{revision}.pdf').read_bytes(), 'application/pdf')})
                assert response.status_code == 201, response.text
                files.append(response.json())
            body = {'operation': 'create', 'evidence_id': 'synthetic_report', 'expected_version': case['version'],
                    'title': 'SYNTHETIC source listing', 'description': 'SYNTHETIC storage fixture; no professional finding.',
                    'evidence_type': 'evaluation', 'responsible_party': 'SYNTHETIC fixture author', 'file_ref': files[0]['id']}
            response = client.post(f'/cases/{case["id"]}/evidence', json=body)
            assert response.status_code == 200, response.text
            response = client.post(f'/cases/{case["id"]}/evidence', json={**body, 'operation': 'update',
                'expected_version': response.json()['case_version'], 'file_ref': files[1]['id']})
            assert response.status_code == 200, response.text
            current = store.get(case['id'])
            current.status = status
            store.put(current, expected_version=current.version)
            return {'id': case['id'], 'status': status, 'files': [{key: file[key] for key in ('id', 'name')} for file in files]}

        statuses = list(get_args(ApplicationStatus))
        cases = {status: make(status, status) for status in statuses}
        cases['second'] = make('accepted', 'second')
        cases['disappearing'] = make('accepted', 'disappearing')
        response = clients['applicant'].post('/cases', json={'title': 'SYNTHETIC empty source inventory'})
        assert response.status_code == 201
        cases['empty'] = {'id': response.json()['id']}
        cases['expired'] = make('accepted', 'expired')
        current = store.get(cases['expired']['id'])
        current.created_at = '2020-01-01T00:00:00+00:00'
        store.put(current, expected_version=current.version)
        (directory / 'fixtures.json').write_text(json.dumps({'users': users, 'cases': cases, 'engine_root': str(engine_root)}))

    original_connect = socket.socket.connect
    def local_connect(self, address):
        if isinstance(address, tuple) and address[0] not in ('127.0.0.1', 'localhost', '::1'):
            raise RuntimeError('External network disabled in retained-source tests')
        return original_connect(self, address)
    socket.socket.connect = local_connect
    listener = socket.socket()
    listener.bind(('127.0.0.1', 8000))
    listener.listen(128)
    (directory / 'port').write_text(str(listener.getsockname()[1]))
    uvicorn.Server(uvicorn.Config(app, log_level='warning', access_log=False)).run(sockets=[listener])


def wait(url, process, log):
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError(log.read_text())
        try:
            urllib.request.urlopen(url, timeout=.5).close()
            return
        except OSError:
            time.sleep(.1)
    raise RuntimeError('Local test service did not start: ' + log.read_text())


if len(sys.argv) > 1 and sys.argv[1] == '--serve':
    serve(Path(sys.argv[2]), Path(sys.argv[3]))
    sys.exit(0)

parser = argparse.ArgumentParser()
parser.add_argument('--engine-root', type=Path, default=ROOT)
parser.add_argument('--require-refused', action='store_true')
parser.add_argument('--reproduce', action='store_true')
args = parser.parse_args()
env = {key: os.environ[key] for key in ('PATH', 'HOME', 'LANG', 'BATATIS_CODEDB', 'CHROME_PATH', 'PLAYWRIGHT_MODULE') if key in os.environ}
env.update(BATATIS_LIVE='0', PYTHONDONTWRITEBYTECODE='1')
with tempfile.TemporaryDirectory(prefix='batatis-retained-sources-') as tmp:
    directory = Path(tmp)
    for revision in ('A', 'B'):
        pdf = canvas.Canvas(str(directory / f'synthetic-{revision}.pdf'))
        pdf.drawString(72, 720, f'SYNTHETIC retained source {revision}. No professional finding.')
        pdf.save()
    processes = []
    try:
        engine_log = directory / 'engine.log'
        with engine_log.open('w') as log:
            engine = subprocess.Popen([sys.executable, __file__, '--serve', tmp, str(args.engine_root)], cwd=WEB, env=env, stdout=log, stderr=subprocess.STDOUT)
        processes.append(engine)
        for _ in range(100):
            if (directory / 'port').exists():
                break
            if engine.poll() is not None:
                raise RuntimeError(engine_log.read_text())
            time.sleep(.1)
        base = 'http://127.0.0.1:' + (directory / 'port').read_text()
        wait(base + '/openapi.json', engine, engine_log)
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 3000))
            port = 3000
        web = f'http://127.0.0.1:{port}'
        env.update(SYNC_TEST_BASE=base, SYNC_WEB_BASE=web, VITE_ENGINE_URL=base,
                   RETAINED_FIXTURES=str(directory / 'fixtures.json'), EVIDENCE_PDF_DIR=tmp,
                   RETAINED_REQUIRE_REFUSED=str(int(args.require_refused)), RETAINED_REPRODUCE=str(int(args.reproduce)))
        vite_log = directory / 'vite.log'
        with vite_log.open('w') as log:
            vite = subprocess.Popen(['node', 'node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', str(port), '--strictPort'], cwd=WEB, env=env, stdout=log, stderr=subprocess.STDOUT)
        processes.append(vite)
        wait(web + '/tests/retained-sources.html', vite, vite_log)
        result = subprocess.run(['node', 'tests/retained-sources.integration.mjs'], cwd=WEB, env=env, timeout=180)
        sys.exit(result.returncode)
    finally:
        for process in reversed(processes):
            process.terminate()
            process.wait(timeout=10)
