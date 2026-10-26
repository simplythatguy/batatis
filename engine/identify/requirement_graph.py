"""Explicit source references, retaining direction and the exact originating passage.

Edges are discovery candidates. In particular a reverse reference is not proof
that the referencing article applies to the current proposal.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from codedb.ids import canon
from engine.models_identify import RequirementEvidence, RequirementGap

from .requirement_corpus import Corpus, Key, qualified

_PID = re.compile(r'(?<![\w.\-])\d{1,2}(?:\.\d{1,3}){1,3}\.?(?:\s*\(\d{1,3}\)(?:\s*\([a-z]{1,4}\)){0,2})?')
_SUFFIX_DIV = re.compile(r'^\s*(?:of|in)\s+(?:the\s+)?Div(?:ision|\.)?\s+([ABC])\b', re.I)
_PREFIX_DIV = re.compile(r'Div(?:ision|\.)?\s+([ABC])\s*[,;:]?\s*(?:(?:Articles?|Sentences?|Clauses?|Subclauses?|Sections?|Subsections?)\s+)?$', re.I)
_EXTERNAL = re.compile(
    r'\b(?:National Fire Code(?:\s+of Canada)?|National Energy Code(?:\s+of Canada for Buildings)?|'
    r'NFC(?:\s*\(AE\))?|NECB|CAN/[^\s,;]+|CSA(?:\s+[A-Z][\w./-]*)?|'
    r'NFPA(?:\s+\d+[A-Z]?)?|ULC(?:\s*[-–]?\s*[A-Z]?\d+[\w.-]*)?|'
    r'ASTM(?:\s+[A-Z]\d+[\w.-]*)?|ISO(?:\s+\d+[\w:-]*)?)(?=$|[^\w])', re.I)
_LOCAL = re.compile(r'\b(?P<kind>Sentences?|Clauses?|Subclauses?)\s+'
                    r'(?P<items>\(\d+\)(?:\([a-z]{1,4}\)){0,2}'
                    r'(?:(?:\s*,?\s*(?:and|or|to)?\s*)\(\d+\)(?:\([a-z]{1,4}\)){0,2})*)', re.I)
_LOCAL_ITEM = re.compile(r'\(\d+\)(?:\([a-z]{1,4}\)){0,2}')
_TABLE = re.compile(r'\bTable\s+[A-Z]?-?\d+(?:\.\d+){1,3}\.(?:[-–][A-Z])?', re.I)
_APPENDIX = re.compile(r'\b(?:Appendix\s+[A-Z]|Appendices\b|Span Tables|Fire and Sound Resistance Tables)\b', re.I)
_NOTE = re.compile(r'\bNote\s+(A-(?:Table\s+)?\d+(?:\.\d+)*\.(?:\(\d+\))?(?:\([a-z]{1,4}\)){0,2})', re.I)
_JOIN = re.compile(r'\s*(?:(?:,|\band\b|\bor\b|\bto\b|\bthrough\b)\s*)+'
                   r'(?:(?:Articles?|Sentences?|Clauses?|Subclauses?|Sections?|Subsections?)\s+)?', re.I)


@dataclass(frozen=True)
class Reference:
    raw: str
    pid: str
    division: str | None
    external: str | None = None


def references(text: str, *, division: str | None = None, article: str | None = None) -> list[Reference]:
    out = []
    matches = list(_PID.finditer(text))
    groups = []
    for match in matches:
        if groups and _JOIN.fullmatch(text[groups[-1][-1].end():match.start()]):
            groups[-1].append(match)
        else:
            groups.append([match])
    context = {m.start(): (group[0].start(), group[-1].end()) for group in groups for m in group}
    for match in matches:
        raw = match.group()
        if re.search(r'\bTables?\s*$', text[max(0, match.start() - 12):match.start()], re.I):
            continue
        # A decimal without code-reference context is not an article. Four-part
        # ids may be entered anywhere, including after a long description.
        if raw.split('(')[0].rstrip('.').count('.') < 3 and not re.search(
                r'\b(?:Sections?|Subsections?|Articles?)\s*$', text[max(0, match.start() - 25):match.start()], re.I):
            continue
        try:
            pid = canon(raw)
        except ValueError:
            continue
        group_start, group_end = context[match.start()]
        before, after = text[max(0, group_start - 100):group_start], text[group_end:group_end + 160]
        suffix, prefix = _SUFFIX_DIV.search(after), _PREFIX_DIV.search(before)
        div = (suffix or prefix).group(1).upper() if suffix or prefix else division
        # Do not reinterpret a foreign-code identifier as an NBC identifier.
        external = re.search(r'^\s*of\s+(?:the\s+)?(' + _EXTERNAL.pattern + ')', after, re.I)
        leading = list(_EXTERNAL.finditer(before))
        foreign = external.group(1) if external else None
        if not foreign and leading and re.fullmatch(
                r'\s*(?:[-–]?\s*20\d{2}\s*)?(?:(?:p[12]|2nd printing|second printing)\s*)?'
                r'[,;:]?\s*(?:(?:Article|Sentence|Clause|Section|Subsection)s?\s+)?',
                before[leading[-1].end():], re.I):
            foreign = leading[-1].group()
        out.append(Reference(raw, pid, div, foreign))
    if article:
        for match in _LOCAL.finditer(text):
            parent = article
            div = division
            external_article = re.match(r'\s+of\s+Article\s+(' + _PID.pattern + ')', text[match.end():], re.I)
            if external_article:
                try:
                    parent = canon(external_article[1])
                except ValueError:
                    continue
                qualifier = _SUFFIX_DIV.search(text[match.end() + external_article.end():])
                if qualifier:
                    div = qualifier[1].upper()
            # "to" ranges are expanded only for numeric sentences of this article.
            items = _LOCAL_ITEM.findall(match['items'])
            if 'to' in match['items'].lower() and len(items) == 2 and all(re.fullmatch(r'\(\d+\)', x) for x in items):
                lo, hi = (int(x[1:-1]) for x in items)
                # Existing source rows, not synthetic ranges, determine targets below.
                items = [f'({i})' for i in range(lo, min(hi, 999) + 1)] if 0 < lo <= hi <= 999 else items
            for item in items:
                out.append(Reference(match.group(), parent + item, div))
    return list(dict.fromkeys(out))


def external_gaps(text: str, *, evidence: RequirementEvidence | None = None,
                  origin: str | None = None) -> list[RequirementGap]:
    gaps = []
    for match in _EXTERNAL.finditer(text):
        label = match.group()
        lower = label.lower()
        code = ('fire_code_unavailable' if 'fire code' in lower or lower.startswith('nfc') else
                'energy_code_unavailable' if 'energy code' in lower or lower.startswith('necb') else
                'referenced_standard_unavailable')
        gaps.append(RequirementGap(code=code, reference=label, from_requirement=origin, evidence=evidence,
                                   message='This referenced source is outside the verified NBC(AE) requirement corpus; its contents were not identified.'))
    for pattern, code in ((_TABLE, 'table_content_unavailable'), (_APPENDIX, 'appendix_content_unavailable')):
        for match in pattern.finditer(text):
            gaps.append(RequirementGap(code=code, reference=match.group(), from_requirement=origin, evidence=evidence,
                                       message='This referenced content is not fully available as parsed requirements; consult the source PDF.'))
    return gaps


@dataclass(frozen=True)
class Edge:
    origin: Key
    target: Key
    evidence: RequirementEvidence
    reference: str


@dataclass
class Graph:
    forward: dict[Key, list[Edge]]
    reverse: dict[Key, list[Edge]]
    gaps: dict[Key, list[RequirementGap]]


def build(corpus: Corpus) -> Graph:
    forward: dict[Key, list[Edge]] = defaultdict(list)
    reverse: dict[Key, list[Edge]] = defaultdict(list)
    gaps: dict[Key, list[RequirementGap]] = defaultdict(list)
    notes = {(n['division'], n['note_id']): n for n in corpus.notes}
    # A reference is parsed once per source passage. Duplicated clause text is
    # already contained in its full parent sentence in the corpus snapshot.
    passages = [(corpus.article_key(r['division'], r['id']), r) for r in corpus.passages
                if r.get('text') and r['level'] not in ('section', 'subsection')]
    passages.extend((key, note) for nkey, targets in corpus.note_articles.items()
                    if (note := notes.get(nkey)) for key in targets)
    seen = set()
    for origin, row in passages:
        if origin is None:
            continue
        evidence = corpus.evidence(row)
        text = row.get('text') or ''
        gaps[origin].extend(external_gaps(text, evidence=evidence, origin=qualified(origin)))
        for note in _NOTE.findall(text):
            if (origin[0], note) not in notes:
                gaps[origin].append(RequirementGap(
                    code='unresolved_note', reference=note, from_requirement=qualified(origin), evidence=evidence,
                    message='The source names a note that is not available in the extracted corpus.'))
        for ref in references(text, division=origin[0], article=origin[1]):
            if ref.external:
                continue
            targets = corpus.targets(ref.division or origin[0], ref.pid)
            if not targets:
                gaps[origin].append(RequirementGap(
                    code='unresolved_reference', reference=ref.raw, from_requirement=qualified(origin), evidence=evidence,
                    message='The source reference could not be resolved in the verified document and division.'))
            for target in targets:
                key = (origin, target, evidence.division, evidence.provision_id)
                if target == origin or key in seen:
                    continue
                seen.add(key)
                edge = Edge(origin, target, evidence, ref.raw)
                forward[origin].append(edge)
                # Explanatory notes may suggest forward context; only actual
                # normative references support a reverse dependency candidate.
                if not evidence.contextual:
                    reverse[target].append(edge)
    return Graph(dict(forward), dict(reverse), dict(gaps))
