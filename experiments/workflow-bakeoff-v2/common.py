"""Shared paths, case loading and CodeDB helpers for the second workflow bakeoff."""
from __future__ import annotations

import json
import os
import re
import sys
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RUNS = Path(os.environ.get('BAKEOFF2_RUNS') or ROOT / '.data' / 'bakeoff-v2')      # requests and responses stay out of git
DB = ROOT / 'codedb' / 'build' / 'codedb.sqlite'
CASES_FILE = ROOT / 'docs' / 'research' / '2026-10-23-elephant' / 'cases-alberta.json'

PID = re.compile(r'\b\d{1,2}\.\d{1,2}\.\d{1,2}\.\d{1,2}\.(?:\(\d+\))*(?:\([a-z]\))*')
CITED = re.compile(r'\b(?:Sentences?|Articles?|Clauses?|Subsections?|Sections?)\s+\d{1,2}\.\d[\d.()a-z ,and-]*', re.I)
LOOSE_ID = re.compile(r'\b\d{1,2}\.\d{1,2}\.\d{1,2}(?:\.\d{1,2})?\.?(?:\s*\(\d+\))*(?:\([a-z]\))*')
ALTERNATIVE_TYPES = {'variance', 'alternative-solution-example'}


def load_cases() -> list[dict]:
    cases = json.loads(CASES_FILE.read_text())
    for case in cases:
        case['gold_path'] = 'alternative' if case['type'] in ALTERNATIVE_TYPES else None
    return cases


def redact(text: str) -> str:
    """Remove code references so a simulated applicant knows the project, not the regulator's answer."""
    text = CITED.sub('[code reference removed]', text or '')
    return LOOSE_ID.sub('[code reference removed]', text)


def article_of(pid: str) -> str:
    """'9.10.15.5.(8)(a)' -> '9.10.15.5.'"""
    m = re.match(r'(\d{1,2}\.\d{1,2}\.\d{1,2}\.\d{1,2}\.)', (pid or '').strip())
    return m.group(1) if m else (pid or '').strip()


def normalize_pid(raw: str) -> str:
    raw = (raw or '').strip().replace(' ', '')
    m = re.match(r'^(\d{1,2})\.(\d{1,2})\.(\d{1,2})\.(\d{1,2})\.?((?:\(\d+\))*(?:\([a-z]\))*)$', raw)
    if not m:
        return raw
    return f'{m.group(1)}.{m.group(2)}.{m.group(3)}.{m.group(4)}.{m.group(5)}'


@lru_cache(maxsize=1)
def codes():
    from engine.codes import Codes
    return Codes(DB)


@lru_cache(maxsize=1)
def article_map() -> dict[str, dict]:
    from engine.identify.corpus import articles
    return articles(DB)


def is_division_b(pid: str) -> bool:
    return codes().provision(normalize_pid(pid), 'B') is not None


def section_c_summary(pid: str) -> dict | None:
    """The deterministic Section C rows for one article or sentence, reduced to codes."""
    from engine.section_c import section_c_rows
    try:
        rows = section_c_rows([normalize_pid(pid)], codes())
    except KeyError:
        return None
    objectives, functions, pairs, intents = set(), set(), set(), 0
    for row in rows:
        for pair in row.pairs:
            objectives.add(pair.objective)
            functions.add(pair.function)
            pairs.add(f'{pair.function}-{pair.objective}')
        intents += sum(len(block.intents) for block in row.intents)
    return {'provision': normalize_pid(pid), 'sentences': [r.provision_id for r in rows],
            'objectives': sorted(objectives), 'functions': sorted(functions), 'pairs': sorted(pairs),
            'intent_statements': intents,
            'statuses': sorted({r.attribution_status for r in rows})}


def article_text(pid: str, limit: int | None = None) -> str:
    from engine.identify.corpus import card
    art = article_map().get(article_of(pid))
    return card(art, limit) if art else ''


def read_json(path: Path):
    return json.loads(Path(path).read_text())


def write_json(path: Path, value) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=1, ensure_ascii=False))
    tmp.replace(path)
