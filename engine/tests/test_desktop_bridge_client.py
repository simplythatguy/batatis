"""The test host isolates child homes and retains failures from real pipe processes."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import traceback

import pytest

from engine.desktop.bridge import ProtocolError
from engine.tests import desktop_bridge_client as client


@pytest.fixture
def synthetic_parent(monkeypatch, tmp_path):
    allowed = {'PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'TMPDIR', 'LANG', 'LC_ALL', 'LC_CTYPE'}
    env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    ambient = tmp_path / 'ambient-home'
    ambient.mkdir()
    env.update(HOME=str(ambient), USERPROFILE=str(ambient), HOMEDRIVE='Z:', HOMEPATH=r'\ambient-home',
               PYTHONPATH=str(ambient / 'modules'), CODEX_HOME=str(ambient / 'codex'),
               OPENAI_API_KEY='synthetic-key', BATATIS_CASES=str(ambient / 'cases.sqlite'),
               BATATIS_CODEDB=str(ambient / 'codedb.sqlite'), VERCEL='1')
    monkeypatch.setattr(os, 'environ', env)
    return env


def test_child_home_resolves_with_the_real_windows_stdlib_policy(tmp_path, synthetic_parent):
    env = client.engine_env('local', tmp_path)
    child = subprocess.run([sys.executable, '-c', '''
import json, ntpath
from pathlib import Path
print(json.dumps({'windows': ntpath.expanduser('~'), 'native': str(Path.home())}))
'''], env=env, cwd=client.ROOT, capture_output=True, text=True, timeout=10)
    assert child.returncode == 0, child.stderr
    homes = json.loads(child.stdout)
    expected = tmp_path / 'engine-home'
    assert homes == {'windows': str(expected), 'native': str(expected)}
    assert expected.is_dir()
    assert synthetic_parent['HOME'] != str(expected)


def test_only_os_settings_pass_through_and_workspace_paths_stay_explicit(monkeypatch, tmp_path):
    temporary = str(tmp_path / 'os-temp')
    monkeypatch.setattr(os, 'environ', {
        'Path': 'synthetic-path', 'SystemRoot': r'C:\Windows', 'windir': r'C:\Windows',
        'TEMP': temporary, 'TMP': temporary, 'TMPDIR': temporary,
        'LANG': 'en_CA.UTF-8', 'LC_ALL': 'C', 'LC_CTYPE': 'C',
        'HOME': 'ambient-home', 'USERPROFILE': 'ambient-profile', 'HOMEDRIVE': 'Z:',
        'HOMEPATH': r'\ambient-home', 'PYTHONPATH': 'ambient-modules',
        'PYTHONSTARTUP': 'ambient-startup', 'CODEX_HOME': 'ambient-codex',
        'OPENAI_API_KEY': 'synthetic-key', 'DATABASE_URL': 'synthetic-database',
        'BATATIS_STORE': 'postgres', 'BATATIS_LIVE': '1', 'VERCEL': '1',
        'BATATIS_CASES': 'ambient-cases', 'BATATIS_CODEDB': 'ambient-codedb',
    })
    codedb = tmp_path / 'reference' / 'codedb.sqlite'
    env = client.engine_env('dev', tmp_path, codedb=codedb)
    for key, expected in {
        'PATH': 'synthetic-path', 'SYSTEMROOT': r'C:\Windows', 'WINDIR': r'C:\Windows',
        'TEMP': temporary, 'TMP': temporary, 'TMPDIR': temporary,
        'LANG': 'en_CA.UTF-8', 'LC_ALL': 'C', 'LC_CTYPE': 'C',
        'HOME': str(tmp_path / 'engine-home'), 'USERPROFILE': str(tmp_path / 'engine-home'),
        'BATATIS_DESKTOP_WORKSPACE': 'dev', 'BATATIS_CASES': str(tmp_path / 'dev' / 'cases.sqlite'),
        'BATATIS_CODEDB': str(codedb), 'PYTHONDONTWRITEBYTECODE': '1',
    }.items():
        assert env.get(key) == expected, key
    assert not ({'HOMEDRIVE', 'HOMEPATH', 'PYTHONPATH', 'PYTHONSTARTUP', 'CODEX_HOME',
                 'OPENAI_API_KEY', 'DATABASE_URL', 'BATATIS_STORE', 'BATATIS_LIVE', 'VERCEL'} & env.keys())


def test_deliberate_test_overrides_win_after_isolation(tmp_path, synthetic_parent):
    overrides = {'HOME': str(tmp_path / 'explicit-home'), 'USERPROFILE': str(tmp_path / 'explicit-profile'),
                 'VERCEL': '1', 'BATATIS_CASES': str(tmp_path / 'explicit-cases.sqlite'),
                 'BATATIS_CODEDB': str(tmp_path / 'explicit-codedb.sqlite'), 'PYTHONPATH': 'explicit-modules'}
    env = client.engine_env('local', tmp_path, **overrides)
    assert all(env[key] == value for key, value in overrides.items())


@pytest.fixture
def child_host(monkeypatch):
    processes = []
    readers = []
    popen = subprocess.Popen
    thread = threading.Thread

    def spawn(*args, **kwargs):
        process = popen(*args, **kwargs)
        processes.append(process)
        return process

    def reader(*args, **kwargs):
        collector = thread(*args, **kwargs)
        readers.append(collector)
        return collector

    def command(source):
        monkeypatch.setattr(client, 'engine_command', lambda: ([sys.executable, '-c', source], client.ROOT))

    monkeypatch.setattr(subprocess, 'Popen', spawn)
    monkeypatch.setattr(threading, 'Thread', reader)
    yield command, processes, readers
    for process in processes:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
    for collector in readers:
        collector.join(timeout=5)
    for process in processes:
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()


def assert_released(processes, readers):
    assert processes and readers
    assert all(process.poll() is not None for process in processes)
    assert all(stream.closed for process in processes for stream in (process.stdin, process.stdout, process.stderr))
    assert all(not collector.is_alive() for collector in readers)


@pytest.mark.parametrize(('kind', 'hosted'), [('local', False), ('dev', False), ('local', True)])
def test_source_entry_reaches_hello_or_refusal_under_windows_home_policy(
        tmp_path, synthetic_parent, child_host, kind, hosted):
    command, _, _ = child_host
    command('''
import ntpath, os
os.path.expanduser = ntpath.expanduser
from engine.desktop.__main__ import main
main()
''')
    engine = client.EngineProcess(client.engine_env(kind, tmp_path, **({'VERCEL': '1'} if hosted else {})))
    try:
        if hosted:
            assert engine.hello['t'] == 'refused' and 'VERCEL' in engine.hello['reason']
            assert engine.proc.wait(timeout=20) == 3
            assert not (tmp_path / kind / 'cases.sqlite').exists()
        else:
            assert engine.hello['t'] == 'hello'
            assert engine.hello['workspace']['kind'] == kind
            assert (tmp_path / kind / 'cases.sqlite').is_file()
            assert engine.close(timeout=20) == 0
    finally:
        engine.close()


@pytest.mark.parametrize('close_stdout_first', [False, True])
def test_failed_start_retains_bounded_stderr_and_exit_code_and_releases_resources(
        tmp_path, synthetic_parent, child_host, close_stdout_first):
    command, processes, readers = child_host
    command(f'''
import os, sys, time
if {close_stdout_first!r}:
    os.close(sys.stdout.fileno())
    time.sleep(0.05)
sys.stderr.buffer.write(b'x' * (256 * 1024) + b'\\xff\\nstartup failure marker\\n')
sys.stderr.buffer.flush()
sys.exit(17)
''')
    with pytest.raises(EOFError) as failed:
        client.EngineProcess(client.engine_env('local', tmp_path))
    diagnostic = ''.join(traceback.format_exception(failed.value))
    assert 'engine closed its output' in diagnostic
    assert 'exit code 17' in diagnostic
    assert '\ufffd\nstartup failure marker' in diagnostic
    assert len(diagnostic) < 70 * 1024
    assert_released(processes, readers)


def test_malformed_start_preserves_protocol_error_and_child_diagnostics(tmp_path, synthetic_parent, child_host):
    command, processes, readers = child_host
    command('''
import os, sys
sys.stderr.write('malformed startup marker\\n')
sys.stderr.flush()
os.write(sys.stdout.fileno(), b'\\0' * 8)
sys.stdin.buffer.read()
sys.exit(23)
''')
    with pytest.raises(ProtocolError, match='frame too large') as failed:
        client.EngineProcess(client.engine_env('local', tmp_path))
    diagnostic = ''.join(traceback.format_exception(failed.value))
    assert 'exit code 23' in diagnostic
    assert 'malformed startup marker' in diagnostic
    assert_released(processes, readers)


@pytest.mark.parametrize('ignore_eof', [False, True])
def test_close_releases_collectors_and_pipes_even_when_wait_times_out(
        tmp_path, synthetic_parent, child_host, ignore_eof):
    command, processes, readers = child_host
    command(f'''
import sys, time
from engine.desktop.bridge import encode
sys.stdout.buffer.write(encode({{'t': 'hello'}}))
sys.stdout.buffer.flush()
if {ignore_eof!r}:
    time.sleep(60)
else:
    sys.stdin.buffer.read()
''')
    engine = client.EngineProcess(client.engine_env('local', tmp_path))
    if ignore_eof:
        with pytest.raises(subprocess.TimeoutExpired):
            engine.close(timeout=0.1)
    else:
        assert engine.close(timeout=5) == 0
        assert engine.close(timeout=5) == 0
    assert_released(processes, readers)
