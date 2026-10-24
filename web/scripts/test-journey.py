"""Run the offline journey regressions with disposable local stores and servers.

Use the engine-ready Python interpreter. PLAYWRIGHT_MODULE (or an installed
playwright-core) supplies the existing browser dependency; nothing is installed.
Optional positional suite names select one group. No provider credentials pass
to child processes. These regressions supplement the full UI walkthrough.
"""
import argparse
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
STANDALONE = {
    'submit': 'test-submit.py',
    'isolation': 'test-submit.py',
    'aliases': 'test-sync.py',
    'professional': 'test-professional-handoff.py',
    'files': 'test-evidence-files.py',
    'refresh': 'test-refresh.py',
    'continuity': 'test-review-continuity.py',
    'readonly': 'test-readonly-export.py',
    'questions': 'test-open-questions.py',
    'refusal': 'test-refusal.py',
    'sources': 'test-retained-sources.py',
}
SHARED = {
    'sync': 'tests/sync.integration.mts',
    'communication': 'tests/communication-sync.integration.mts',
    'conversation': 'tests/conversation.integration.mjs',
    'requested': 'tests/requested-items.integration.mjs',
    'evidence': 'tests/evidence-r8.integration.mts',
    'return-draft': 'tests/return-draft.integration.mjs',
}


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


def run_shared(names, env):
    with tempfile.TemporaryDirectory(prefix='batatis-journey-') as temp:
        directory = Path(temp)
        processes = []
        try:
            engine_log = directory / 'engine.log'
            with engine_log.open('w') as log:
                server = subprocess.Popen([sys.executable, str(WEB / 'scripts/test-sync.py'), '--serve', temp],
                                          env=env, stdout=log, stderr=subprocess.STDOUT)
                processes.append(server)
            for _ in range(150):
                if (directory / 'port').exists():
                    break
                if server.poll() is not None:
                    raise RuntimeError(engine_log.read_text())
                time.sleep(.1)
            base = 'http://127.0.0.1:' + (directory / 'port').read_text()
            wait_ready(base + '/openapi.json', server, engine_log)
            child_env = {**env, 'SYNC_TEST_BASE': base, 'SYNC_TEST_DB': str(directory / 'cases.sqlite')}
            if any(name in names for name in ('conversation', 'requested', 'return-draft')):
                with socket.socket() as sock:
                    sock.bind(('127.0.0.1', 3000))
                    web_port = 3000
                web = f'http://127.0.0.1:{web_port}'
                web_log = directory / 'web.log'
                with web_log.open('w') as log:
                    frontend = subprocess.Popen(['node', str(WEB / 'node_modules/vite/bin/vite.js'),
                        '--host', '127.0.0.1', '--port', str(web_port), '--strictPort', '--configLoader', 'runner'],
                        cwd=WEB, env=env, stdout=log, stderr=subprocess.STDOUT)
                    processes.append(frontend)
                wait_ready(web + '/tests/check.html', frontend, web_log)
                child_env['SYNC_WEB_BASE'] = web
            for name in names:
                subprocess.run(['node', '--experimental-strip-types', '--import', './scripts/register-ts.mjs',
                    SHARED[name]], cwd=WEB, env=child_env, check=True, timeout=180)
        finally:
            for process in reversed(processes):
                process.terminate()
                process.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('suites', nargs='*', metavar='SUITE')
    names = parser.parse_args().suites or [*STANDALONE, *SHARED]
    unknown = set(names) - {*STANDALONE, *SHARED}
    if unknown:
        parser.error('Unknown suites: ' + ', '.join(sorted(unknown)))
    env = {key: os.environ[key] for key in (
        'PATH', 'HOME', 'LANG', 'BATATIS_CODEDB', 'BATATIS_SCC_FORM', 'CHROME_PATH', 'PLAYWRIGHT_MODULE'
    ) if key in os.environ}
    env.update(BATATIS_LIVE='0', PYTHONDONTWRITEBYTECODE='1', BATATIS_AUTH_RATE_LIMIT='100',
               BATATIS_CODEDB=env.get('BATATIS_CODEDB', str(ROOT / 'codedb/build/codedb.sqlite')))
    for name in names:
        if name in STANDALONE:
            command = [sys.executable, str(WEB / 'scripts' / STANDALONE[name])]
            if name == 'aliases':
                command.append('--aliases')
            if name == 'isolation':
                command.append('--isolation')
            if name == 'sources':
                command.append('--require-refused')
            subprocess.run(command, cwd=ROOT, env=env, check=True, timeout=240)
    shared = [name for name in names if name in SHARED]
    if shared:
        run_shared(shared, env)


if __name__ == '__main__':
    main()
