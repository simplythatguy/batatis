"""Precedent-example panel data for the six process fields: structure only, never text to paste.

For each applicant-written field, what a good answer must address and which public precedents show that kind of
content, cited by title, issuer, number and PDF page with a public link. The precedents themselves are not in the
repository (`reference/precedents/**` is git-excluded); nothing here copies their text. Each `structure` line is
Batatis's own one-sentence description of how the cited page lays the content out.

Data: `engine/data/process_examples.json` (bundled with the engine). `problems()` is the structure-only check used
by `scripts/gate_g3.py` and `engine/tests/test_process_examples.py`.
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


DATA = Path(__file__).resolve().parent / 'data' / 'process_examples.json'
# Git-excluded local copies of the precedents (a worktree may point at the main checkout's copy).
REFERENCE = Path(os.environ.get('BATATIS_REFERENCE_DIR') or Path(__file__).resolve().parents[1] / 'reference')
LABEL = 'Precedent examples: structure only. Read the source; write your own words.'
MAX_STRUCTURE_WORDS = 45       # a description, not an excerpt
MAX_SHARED_WORDS = 7           # no run of this many consecutive words copied from the cited page
FIELD_IDS = ('rationale', 'risk_assessment', 'mitigating_measures', 'assumptions_and_limits',
             'maintenance_operation', 'qualifications')
_TOKEN = re.compile(r'[a-z0-9]+')


def words(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def _grams(tokens: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)}


BANNED = re.compile(r'\b(?:complies|comply|compliant|safe|approved|approval|adequate|adequacy)\b', re.I)


class PrecedentRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')
    title: str
    issuer: str
    number: str | None = None
    date: str | None = None
    pdf_page: int = Field(ge=1)
    url: str | None = None                     # public source; the local copy is never served
    structure: str                             # Batatis's description of the page's structure, not its text
    edition: str                               # NBC(AE) 2023, or historical (labelled as such)


class ProcessExample(BaseModel):
    """Shown next to a process field. `kind` is fixed so a client can never present it as a draft answer."""
    model_config = ConfigDict(frozen=True, extra='forbid')
    kind: Literal['structure_only'] = 'structure_only'
    label: str = LABEL
    must_address: tuple[str, ...]
    precedents: tuple[PrecedentRef, ...]


@lru_cache(maxsize=1)
def _load() -> dict:
    return json.loads(DATA.read_text(encoding='utf-8'))


def local_file(ref: dict | PrecedentRef) -> Path | None:
    name = ref.get('file') if isinstance(ref, dict) else None
    return REFERENCE / name if name else None


def examples() -> dict[str, ProcessExample]:
    out = {}
    for fid, entry in _load()['fields'].items():
        refs = tuple(PrecedentRef(**{k: v for k, v in p.items() if k != 'file'}) for p in entry['precedents'])
        out[fid] = ProcessExample(must_address=tuple(entry['must_address']), precedents=refs)
    return out


def example_for(field_id: str) -> ProcessExample | None:
    return examples().get(field_id)


def _page_text(path: Path, page: int) -> str | None:
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        return reader.pages[page - 1].extract_text() or '' if page <= len(reader.pages) else None
    except Exception:  # noqa: BLE001  a local copy that cannot be read is reported, never trusted
        return None


def problems(*, check_sources: bool = True) -> list[str]:
    """Structure-only and sourcing checks. With the git-excluded local copies present, every cited page exists
    and no description shares a run of MAX_SHARED_WORDS words with it."""
    out = []
    data = _load()['fields']
    for fid in FIELD_IDS:
        entry = data.get(fid)
        if entry is None:
            out.append(f'{fid}: no example')
            continue
        if len(entry['must_address']) < 3:
            out.append(f'{fid}: fewer than three must-address items')
        if not entry['precedents']:
            out.append(f'{fid}: no precedent')
        for text in entry['must_address']:
            if BANNED.search(text):
                out.append(f'{fid}: must-address item uses "{BANNED.search(text).group()}"')
        for ref in entry['precedents']:
            name = f'{fid}: {ref.get("number") or ref["title"]} p.{ref["pdf_page"]}'
            if len(words(ref['structure'])) > MAX_STRUCTURE_WORDS:
                out.append(f'{name}: structure description is longer than {MAX_STRUCTURE_WORDS} words')
            if BANNED.search(ref['structure']):
                out.append(f'{name}: structure description uses "{BANNED.search(ref["structure"]).group()}"')
            if not ref.get('url'):
                out.append(f'{name}: no public source link')
            path = local_file(ref)
            if check_sources and path is not None and path.is_file():
                page = _page_text(path, ref['pdf_page'])
                if page is None:
                    out.append(f'{name}: the cited page is not in the local copy')
                    continue
                if _grams(words(ref['structure']), MAX_SHARED_WORDS) & _grams(words(page), MAX_SHARED_WORDS):
                    out.append(f'{name}: the structure description copies the source text')
    extra = set(data) - set(FIELD_IDS)
    out += [f'{fid}: not a process field' for fid in sorted(extra)]
    return out
