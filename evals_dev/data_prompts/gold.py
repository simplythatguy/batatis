"""Reference items per case, derived only from the case metadata and the attachments, never from a run.

Four kinds of judged or checked items:
  F  a source fact (source.json) that a reader of the prompt and attachments can find (text available)
  R  a review point (evaluation.json review_focus)
  B  a boundary statement built from the metadata: outside-Alberta records, other safety-codes disciplines,
     and code editions other than NBC(AE) 2023
  A  an NBC(AE) 2023 provision the source names, which resolves in the code database
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from .corpus import Case, load
from .texts import pages

TIER_KIND = {
    'Calgary / Edmonton': 'alberta',
    'Other Alberta / province-wide': 'alberta',
    'Canadian supporting evidence': 'canada_supporting',
    'Outside Alberta - attachment comparison only': 'outside_alberta',
}
RECORD = {
    'actual_application': 'application record', 'appeal_decision': 'appeal decision',
    'documented_case_summary': 'case summary', 'documented_design_study': 'design study',
    'issued_variance': 'issued variance', 'product_evidence': 'product evidence',
    'published_worked_example': 'published worked example', 'regulatory_guidance': 'regulatory guidance',
    'research_evidence': 'research evidence',
}
OTHER_CODES = (
    (re.compile(r'fire code|\bNFC\b|NFC\(AE\)', re.I), 'Fire Code'),
    (re.compile(r'plumbing code|\bNPC\b', re.I), 'Plumbing Code'),
    (re.compile(r'elevating devices', re.I), 'Elevating Devices requirements'),
    (re.compile(r'occupational health and safety', re.I), 'Occupational Health and Safety requirements'),
)
AVAILABLE_AT = 0.6
LABEL_RANGE = (0.3, 0.6)        # overlap band decided once by availability.json
LABELS = Path(__file__).with_name('availability.json')


@dataclass(frozen=True)
class Item:
    id: str              # F1, R2, B1 ... unique within a case
    kind: str            # F, R, B
    text: str


def edition_status(code_edition: str) -> str:
    """current (NBC(AE) 2023), historical (an earlier Alberta or national edition), or unknown."""
    text = code_edition or ''
    years = re.findall(r'\b(19[5-9]\d|20[0-4]\d)\b', text)
    alberta = re.search(r'Alberta|\(AE\)|\bAE\b|NBC-?2019AE', text, re.I)
    if years and years[0] == '2023' and alberta:
        return 'current'
    if years:
        return 'historical'
    return 'unknown'


def boundary_items(case: Case) -> list[Item]:
    kind = TIER_KIND[case.tier]
    record = RECORD.get(case.case_type, case.case_type.replace('_', ' '))
    out: list[str] = []
    if kind == 'outside_alberta':
        out.append(f'States that the record comes from {case.jurisdiction}, outside Alberta, and does not treat its '
                   'code provisions, interpretations or outcome as NBC(AE) requirements or as an Alberta approval.')
    else:
        if kind == 'canada_supporting':
            out.append(f'Treats the attachment as supporting {record} only, not as an Alberta approval, an '
                       'acceptance, or a finding that a project complies.')
        status = edition_status(case.code_edition)
        if status == 'historical':
            out.append('Flags that the source relies on a code edition other than NBC(AE) 2023 (the source states: '
                       f'"{case.code_edition}") and that the edition governing a current application must be confirmed.')
        elif status == 'unknown':
            out.append('Flags that the source does not establish which code edition applies and asks which edition '
                       'governs.')
        others = [name for pattern, name in OTHER_CODES if pattern.search(case.code_edition or '')]
        if others:
            out.append(f'Keeps the {" and ".join(others)} explicit as a discipline separate from the NBC(AE) '
                       'building-code requirements.')
    return [Item(f'B{i}', 'B', text) for i, text in enumerate(out, start=1)]


_STOP = set('''the and for with that this from are was were has have had not but its into than then they them their
there these those which while where when what who whom will would shall should could can may might must also such
each other only any all both more most some per via upon within without about above below under over between
does did done being been being out off own same very just case record report source attachment attached document
documents page pages pdf states stated state says said shows show listed lists list includes include including'''.split())
_TOKEN = re.compile(r"\d+(?:[.,]\d+)?|[a-z][a-z'\-]{2,}")


def _norm(text: str) -> str:
    text = unicodedata.normalize('NFKC', text or '').lower()
    return text.replace('’', "'").replace('–', '-').replace('—', '-')


def tokens(text: str) -> set[str]:
    return {t.strip("'-") for t in _TOKEN.findall(_norm(text)) if t not in _STOP and len(t.strip("'-")) >= 2}


@cache
def _windows(case_id: str) -> tuple[frozenset[str], ...]:
    case = next(c for c in load() if c.id == case_id)
    out = [frozenset(tokens(case.prompt))]
    for attachment in case.attachments:
        texts = pages(case, attachment)
        sets = [tokens(t) for t in texts]
        out += [frozenset(s) for s in sets]
        out += [frozenset(a | b) for a, b in zip(sets, sets[1:])]
    return tuple(out)


def availability(case: Case, text: str) -> float:
    """Share of the fact's content words and numbers found on one page (or two adjacent pages) or the prompt."""
    want = tokens(text)
    if not want:
        return 0.0
    return max((len(want & window) / len(want) for window in _windows(case.id)), default=0.0)


@cache
def _labels() -> dict:
    return json.loads(LABELS.read_text())['labels'] if LABELS.exists() else {}


def available(case: Case, index: int, score: float) -> bool:
    """Overlap of 0.6 or more counts; under 0.3 does not; in between, the frozen label decides."""
    if score >= AVAILABLE_AT:
        return True
    if score < LABEL_RANGE[0]:
        return False
    return bool(_labels().get(case.id, {}).get(str(index)))


def fact_items(case: Case) -> tuple[list[Item], list[tuple[str, float]]]:
    """(available facts as F items, every fact with its availability score)."""
    scored = [(f.text, availability(case, f.text)) for f in case.facts]
    items = [Item(f'F{i}', 'F', text) for i, (text, score) in enumerate(scored, start=1)
             if available(case, i - 1, score)]
    return items, scored


def focus_items(case: Case) -> list[Item]:
    return [Item(f'R{i}', 'R', text) for i, text in enumerate(case.focus, start=1)]


_ARTICLE = re.compile(r'(?<![\d.])(\d{1,2})\.(\d{1,2})\.(\d{1,2})\.(\d{1,3})(?![\d])')
_NOT_NBC = re.compile(r'fire code|\bNFC\b|plumbing|\bNPC\b|NFPA|\bOBC\b|BC Building Code|BCBC|Ontario', re.I)


def article_gold(case: Case, codes) -> list[str]:
    """Division B articles the source names that resolve in NBC(AE) 2023 2nd printing (Alberta and Canadian tiers)."""
    if TIER_KIND[case.tier] == 'outside_alberta':
        return []
    text = ' '.join([*(f.text for f in case.facts), case.known_outcome, *case.focus])
    found: list[str] = []
    for sentence in re.split(r'(?<=[.;])\s+(?=[A-Z(])', text):
        if _NOT_NBC.search(sentence):
            continue
        for m in _ARTICLE.finditer(sentence):
            before = sentence[max(0, m.start() - 14):m.start()]
            if re.search(r'Div(?:ision|\.)?\s*[AC]\b', before):
                continue
            article = '.'.join(m.groups()) + '.'
            hit = codes.provision(article, 'B')
            if hit and hit.get('level') == 'article' and article not in found:
                found.append(article)
    return found


@dataclass(frozen=True)
class Gold:
    case_id: str
    items: tuple[Item, ...]
    articles: tuple[str, ...]
    facts_total: int
    facts_unavailable: tuple[str, ...]


def gold(case: Case, codes) -> Gold:
    facts, scored = fact_items(case)
    items = [*facts, *focus_items(case), *boundary_items(case)]
    return Gold(case.id, tuple(items), tuple(article_gold(case, codes)), len(scored),
                tuple(text for i, (text, score) in enumerate(scored) if not available(case, i, score)))
