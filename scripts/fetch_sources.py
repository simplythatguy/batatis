"""Download the NBC(AE) PDFs the codedb builder needs. Each download is sha256-checked.

Official URLs are tried first, with retries. When a build machine cannot reach
nrc-publications.canada.ca, set CODEDB_PDF_URL and CODEDB_INTENT_PDF_URL to private
Vercel Blob or Neon object URLs. Those URLs are never printed. A mismatched digest
is deleted. This script does not commit the PDF or the sqlite, and it fails the
build rather than continue without a verified file.

CODEDB_SKIP_OFFICIAL=1 skips the NRC host when the matching private URL is set.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Pinned to the official publications. Sizes and digests match the local rebuild inputs.
# Intent statements are required because `python -m codedb build` reads both PDFs.
DEFAULTS = (
    {
        'key': 'nbc_ae',
        'env': 'CODEDB_PDF_URL',
        'url': 'https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en',
        'sha256': '3d45376d6c71d54b7f1797084d0828c250b20ab9b380f424f1aab8cfc9a39827',
        'bytes': 15010934,
        'path': 'reference/codes/NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2.pdf',
        'jsonl': 'reference/text/NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2.jsonl',
        'jsonl_sha256': '923483af04ebba73d9dd8c31742c7eb05f0eca018a3dd67c29bab532e350af29',
    },
    {
        'key': 'intent',
        'env': 'CODEDB_INTENT_PDF_URL',
        'url': 'https://nrc-publications.canada.ca/eng/view/ft/?id=de0e0ec9-a452-4337-bc84-002a230c9d66',
        'sha256': 'a75ef52eff6f060a4735010c0435ee966b48b1a1d11cf22e1610f557096ba4cf',
        'bytes': 17156090,
        'path': 'reference/codes/NBC-2020-Intent-Statements.pdf',
        'jsonl': 'reference/text/NBC-2020-Intent-Statements.jsonl',
        'jsonl_sha256': '787c20b46a7c0ee975873cf7662fb0dc9af70df2d16ddb71d00584edc2aa50b1',
    },
)

# Safety Codes Council variance form. Live URL checked 2026-10-20; sha256 matches
# engine/export/field_maps/scc_2026-10.json. Not a codedb input. Never commit the PDF.
SCC_FORM = {
    'key': 'scc_form',
    'env': 'SCC_FORM_URL',
    'url': 'https://ebs.safetycodes.ab.ca/documents/webdocs/PI/Variance%20Template%20final.pdf',
    'sha256': 'f44640ca005c957c11a2387d2768fffc35ef93c97125dcca37436fcc0b9afc1d',
    'bytes': 334580,
    'path': 'codedb/build/SCC-Variance-Form.pdf',
}

FAIL = ('engine build failed: {detail} The engine will not deploy without a sha256-checked code database. '
        'Do not commit the NRC PDF or codedb.sqlite. If the build machine cannot reach '
        'nrc-publications.canada.ca, set CODEDB_PDF_URL and CODEDB_INTENT_PDF_URL to private '
        'Vercel Blob or Neon object URLs that are not publicly readable. The bytes are still '
        'sha256-checked.')

SCC_FAIL = ('engine build failed: {detail} Do not commit the SCC variance form. '
            'If the builder cannot reach ebs.safetycodes.ab.ca, set SCC_FORM_URL to a private '
            'URL that is not publicly readable. The bytes are still sha256-checked.')


class DownloadError(Exception):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def load_sources(root: Path = ROOT) -> list[dict]:
    manifest = root / 'codedb' / 'source_manifest.json'
    if not manifest.is_file():
        return [dict(item) for item in DEFAULTS]
    data = json.loads(manifest.read_text())
    items = []
    for key, env in (('nbc_ae', 'CODEDB_PDF_URL'), ('intent', 'CODEDB_INTENT_PDF_URL')):
        if key not in data:
            continue
        item = dict(data[key])
        item['key'] = key
        item['env'] = env
        items.append(item)
    return items or [dict(item) for item in DEFAULTS]


def curl_fetch(url: str, dest: Path, retries: int = 3) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ['curl', '--http1.1', '-fsSL', '--retry', str(retries), '--retry-delay', '2',
           '--retry-all-errors', '--connect-timeout', '20', '--max-time', '180',
           '-o', str(dest), url]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        dest.unlink(missing_ok=True)
        raise DownloadError(f'curl exit {proc.returncode}')


def _candidates(item: dict, env: dict) -> list[tuple[str, str]]:
    private = (env.get(item['env']) or '').strip()
    skip_official = env.get('CODEDB_SKIP_OFFICIAL') == '1' and bool(private)
    urls = []
    if not skip_official:
        urls.append(('official', item['url']))
    if private:
        urls.append(('private', private))
    return urls


def acquire(item: dict, *, root: Path, env: dict | None = None, fetcher=curl_fetch, log=print,
            fail: str = FAIL) -> Path:
    """Download one pinned PDF. Raises DownloadError with a deploy-stopping message."""
    env = os.environ if env is None else env
    dest = root / item['path']
    if dest.is_file() and dest.stat().st_size == int(item['bytes']) and sha256(dest) == item['sha256']:
        log(f'ok {item["key"]} already sha256-checked')
        return dest
    errors = []
    for kind, url in _candidates(item, env):
        tmp = dest.with_suffix(dest.suffix + '.partial')
        tmp.parent.mkdir(parents=True, exist_ok=True)
        try:
            log(f'download {item["key"]} from {kind} source')
            fetcher(url, tmp)
            got = sha256(tmp)
            size = tmp.stat().st_size
            if got != item['sha256'] or size != int(item['bytes']):
                tmp.unlink(missing_ok=True)
                errors.append(f'{kind} source sha256 {got} ({size} bytes) does not match '
                              f'pinned {item["sha256"]} ({item["bytes"]} bytes)')
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp.replace(dest)
            log(f'ok {item["key"]} sha256-checked via {kind} source')
            return dest
        except DownloadError as exc:
            tmp.unlink(missing_ok=True)
            errors.append(f'{kind} source failed: {exc}')
        except OSError as exc:
            tmp.unlink(missing_ok=True)
            errors.append(f'{kind} source failed: {exc}')
    detail = f'could not fetch {item["key"]} ({"; ".join(errors) or "no URL"}).'
    raise DownloadError(fail.format(detail=detail))


def extract_jsonl(pdf: Path, dest: Path, expect_sha: str | None) -> None:
    if dest.is_file() and (not expect_sha or sha256(dest) == expect_sha):
        print(f'ok {dest.name} jsonl matches', file=sys.stderr)
        return
    from pypdf import PdfReader
    reader = PdfReader(str(pdf))
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(dest.suffix + '.partial')
    with partial.open('w', encoding='utf8') as handle:
        for number, page in enumerate(reader.pages, 1):
            handle.write(json.dumps({'page': number, 'text': page.extract_text() or ''}, ensure_ascii=False) + '\n')
    if expect_sha and sha256(partial) != expect_sha:
        partial.unlink(missing_ok=True)
        raise DownloadError(FAIL.format(detail=(
            f'{dest.name} page extract is not sha256-checked. '
            'The codedb was not built from an unverified extract.')))
    partial.replace(dest)
    print(f'extracted {dest.name} pages={len(reader.pages)}', file=sys.stderr)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    form_only = '--scc-form' in argv
    try:
        if not form_only:
            for item in load_sources():
                pdf = acquire(item, root=ROOT, log=lambda msg: print(msg, file=sys.stderr))
                if item.get('jsonl'):
                    extract_jsonl(pdf, ROOT / item['jsonl'], item.get('jsonl_sha256'))
        acquire(SCC_FORM, root=ROOT, fail=SCC_FAIL, log=lambda msg: print(msg, file=sys.stderr))
    except DownloadError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
