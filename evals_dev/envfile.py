"""Read provider keys from a git-ignored ``.env`` without ever printing them.

The keys are loaded by the runner itself (there is no dotenv dependency). Nothing here logs, prints or returns a
value except to the caller that asked for the variable by name. ``find_env_file`` looks in the checkout, then in
the main checkout of the same repository (a worktree has no ``.env`` of its own).
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_LINE = re.compile(r'^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$')
KEY_NAMES = ('OPENAI_API_KEY', 'JEV_API_KEY', 'TYPESAFE_API_KEY', 'ANTHROPIC_API_KEY', 'OPENROUTER_API_KEY')


def parse_env(text: str) -> dict[str, str]:
    """``NAME=value`` lines; quotes around a value are removed; comments and blank values are skipped."""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith('#'):
            continue
        m = _LINE.match(raw)
        if not m:
            continue
        name, value = m.groups()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
            value = value[1:-1]
        elif ' #' in value:
            value = value.split(' #', 1)[0].rstrip()
        if value:
            out[name] = value
    return out


def main_checkout() -> Path | None:
    """The repository's main working tree (where the git-ignored .env lives), found through git."""
    try:
        common = subprocess.run(['git', 'rev-parse', '--path-format=absolute', '--git-common-dir'], cwd=REPO,
                                capture_output=True, text=True, timeout=10, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return Path(common).parent if common else None


def find_env_file(explicit: str | os.PathLike | None = None) -> Path | None:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    elif os.environ.get('BATATIS_ENV_FILE'):
        candidates.append(Path(os.environ['BATATIS_ENV_FILE']))
    else:
        candidates.append(REPO / '.env')
        main = main_checkout()
        if main:
            candidates.append(main / '.env')
    return next((p for p in candidates if p.is_file()), None)


def load_env_file(path: str | os.PathLike | None = None, *, names: tuple[str, ...] | None = None,
                  environ: dict | None = None, override: bool = False) -> list[str]:
    """Copy variables from the .env into ``environ`` (default ``os.environ``). Returns the names set, never values."""
    target = os.environ if environ is None else environ
    found = find_env_file(path)
    if found is None:
        return []
    values = parse_env(found.read_text(encoding='utf-8'))
    set_names = []
    for name, value in values.items():
        if names is not None and name not in names:
            continue
        if override or not target.get(name):
            target[name] = value
            set_names.append(name)
    return sorted(set_names)


def apply_defaults(environ: dict | None = None) -> None:
    """Environment fixes this Mac needs: a CA bundle for the python.org build, and the Jev key under its client name."""
    target = os.environ if environ is None else environ
    if not target.get('SSL_CERT_FILE') and Path('/etc/ssl/cert.pem').is_file():
        target['SSL_CERT_FILE'] = '/etc/ssl/cert.pem'
    # The vendored Jev client reads TYPESAFE_API_KEY; the project and the .env call the same key JEV_API_KEY.
    if target.get('JEV_API_KEY') and not target.get('TYPESAFE_API_KEY'):
        target['TYPESAFE_API_KEY'] = target['JEV_API_KEY']


def redact(text: str, environ: dict | None = None) -> str:
    """Replace any known key value found in ``text`` with its variable name, for logs and error messages."""
    source = os.environ if environ is None else environ
    for name in KEY_NAMES:
        value = source.get(name)
        if value and len(value) >= 8:
            text = text.replace(value, f'<{name}>')
    return text
