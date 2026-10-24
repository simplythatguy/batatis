"""Disposable local engine + Vite + real mounted evidence wizard. No credentials/providers.

Run with the engine-ready Python environment. PLAYWRIGHT_MODULE can point to an existing
playwright-core entrypoint when it is installed outside this checkout; no installs occur.
"""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

from reportlab.pdfgen import canvas

WEB = Path(__file__).resolve().parents[1]


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


env = {key: os.environ[key] for key in ('PATH', 'HOME', 'LANG', 'BATATIS_CODEDB', 'CHROME_PATH', 'PLAYWRIGHT_MODULE') if key in os.environ}
env.update(BATATIS_LIVE='0', PYTHONDONTWRITEBYTECODE='1')
with tempfile.TemporaryDirectory(prefix='batatis-evidence-files-') as tmp:
    directory = Path(tmp)
    for revision in ('A', 'B'):
        pdf = canvas.Canvas(str(directory / f'synthetic-{revision}.pdf'))
        pdf.drawString(72, 720, f'SYNTHETIC attachment fixture {revision}. No professional finding.')
        pdf.save()
    env['EVIDENCE_PDF_DIR'] = tmp
    processes = []
    try:
        engine_log = directory / 'engine.log'
        with engine_log.open('w') as log:
            engine = subprocess.Popen([sys.executable, str(WEB / 'scripts/test-sync.py'), '--serve', tmp], cwd=WEB, env=env, stdout=log, stderr=subprocess.STDOUT)
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
        env.update(SYNC_TEST_BASE=base, SYNC_WEB_BASE=web, VITE_ENGINE_URL=base)
        vite_log = directory / 'vite.log'
        with vite_log.open('w') as log:
            vite = subprocess.Popen(['node', 'node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', str(port), '--strictPort'], cwd=WEB, env=env, stdout=log, stderr=subprocess.STDOUT)
        processes.append(vite)
        wait(web + '/tests/evidence-files.html', vite, vite_log)
        result = subprocess.run(['node', 'tests/evidence-files.integration.mjs'], cwd=WEB, env=env, timeout=120)
        sys.exit(result.returncode)
    finally:
        for process in reversed(processes):
            process.terminate()
            process.wait(timeout=10)
