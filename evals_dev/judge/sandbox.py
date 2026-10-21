"""What the system under test (SUT) gets to see: a scrubbed environment, a temporary working directory and,
where the OS offers it, a sandbox that denies every read and write under the judge folder.

The SUT receives the applicant's words on stdin and nothing else from the dataset. It is started in a fresh
temporary directory with an allow-listed environment: ``BATATIS_JUDGE_DIR`` is removed, as is any variable whose
value mentions the judge folder. On macOS the process also runs under ``sandbox-exec`` with a profile that denies
``file-read*`` and ``file-write*`` on the judge folder, so a SUT that guesses the path still cannot open it.
Where ``sandbox-exec`` is absent only the environment isolation applies, and the judge says so in its output.
"""
from __future__ import annotations

import shutil
import sys
from collections.abc import Mapping
from pathlib import Path

ENV_VAR = 'BATATIS_JUDGE_DIR'
ENV_ALLOW = ('PATH', 'HOME', 'USER', 'LOGNAME', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TMPDIR', 'TZ', 'SSL_CERT_FILE',
             'SSL_CERT_DIR', 'VIRTUAL_ENV', 'PYTHONHASHSEED', 'PYTHONUTF8', 'PYTHONIOENCODING')
# The SUT is the product under test and calls its providers itself, so the provider credentials pass through.
# They go into the child's environment only; the judge never prints them.
ENV_PROVIDER_KEYS = ('JEV_API_KEY', 'TYPESAFE_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'OPENROUTER_API_KEY')
ENV_PREFIXES = ('BATATIS_',)


def _mentions(value: str, folders: set[str]) -> bool:
    return any(f in value for f in folders)


def candidate_env(environ: Mapping[str, str], judge_root: Path, extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """The SUT's environment: allow-listed names only, never a path into the judge folder."""
    folders = {str(judge_root), str(judge_root.resolve())}
    env: dict[str, str] = {}
    for name, value in environ.items():
        if name == ENV_VAR or _mentions(value, folders):
            continue
        if name in ENV_ALLOW or name in ENV_PROVIDER_KEYS or name.startswith(ENV_PREFIXES):
            env[name] = value
    for name, value in (extra or {}).items():
        if name == ENV_VAR or _mentions(str(value), folders):
            raise ValueError(f'refusing to pass {name} to the system under test')
        env[name] = str(value)
    return env


def _quote(path: str) -> str:
    return path.replace('\\', '\\\\').replace('"', '\\"')


def sandbox_profile(judge_root: Path) -> str:
    folders = sorted({str(judge_root), str(judge_root.resolve())})
    rules = ''.join(f'(deny file-read* (subpath "{_quote(f)}"))(deny file-write* (subpath "{_quote(f)}"))'
                    for f in folders)
    return '(version 1)(allow default)' + rules


def sandbox_prefix(judge_root: Path) -> list[str] | None:
    """Command prefix that runs a process with the judge folder unreadable, or None when the OS has no sandbox."""
    exe = shutil.which('sandbox-exec')
    if sys.platform != 'darwin' or not exe:
        return None
    return [exe, '-p', sandbox_profile(judge_root)]
