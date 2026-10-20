"""Download official NBC(AE) and SCC sources into gitignored reference/ paths and check sha256.

Idempotent: a file whose size and sha256 already match the manifest is left in place.
JSONL text is extracted with pypdf when the pinned extract is missing. Does not print secrets.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'codedb' / 'source_manifest.json'


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def require_file(path: Path, expect_sha: str, expect_bytes: int, url: str) -> None:
    if path.is_file() and path.stat().st_size == expect_bytes and sha256(path) == expect_sha:
        print(f'ok {path.relative_to(ROOT)} sha256 matches', file=sys.stderr)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.partial')
    print(f'download {path.name}', file=sys.stderr)
    proc = subprocess.run(
        ['curl', '--http1.1', '-L', '--fail', '--retry', '3', '--retry-delay', '2', '-o', str(tmp), url],
        cwd=ROOT)
    if proc.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise SystemExit(f'could not download {url} (curl exit {proc.returncode})')
    got = sha256(tmp)
    size = tmp.stat().st_size
    if got != expect_sha or size != expect_bytes:
        tmp.unlink(missing_ok=True)
        raise SystemExit(
            f'{path.name} SHA-256 {got} ({size} bytes) does not match manifest {expect_sha} ({expect_bytes} bytes). '
            f'Refusing to keep the file.')
    tmp.replace(path)
    print(f'ok {path.relative_to(ROOT)} downloaded', file=sys.stderr)


def extract_jsonl(pdf: Path, dest: Path, expect_sha: str | None) -> None:
    if dest.is_file() and (expect_sha is None or sha256(dest) == expect_sha):
        print(f'ok {dest.relative_to(ROOT)} jsonl matches', file=sys.stderr)
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    from pypdf import PdfReader
    reader = PdfReader(str(pdf))
    with dest.open('w', encoding='utf8') as handle:
        for number, page in enumerate(reader.pages, 1):
            handle.write(json.dumps({'doc': pdf.stem, 'page': number, 'text': page.extract_text() or ''}) + '\n')
    if expect_sha and sha256(dest) != expect_sha:
        raise SystemExit(f'{dest.name} extract SHA-256 does not match the manifest. Refusing to continue.')
    print(f'extracted {dest.name} pages={len(reader.pages)}', file=sys.stderr)


def main() -> int:
    manifest = json.loads(MANIFEST.read_text())
    for key in ('nbc_ae', 'intent', 'form'):
        item = manifest[key]
        path = ROOT / item['path']
        require_file(path, item['sha256'], int(item['bytes']), item['url'])
        if item.get('jsonl'):
            extract_jsonl(path, ROOT / item['jsonl'], item.get('jsonl_sha256'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
