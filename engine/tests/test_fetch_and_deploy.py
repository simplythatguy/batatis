import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('fetch_sources', ROOT / 'scripts' / 'fetch_sources.py')
fetch_sources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch_sources)


def _item(payload: bytes):
    return {'key': 'nbc_ae', 'env': 'CODEDB_PDF_URL', 'url': 'https://nrc-publications.canada.ca/example.pdf',
            'sha256': hashlib.sha256(payload).hexdigest(), 'bytes': len(payload),
            'path': 'reference/codes/sample.pdf'}


def test_official_failure_then_private_url_is_not_logged(tmp_path):
    payload = b'%PDF-private-bytes'
    logs = []

    def fetcher(url, dest):
        if 'nrc-publications' in url:
            raise fetch_sources.DownloadError('curl exit 6')
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload)

    path = fetch_sources.acquire(_item(payload), root=tmp_path,
                                 env={'CODEDB_PDF_URL': 'https://blob.example/signed?token=secret-value'},
                                 fetcher=fetcher, log=logs.append)
    assert path.read_bytes() == payload
    text = '\n'.join(logs)
    assert 'secret-value' not in text and 'private source' in text
    assert 'official' in text


def test_hash_mismatch_and_total_failure_do_not_keep_a_file(tmp_path):
    payload = b'not-the-pdf'
    item = _item(b'the-real-bytes')

    def fetcher(url, dest):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload)

    with pytest.raises(fetch_sources.DownloadError):
        fetch_sources.acquire(item, root=tmp_path, env={}, fetcher=fetcher, log=lambda _m: None)
    assert not (tmp_path / item['path']).exists()
    assert list(tmp_path.rglob('*.partial')) == []


def test_failure_message_refuses_to_continue(tmp_path):
    def fetcher(url, dest):
        raise fetch_sources.DownloadError('curl exit 6')

    with pytest.raises(fetch_sources.DownloadError) as raised:
        fetch_sources.acquire(_item(b'abc'), root=tmp_path, env={'CODEDB_PDF_URL': 'https://private.example/obj'},
                              fetcher=fetcher, log=lambda _m: None)
    message = str(raised.value)
    assert 'Do not commit the NRC PDF or codedb.sqlite' in message
    assert 'private.example' not in message
    assert 'CODEDB_PDF_URL' in message


def test_skip_official_uses_only_the_private_url(tmp_path):
    payload = b'private-ok'
    seen = []

    def fetcher(url, dest):
        seen.append(url)
        dest.write_bytes(payload)

    fetch_sources.acquire(_item(payload), root=tmp_path,
                          env={'CODEDB_PDF_URL': 'https://private.example/obj', 'CODEDB_SKIP_OFFICIAL': '1'},
                          fetcher=fetcher, log=lambda _m: None)
    assert seen == ['https://private.example/obj']


def test_vercel_config_keeps_sqlite_on_the_engine_only():
    config = json.loads((ROOT / 'vercel.json').read_text())
    web = config['services']['web']
    engine = config['services']['engine']
    assert web['root'] == 'web' and web['outputDirectory'] == 'dist'
    assert 'codedb' not in json.dumps(web)
    included = engine['functions']['engine/api.py']['includeFiles']
    excluded = engine['functions']['engine/api.py']['excludeFiles']
    assert 'codedb/build/codedb.sqlite' in included
    assert 'codedb/build/SCC-Variance-Form.pdf' in included
    assert 'reference/**' in excluded
    assert 'engine/tests/**' in excluded and 'evals/**' in excluded and 'reference/**' in excluded
    assert config['rewrites'][0]['source'] == '/api/(.*)'
    assert config['rewrites'][0]['destination'] == {'service': 'engine'}
    assert config['rewrites'][1]['destination'] == {'service': 'web'}
    assert engine['rewrites'][0]['destination'] == '/:path'
    assert config['headers'][0]['headers'][0] == {'key': 'X-Robots-Tag', 'value': 'noindex, nofollow'}
    assert 'Disallow: /' in (ROOT / 'web' / 'public' / 'robots.txt').read_text()
    build = (ROOT / 'scripts' / 'vercel_build_engine.sh').read_text()
    assert 'scripts/build_codedb.sh' in build
    assert 'fetch_sources.py' in build
    assert 'Refusing to deploy without a sha256-checked code database' in build
    client = (ROOT / 'web' / 'src' / 'api' / 'client.ts').read_text()
    assert 'VITE_API_BASE' in client
    assert 'PDF too large' not in client
    assert 'PDF too large: the limit is 4 MB' in (ROOT / 'engine' / 'uploads.py').read_text()
