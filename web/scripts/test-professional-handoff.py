"""Run the J02 public applicant/sync/officer regression with disposable SQLite and no provider I/O."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request

WEB = Path(__file__).resolve().parents[1]
env = {key: os.environ[key] for key in ('PATH', 'HOME', 'LANG', 'BATATIS_CODEDB') if key in os.environ}
env.update(BATATIS_LIVE='0', PYTHONDONTWRITEBYTECODE='1',
           BATATIS_REVIEWER_CODES='{"edmonton":"officer-secret","calgary":"calgary-secret"}',
           BATATIS_AUTH_RATE_LIMIT='100')
with tempfile.TemporaryDirectory(prefix='batatis-professional-handoff-') as tmp:
    directory = Path(tmp)
    with (directory / 'server.log').open('w') as log:
        server = subprocess.Popen([sys.executable, str(WEB / 'scripts/test-sync.py'), '--serve', tmp],
                                  env=env, stdout=log, stderr=subprocess.STDOUT)
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
            result = subprocess.run(['node', '--experimental-strip-types', '--import', './scripts/register-ts.mjs',
                                     'tests/professional-handoff.integration.mts'], cwd=WEB, env=env, timeout=120)
            sys.exit(result.returncode)
        finally:
            server.terminate()
            server.wait(timeout=10)
