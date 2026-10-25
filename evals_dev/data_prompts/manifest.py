"""Frozen provenance for new experiments, computed once in the parent, never inside SUT workers.

Only hashes/configuration live here. References, availability labels and expected answers never enter
the engine request. Historical runs without this manifest remain explicitly legacy/unverified.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import corpus

VERSION = 'dpe-manifest-v1'
HARNESS = Path(__file__).resolve().parent


def fingerprint(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode()).hexdigest()


def file_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _tree(root: Path, suffixes: tuple[str, ...]) -> dict:
    return {str(p.relative_to(root)): file_hash(p) for p in sorted(root.rglob('*'))
            if p.is_file() and p.suffix in suffixes and '__pycache__' not in p.parts}


def scoring_sources() -> dict:
    """Hash the measurement inputs once, without opening item-level holdout errors or outputs."""
    from engine.codes import default_db
    metadata = {'index.json': file_hash(corpus.METADATA_ROOT / 'index.json')}
    for case in corpus.load():
        for name in ('prompt.txt', 'source.json', 'evaluation.json'):
            key = str(Path(case.folder) / name)
            metadata[key] = file_hash(corpus.METADATA_ROOT / key)
    return {'corpus': metadata, 'split': corpus.split(), 'measurement': _tree(HARNESS, ('.py',)),
            'gold': {name: file_hash(HARNESS / name) for name in ('gold.py', 'texts.py', 'corpus.py')},
            'availability': file_hash(HARNESS / 'availability.json'),
            'codedb': {name: file_hash(Path(str(default_db()) + suffix))
                       for name, suffix in (('database', ''), ('wal', '-wal'))}}


def build(args, metadata: dict, cases) -> dict:
    # Each distinct original attachment is read once here; case.read still enforces its recorded
    # source hash at the engine boundary. Workers receive only the resulting fingerprint.
    attachments = {}
    for case in cases:
        for attachment in case.attachments:
            path = case.path(attachment)
            key = str(path.resolve())
            if key not in attachments:
                attachments[key] = {'expected_sha256': attachment.sha256, 'sha256': file_hash(path)}
    return {'version': VERSION, 'resolved': {k: v for k, v in metadata.items()
                                            if k not in ('name', 'started', 'commit')},
            'selection': {'split': args.split, 'limit': args.limit, 'case_ids': [c.id for c in cases]},
            'engine': _tree(corpus.REPO / 'engine', ('.py', '.json')),
            'harness': _tree(HARNESS, ('.py',)),
            'codedb_code': _tree(corpus.REPO / 'codedb', ('.py',)),
            'scoring_sources': scoring_sources(), 'attachments': attachments}
