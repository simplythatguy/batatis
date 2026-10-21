"""Load the judge-only held-out scenarios (``BATATIS_JUDGE_DIR``, default ``~/batatis-judge``).

The folder layout is the one in the dataset's own README: ``evals/scenarios/ab-NNN.yaml`` (JSON syntax),
``evals/dataset-manifest.json``. This module reads only what the judge scores with: the applicant's words, the
split, the confidence, the required and helpful citations, the prohibited citations, the engineering decision
and the intake action. Errors name a field or a count, never scenario text.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from evals_dev.metrics.ranking import article_of

ENV_VAR = 'BATATIS_JUDGE_DIR'
DEFAULT_DIR = '~/batatis-judge'
CODE_DOCUMENT = 'NBC(AE) 2023 p2'
INTAKE_ACTIONS = ('ask', 'proceed_conditionally', 'redirect')
ENGINEERING = ('yes', 'no', 'depends')
SPLITS = ('dev', 'test')
_ID = re.compile(r'^ab-\d{3}$')


class DatasetError(Exception):
    """The judge folder is missing or malformed. The message never contains scenario text."""


@dataclass(frozen=True)
class Scenario:
    id: str
    split: str
    confidence: str
    description: str
    must_cite_b: tuple[str, ...]           # required Division B articles, article level
    should_cite_b: tuple[str, ...]
    forbidden_b: tuple[str, ...]           # prohibited Division B articles (specific, not wildcard)
    engineering_required: str
    intake_action: str
    out_of_scope: bool
    category: str = ''
    applicant_type: str = ''

    @property
    def part_group(self) -> str:
        parts = {int(a.split('.')[0]) for a in self.must_cite_b}
        if not parts:
            return 'none'
        return 'part9' if parts == {9} else ('mixed' if 9 in parts else 'other')


@dataclass(frozen=True)
class JudgeDir:
    root: Path
    evals: Path
    scenarios: Path
    state: Path
    manifest: dict = field(default_factory=dict)

    @property
    def manifest_sha256(self) -> str | None:
        path = self.evals / 'dataset-manifest.json'
        return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def judge_dir(explicit: str | os.PathLike | None = None) -> JudgeDir:
    """Resolve the judge folder from the argument, ``BATATIS_JUDGE_DIR`` or ``~/batatis-judge``."""
    raw = explicit or os.environ.get(ENV_VAR) or DEFAULT_DIR
    root = Path(raw).expanduser().resolve()
    if not root.is_dir():
        raise DatasetError('judge folder not found (set BATATIS_JUDGE_DIR)')
    evals = root / 'evals' if (root / 'evals').is_dir() else root
    scenarios = evals / 'scenarios'
    if not scenarios.is_dir():
        raise DatasetError('judge folder has no scenarios directory')
    manifest_path = evals / 'dataset-manifest.json'
    manifest = {}
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text())
        except (OSError, ValueError):
            raise DatasetError('dataset-manifest.json is not valid JSON') from None
    return JudgeDir(root=root, evals=evals, scenarios=scenarios, state=root / 'state', manifest=manifest)


def _citations(entries, *, specific_only: bool = False) -> tuple[str, ...]:
    out: list[str] = []
    for e in entries or []:
        if not isinstance(e, dict) or e.get('document') != CODE_DOCUMENT or e.get('division') != 'B':
            continue
        provision = e.get('provision')
        if specific_only and (not provision or '*' in str(provision)):
            continue
        art = article_of(provision)
        if art and art not in out:
            out.append(art)
    return tuple(out)


def parse_scenario(data: dict) -> Scenario:
    """One scenario record. Raises ``DatasetError`` naming the missing or invalid field."""
    for key in ('id', 'split', 'description', 'gold'):
        if key not in data:
            raise DatasetError(f'scenario is missing {key}')
    gold = data['gold']
    if not isinstance(gold, dict):
        raise DatasetError('scenario gold must be an object')
    sid = data['id']
    if not isinstance(sid, str) or not _ID.match(sid):
        raise DatasetError('scenario id is not ab-NNN')
    if data['split'] not in SPLITS:
        raise DatasetError('scenario split is not dev or test')
    if not isinstance(data['description'], str) or not data['description'].strip():
        raise DatasetError('scenario description is empty')
    action, eng = gold.get('intake_action'), gold.get('engineering_required')
    if action not in INTAKE_ACTIONS:
        raise DatasetError('scenario gold.intake_action is not ask, proceed_conditionally or redirect')
    if eng not in ENGINEERING:
        raise DatasetError('scenario gold.engineering_required is not yes, no or depends')
    must, should = _citations(gold.get('must_cite')), _citations(gold.get('should_cite'))
    # A prohibition names a sentence (typically an exception whose condition the facts rule out). At article level it
    # can collapse onto the required article itself, so only articles disjoint from the citations stay prohibited.
    forbidden = tuple(a for a in _citations(gold.get('must_not_cite'), specific_only=True)
                      if a not in must and a not in should)
    return Scenario(
        id=sid, split=data['split'], confidence=data.get('confidence', 'high'), description=data['description'],
        must_cite_b=must, should_cite_b=should, forbidden_b=forbidden,
        engineering_required=eng, intake_action=action, out_of_scope=bool(gold.get('out_of_scope')),
        category=str(data.get('category', '')), applicant_type=str(data.get('applicant_type', '')))


def load_scenarios(jd: JudgeDir, split: str | None = None) -> list[Scenario]:
    """All scenarios (or one split), in id order. The files are JSON syntax with a .yaml extension."""
    out: list[Scenario] = []
    seen: set[str] = set()
    for path in sorted(jd.scenarios.glob('ab-*.yaml')):
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            raise DatasetError('a scenario file is not valid JSON') from None
        scenario = parse_scenario(data)
        if scenario.id in seen:
            raise DatasetError('duplicate scenario id')
        seen.add(scenario.id)
        out.append(scenario)
    if split is not None:
        out = [s for s in out if s.split == split]
    return out


def headline_exclusions(jd: JudgeDir) -> set[str]:
    """Scenario ids the dataset says to leave out of headline numbers (low-confidence gold)."""
    listed = jd.manifest.get('headline_test_exclusions') or []
    return {x for x in listed if isinstance(x, str)}
