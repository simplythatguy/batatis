"""Cached read-only navigation and provision context for NBC(AE) 2023 p2."""
from __future__ import annotations

import json
import re
from contextlib import closing
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from codedb import ids, store

from .codes import Codes
from .section_c import section_c_rows

EDITION = 'NBC(AE) 2023, 2nd printing'


class TocArticle(BaseModel):
    id: str
    title: str


class TocSubsection(BaseModel):
    id: str
    title: str
    articles: list[TocArticle]


class TocSection(BaseModel):
    id: str
    title: str
    subsections: list[TocSubsection]
    articles: list[TocArticle]


class TocPart(BaseModel):
    part: int
    title: str | None
    sections: list[TocSection]


class CodeTOC(BaseModel):
    division: str
    edition: str = EDITION
    parts: list[TocPart]


class ContextNode(BaseModel):
    id: str
    level: str
    title: str | None


class ContextDefinition(BaseModel):
    code: str
    title: str | None


class ContextIntent(BaseModel):
    objective: str | None
    text: str


class ContextNote(BaseModel):
    id: str
    title: str | None
    excerpt: str


class ProvisionContext(ContextNode):
    citation: str
    pdf_page: int
    path: list[ContextNode]
    objectives: list[ContextDefinition]
    functions: list[ContextDefinition]
    attribution_status: Literal['direct', 'inherited', 'no-row']
    inherited_from: str | None
    intent: list[ContextIntent]
    intent_differs: bool
    intent_differs_detail: str | None
    notes: list[ContextNote]
    references: list[str]
    referenced_by: list[str]


@lru_cache(maxsize=12)
def table_of_contents(db_path: Path, division: str = 'B') -> CodeTOC:
    """Code order comes from sort_key. Only stored part headings can supply part titles.

    The current schema's docs/meta contain edition/build metadata, not part headings, and
    provisions currently starts at section level. Those parts therefore have null titles.
    """
    with closing(store.connect(db_path)) as con:
        records = [dict(row) for row in con.execute(
            "SELECT id, level, part, section, subsection, title FROM provisions "
            "WHERE doc='NBC-AE' AND division=? AND level IN ('part','section','subsection','article') "
            "ORDER BY sort_key", (division,))]
    parts: dict[int, TocPart] = {}
    sections: dict[str, TocSection] = {}
    subsections: dict[str, TocSubsection] = {}
    for row in records:
        part = parts.setdefault(row['part'], TocPart(part=row['part'], title=None, sections=[]))
        if row['level'] == 'part':
            part.title = row['title']
        elif row['level'] == 'section':
            section = TocSection(id=row['id'], title=row['title'] or '', subsections=[], articles=[])
            sections[row['id']] = section
            part.sections.append(section)
    for row in records:
        if row['level'] == 'subsection':
            subsection = TocSubsection(id=row['id'], title=row['title'] or '', articles=[])
            subsections[row['id']] = subsection
            sections[row['section']].subsections.append(subsection)
    for row in records:
        if row['level'] == 'article':
            parent = subsections.get(row['subsection']) or sections[row['section']]
            parent.articles.append(TocArticle(id=row['id'], title=row['title'] or ''))
    return CodeTOC(division=division, parts=list(parts.values()))


# Full dotted identifiers only; note identifiers (A-...) are handled by note_links.
# A missing target is discarded rather than shortened to an existing ancestor.
_REFERENCE = re.compile(
    r'(?<![\w.-])\d{1,2}(?:\.\d{1,3}){1,3}\.?(?:\s*\(\d{1,2}\)'
    r'(?:\s*\([a-z]{1,2}\)(?:\s*\([ivx]+\))?)?)?(?![\w(]|\.(?:\d|\())')


def _references(text: str, existing: frozenset[str]) -> list[str]:
    found = {}
    for match in _REFERENCE.finditer(text or ''):
        try:
            pid = ids.canon(match.group())
        except ValueError:
            continue
        if pid in existing:
            found[pid] = None
    return list(found)


@lru_cache(maxsize=12)
def _reference_index(db_path: Path, division: str) -> tuple[frozenset[str], dict[str, list[str]]]:
    with closing(store.connect(db_path)) as con:
        records = con.execute("SELECT id, text FROM provisions WHERE doc='NBC-AE' AND division=? "
                              "ORDER BY sort_key", (division,)).fetchall()
    existing = frozenset(row['id'] for row in records)
    reverse: dict[str, list[str]] = {}
    for row in records:
        targets = {}
        for ref in _references(row['text'], existing):
            targets[ref] = None
            # An article/sentence's backlinks include citations of its descendants.
            for ancestor in ids.parse(ref).ancestors():
                if ancestor.level in ('article', 'sentence'):
                    targets[str(ancestor)] = None
        for ref in targets:
            if row['id'] != ref:
                reverse.setdefault(ref, []).append(row['id'])
    return existing, reverse


def provision_context(rec: dict, codes: Codes) -> ProvisionContext:
    """Use Section C's exact rows, including its clause inheritance and intent filtering.

    Article context is the union of its Section C sentence rows. Higher headings and
    Divisions A/C have no Section C attribution rows.
    """
    pid, division = rec['id'], rec['division']
    has_rows = rec['level'] in ('sentence', 'clause', 'subclause') or (
        rec['level'] == 'article' and any(child['level'] == 'sentence' for child in rec['children']))
    rows = section_c_rows([pid], codes) if division == 'B' and has_rows else []
    objectives, functions, intents = {}, {}, {}
    for row in rows:
        for pair in row.pairs:
            objectives.setdefault(pair.objective, ContextDefinition(code=pair.objective, title=pair.objective_text))
            functions.setdefault(pair.function, ContextDefinition(code=pair.function, title=pair.function_text))
        for block in row.intents:
            for text in block.intents:
                intents.setdefault((block.objective, text), ContextIntent(objective=block.objective, text=text))
    status = 'no-row'
    if any(row.attribution_status == 'direct' for row in rows):
        status = 'direct'
    elif any(row.attribution_status == 'inherited from parent' for row in rows):
        status = 'inherited'
    inherited = list(dict.fromkeys(row.attributed_via for row in rows if row.attributed_via))
    differences = [{'id': row.provision_id, 'only_in_intent': row.only_in_intent, 'only_in_ae': row.only_in_ae}
                   for row in rows if row.differs]
    path = [ContextNode(id=pid, level=rec['level'], title=rec['title'])]
    seen = {pid}
    parent_id = rec['parent_id']
    with closing(store.connect(codes.db_path)) as con:
        while parent_id and parent_id not in seen:
            parent = con.execute("SELECT id, level, title, parent_id FROM provisions "
                                 "WHERE doc='NBC-AE' AND division=? AND id=?", (division, parent_id)).fetchone()
            if parent is None:
                break
            seen.add(parent['id'])
            path.append(ContextNode(id=parent['id'], level=parent['level'], title=parent['title']))
            parent_id = parent['parent_id']
    existing, reverse = _reference_index(codes.db_path, division)
    return ProvisionContext(
        id=pid, level=rec['level'], title=rec['title'], citation=rec['citation'], pdf_page=rec['pdf_page'],
        path=list(reversed(path)), objectives=list(objectives.values()), functions=list(functions.values()),
        attribution_status=status, inherited_from=inherited[0] if status == 'inherited' and len(inherited) == 1 else None,
        intent=list(intents.values()), intent_differs=bool(differences),
        intent_differs_detail=json.dumps(differences) if differences else None,
        notes=[ContextNote(id=note['note_id'], title=note['title'], excerpt=' '.join((note['text'] or '').split())[:320])
               for note in rec['notes']],
        references=_references(rec['text'], existing), referenced_by=reverse.get(pid, [])[:20])
