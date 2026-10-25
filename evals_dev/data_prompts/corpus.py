"""The 653 Data Prompts cases, their default-input attachments, and the grouped dev/holdout split.

Metadata (prompt.txt, source.json, evaluation.json) is read from the committed `Data Prompts/` folder.
Attachments are not in Git; they are read from DATA_PROMPTS_ROOT (a restored local collection) and
checked against the recorded sha256 before use. evaluation.json and source.json never reach the system
under test: only the prompt text and the default-input attachments do.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
METADATA_ROOT = REPO / 'Data Prompts'
TIERS = ('Calgary / Edmonton', 'Other Alberta / province-wide', 'Canadian supporting evidence',
         'Outside Alberta - attachment comparison only')


def attachments_root() -> Path:
    return Path(os.environ.get('DATA_PROMPTS_ROOT') or METADATA_ROOT)


@dataclass(frozen=True)
class Attachment:
    filename: str
    role: str
    sha256: str
    bytes: int

    @property
    def kind(self) -> str:
        return Path(self.filename).suffix.lower().lstrip('.')


@dataclass(frozen=True)
class SourceFact:
    text: str
    locator: str


@dataclass(frozen=True)
class Case:
    id: str
    prompt_no: int
    folder: str
    title: str
    tier: str
    case_type: str
    jurisdiction: str
    code_edition: str
    country: str
    province: str
    city: str
    source_group: str
    outcome_leakage: bool
    prompt: str
    attachments: tuple[Attachment, ...]
    facts: tuple[SourceFact, ...]
    focus: tuple[str, ...]
    known_outcome: str
    limitations: tuple[str, ...] = field(default=())

    def path(self, attachment: Attachment) -> Path:
        return attachments_root() / self.folder / attachment.filename

    def read(self, attachment: Attachment) -> bytes:
        data = self.path(attachment).read_bytes()
        if hashlib.sha256(data).hexdigest() != attachment.sha256:
            raise ValueError(f'{self.id}: {attachment.filename} does not match its recorded sha256')
        return data


def _focus(value, case_id: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or not all(isinstance(x, str) and len(x.strip()) > 3 for x in value):
        raise ValueError(f'{case_id}: review_focus must be a list of statements')
    return tuple(x.strip() for x in value)


@cache
def load(root: Path | None = None) -> tuple[Case, ...]:
    root = Path(root or METADATA_ROOT)
    out = []
    for row in json.loads((root / 'index.json').read_text()):
        folder = root / row['folder']
        source = json.loads((folder / 'source.json').read_text())
        evaluation = json.loads((folder / 'evaluation.json').read_text())
        attachments = tuple(Attachment(a['filename'], a.get('role') or 'input', a['sha256'], int(a.get('bytes') or 0))
                            for a in source['attachments'] if a.get('included_in_default_input', True))
        out.append(Case(
            id=row['case_id'], prompt_no=int(row['prompt']), folder=row['folder'], title=row['title'],
            tier=row['priority'], case_type=row['case_type'], jurisdiction=row['jurisdiction'],
            code_edition=row['code_edition'], country=row['country'], province=row['province_or_state'],
            city=row['city_or_town'], source_group=row['source_group'], outcome_leakage=bool(row['outcome_leakage']),
            prompt=(folder / 'prompt.txt').read_text().strip(), attachments=attachments,
            facts=tuple(SourceFact(f['text'].strip(), (f.get('locator') or '').strip()) for f in source['facts']),
            focus=_focus(evaluation.get('review_focus'), row['case_id']),
            known_outcome=(evaluation.get('known_outcome') or '').strip(),
            limitations=tuple(source.get('limitations') or ())))
    if len(out) != 653 or len({c.id for c in out}) != len(out):
        raise ValueError('expected 653 distinct cases')
    return tuple(out)


def _components(cases: tuple[Case, ...]) -> dict[str, str]:
    """Case id -> component key. Cases sharing a source group or any attachment file are one component."""
    parent: dict[str, str] = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    for c in cases:
        union('case:' + c.id, 'group:' + c.source_group)
        for a in c.attachments:
            union('case:' + c.id, 'file:' + a.sha256)
    return {c.id: find('case:' + c.id) for c in cases}


@cache
def split(cases: tuple[Case, ...] | None = None) -> dict[str, str]:
    """Case id -> 'dev' or 'holdout'. Whole components stay together; each tier is balanced by case count.

    Deterministic: components are ordered by a hash of their key, then each goes to whichever split
    has fewer cases of that tier so far (ties go to dev)."""
    cases = cases or load()
    comp = _components(cases)
    members: dict[str, list[Case]] = {}
    for c in cases:
        members.setdefault(comp[c.id], []).append(c)
    counts = {(t, s): 0 for t in TIERS for s in ('dev', 'holdout')}
    out: dict[str, str] = {}
    keyed = sorted(members.items(), key=lambda kv: hashlib.sha256(kv[0].encode()).hexdigest())
    for _, group in keyed:
        tier = max(TIERS, key=lambda t: sum(c.tier == t for c in group))
        side = 'dev' if counts[(tier, 'dev')] <= counts[(tier, 'holdout')] else 'holdout'
        for c in group:
            out[c.id] = side
            counts[(c.tier, side)] += 1
    return out


def select(name: str, cases: tuple[Case, ...] | None = None) -> list[Case]:
    """'dev', 'holdout', 'all', or a comma-separated list of case ids."""
    cases = cases or load()
    if name == 'all':
        return list(cases)
    if name in ('dev', 'holdout'):
        sides = split(cases)
        return [c for c in cases if sides[c.id] == name]
    wanted = [x.strip() for x in name.split(',') if x.strip()]
    by_id = {c.id: c for c in cases}
    missing = [x for x in wanted if x not in by_id]
    if missing:
        raise KeyError(f'unknown case ids: {", ".join(missing)}')
    return [by_id[x] for x in wanted]
