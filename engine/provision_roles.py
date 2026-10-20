"""Record which confirmed provisions the applicant departs from.

``POST /cases/{id}/section-d`` is the path that stores a user-added or identified
provision. Each id in that request is ``departure``. Article and Sentence
references in the text ``codes.provision`` returns (an article lookup already
includes its sentences), and references reached from that chain, are appended
as ``citing``. A citing provision stays on the case for Section C and does not
take an evidence gap.

Nothing here decides that a design complies, and it does not invent a provision
the code text did not name and the database did not resolve.
"""
from __future__ import annotations

import re

from codedb import ids

from .models import Case, Fact, Source
from .section_c import section_c_rows

# One hop is the provision the departure names. Further hops are that chain.
_MAX_DEPTH = 4
_MAX_CITING = 16
_ROMAN = r'i|ii|iii|iv|v|vi|vii|viii|ix|x|xi|xii'
_NAMED = re.compile(
    r'\b(?P<kind>Articles?|Sentences?|Clauses?)\s+'
    r'(?P<id>\d+\.\d+\.\d+\.\d+\.'
    rf'(?:\(\d+\))?(?:\([a-z]{{1,2}}\))?(?:\((?:{_ROMAN})\))?)')
_AND_SENTENCE = re.compile(r'\s+and\s+\((?P<n>\d+)\)')
_RELATIVE_SENTENCE = re.compile(r'\bSentences?\s+\((?P<n>\d+)\)')


def _article(provision_id: str) -> str | None:
    try:
        parsed = ids.parse(provision_id)
    except ValueError:
        return None
    if len(parsed.nums) != 4:
        return None
    return str(ids.Pid(parsed.nums))


def _canon(provision_id: str) -> str | None:
    try:
        return ids.canon(provision_id)
    except ValueError:
        return None


def _under(provision_id: str, roots: set[str]) -> bool:
    if provision_id in roots:
        return True
    try:
        parsed = ids.parse(provision_id)
    except ValueError:
        return False
    return any(str(ancestor) in roots for ancestor in parsed.ancestors())


def referenced_ids(text: str, current_id: str) -> list[str]:
    """Provision ids an Article or Sentence reference names, in text order.

    ``Sentence (2)`` is the same article as ``current_id``. ``and (3)`` continues
    the sentence just named. A table number is not a provision.
    """
    found: list[str] = []

    def add(provision_id: str | None) -> None:
        if not provision_id or provision_id == current_id or provision_id in found:
            return
        found.append(provision_id)

    for match in _NAMED.finditer(text or ''):
        named = _canon(match.group('id'))
        add(named)
        if named and match.group('kind').lower().startswith('sentence') and '(' in named:
            extra = _AND_SENTENCE.match(text, match.end())
            article = _article(named)
            if extra and article:
                add(_canon(f'{article}({extra.group("n")})'))
    article = _article(current_id)
    if article:
        for match in _RELATIVE_SENTENCE.finditer(text or ''):
            add(_canon(f'{article}({match.group("n")})'))
    return found


def _lookup(codes, provision_id: str):
    try:
        return codes.provision(provision_id, 'B')
    except (ValueError, KeyError):
        return None


def _resolves(record: dict | None) -> bool:
    if not record:
        return False
    level = record.get('level')
    if level in ('section', 'subsection', 'part'):
        return False
    if level == 'article':
        return any(child.get('level') == 'sentence' for child in record.get('children') or [])
    return level in ('sentence', 'clause', 'subclause')


def _section_c_accepts(codes, provision_id: str) -> bool:
    """True when this id can sit on the case without failing the Section C lookup."""
    if not _resolves(_lookup(codes, provision_id)):
        return False
    try:
        section_c_rows([provision_id], codes)
    except (KeyError, ValueError):
        return False
    return True


def citing_chain(codes, departures: list[str]) -> list[tuple[str, str]]:
    """``(citing id, provision whose text named it)``, shortest chain first."""
    roots = set(departures)
    found: list[tuple[str, str]] = []
    seen = set(departures)
    frontier = list(departures)
    for _depth in range(_MAX_DEPTH):
        nxt: list[str] = []
        for provision_id in frontier:
            record = _lookup(codes, provision_id)
            if record is None:
                continue
            for ref in referenced_ids(record.get('text') or '', provision_id):
                if ref in seen or _under(ref, roots):
                    continue
                if not _section_c_accepts(codes, ref):
                    continue
                seen.add(ref)
                found.append((ref, provision_id))
                nxt.append(ref)
                if len(found) >= _MAX_CITING:
                    return found
        frontier = nxt
        if not frontier:
            break
    return found


def _departure_fact(provision_id: str) -> Fact:
    return Fact(field='provision_role', value=f'departure:{provision_id}', kind='pointed', status='confirmed',
                source=Source(type='user_text', ref='applicant', quote=provision_id))


def _citing_fact(provision_id: str, via: str) -> Fact:
    return Fact(field='provision_role', value=f'citing:{provision_id}', kind='exact', status='confirmed',
                source=Source(type='code', ref=via, quote=provision_id))


def record_provision_roles(case: Case, codes, selected: list[str]) -> None:
    """Store ``selected`` as the departure and append the citing chain.

    Replaces earlier ``provision_role`` facts. The applicant's ids stay
    ``departure`` even when a reference also names them.
    """
    departures: list[str] = []
    for raw in selected:
        provision_id = ids.canon(raw)
        if provision_id not in departures:
            departures.append(provision_id)
    citing = citing_chain(codes, departures)
    case.provisions = departures + [provision_id for provision_id, _via in citing]
    case.facts = [fact for fact in case.facts if fact.field != 'provision_role']
    case.facts.extend(_departure_fact(provision_id) for provision_id in departures)
    case.facts.extend(_citing_fact(provision_id, via) for provision_id, via in citing)
