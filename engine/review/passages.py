"""Visible applicant passages; ambiguous whole answers retain officer pointers."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..models_review import Pointer
from .pdf_reader import ReadFile

# Headings that start an applicant-written passage in an appendix or attachment.
TEXT_FIELDS = {
    'alternative_description': ('description of the proposed alternative', re.compile(
        r'^\s*(?:[A-Z]-\d+\s+)?(?:proposed alternative(?: solution)?|description of (?:the )?proposed alternative'
        r'(?: solution)?)\s*(?::|$)', re.I | re.M)),
    'rationale': ('rationale', re.compile(
        r'^\s*(?:[A-Z]-\d+\s+)?rationale(?: for (?:the )?(?:proposed )?(?:alternative(?: solution)?|variance))?'
        r'\s*(?::|$)', re.I | re.M)),
    'risk_assessment': ('risk assessment', re.compile(r'^\s*(?:[A-Z]-\d+\s+)?risk assessment\s*(?::|$)', re.I | re.M)),
    'mitigating_measures': ('mitigating measures', re.compile(
        r'^\s*(?:[A-Z]-\d+\s+)?mitigating measures\s*(?::|$)', re.I | re.M)),
    'assumptions_and_limits': ('assumptions and limits', re.compile(
        r'^\s*(?:[A-Z]-\d+\s+)?assumptions(?:,)?(?: and)? limit(?:s|ing factors|ations)?\s*(?::|$)', re.I | re.M)),
    'professional_name': ('responsible professional', re.compile(
        r'^\s*(?:responsible professional|registered professional)\s*(?::|$)', re.I | re.M)),
    'professional_qualifications': ('qualifications of the responsible professional', re.compile(
        r'^\s*(?:[A-Z]-\d+\s+)?qualifications(?: of (?:the )?responsible (?:people|professional|persons?))?\s*(?::|$)',
        re.I | re.M)),
    'maintenance_operation': ('maintenance and operation', re.compile(
        r'^\s*(?:[A-Z]-\d+\s+)?(?:maintenance(?: and (?:operation|commissioning))?|operation and maintenance)\s*(?::|$)', re.I | re.M)),
    'qualifications': ('qualifications of responsible people', re.compile(
        r'^\s*(?:[A-Z]-\d+\s+)?qualifications(?: of responsible people)?\s*(?::|$)', re.I | re.M)),
}
_STOP_LINE = re.compile(r'^\s*(?:[A-Z]-\d+\s|Applicant source:|NBC\(AE\)|[A-Z]\.\s+[A-Z]|Appendix page|'
                        r'(?:rationale|code analysis|testing procedures?|qualifications(?: of [a-z ]+)?|'
                        r'maintenance(?: and (?:operation|commissioning))?|operation and maintenance|commissioning)'
                        r'\s*(?::|$))', re.M | re.I)
# Rationale can discuss NBC(AE) in its own words. Only labelled boundaries end the passage;
# generic section labels and citation-shaped lines remain ambiguous rather than proving blankness.
_RATIONALE_STOP_LINE = re.compile(
    r'^[ \t]*(?:Applicant\s+source:|Appendix\s+page[ \t]+\d+|'
    r'(?:[A-Z]-\d+[ \t]+)?(?:'
    r'proposed\s+alternative(?:\s+solution)?|description\s+of\s+(?:the\s+)?proposed\s+alternative(?:\s+solution)?|'
    r'rationale(?:\s+for\s+(?:the\s+)?(?:proposed\s+)?(?:alternative(?:\s+solution)?|variance))?|'
    r'risk\s+assessment|mitigating\s+measures|assumptions,?(?:\s+and)?\s+limit(?:s|ing\s+factors|ations)?|'
    r'(?:responsible|registered)\s+professional|code\s+analysis|testing\s+procedures?|'
    r'qualifications(?:\s+of\s+(?:the\s+)?responsible\s+(?:people|professional|persons?)|[ \t]+of[ \t]+[a-z ]+)?|'
    r'maintenance(?:\s+and\s+(?:operation|commissioning))?|operation\s+and\s+maintenance|commissioning)[ \t]*(?::|$)|'
    r'(?P<ambiguous>[A-Z]-\d+[ \t]+|[A-Z]\.[ \t]+[A-Z]|'
    r'NBC\(AE\)[ \t]+\d{4}(?:[ \t]+p\d+)?[ \t]*,[ \t]*Div[ \t]+[ABC][ \t]*,))', re.M | re.I)
# Section headings the Batatis appendix prints; inside its own appendix they end a passage unambiguously.
_APPENDIX_SECTION = re.compile(r'(?:X\. Form values continued|N\. Fields marked not applicable|'
                               r'B\. Request for variance|P\. Alternative solution \(Div C 2\.3\.1\)|'
                               r'C\. Attributions to acceptable solutions|D\. Supporting documentation)')
_RUNNING_HEADER = re.compile(r'^Batatis appendix to SCC variance form - case [^\n]+\n')
_NO_RATIONALE = '(Not provided or not confirmed. No answer has been supplied by Batatis.)'
_ENGINEERING = re.compile(r'\b(?:engineering|registered professional|professional involvement)\s+(?:is\s+)?required'
                          r'\s*[:\-]?\s*(yes|no)\b', re.I)


@dataclass
class TextValue:
    status: str
    value: str
    file: str
    page: int | None
    quote: str | None
    pointers: list[Pointer] = field(default_factory=list)
    reason: str = ''


def _norm(text: str) -> str:
    return re.sub(r'\s+', ' ', text or '').strip()


def text_value(pages: list[tuple[str, int, str]], pattern, reads=None) -> TextValue:
    """Passage after a heading, up to the next heading or source line. Absent heading: not_found."""
    for file, page, text in pages:
        match = pattern.search(text)
        if not match:
            continue
        rest = text[match.end():]
        stop = _STOP_LINE.search(rest)
        for other in TEXT_FIELDS.values():
            hit = other[1].search(rest)
            if hit and (stop is None or hit.start() < stop.start()):
                stop = hit
        body = rest[:stop.start()] if stop else rest
        body = body.split('\n\n', 1)[0]
        value = _norm(body)
        read = (reads or {}).get(file)
        if read:
            raw_heading = match.group(0)
            heading = (_norm(raw_heading), match.start() + len(raw_heading) - len(raw_heading.lstrip()))
            end = None
            if stop:
                suffix = rest[stop.start():]
                end = (_norm(suffix.strip().split('\n', 1)[0]),
                       match.end() + stop.start() + len(suffix) - len(suffix.lstrip()))
            if read.passage_has_marks(page - 1, heading, end):
                return TextValue('not_found', '', file, page, None, [Pointer(file=file, page=page)],
                                 'This answer contains text or marks that could not be read confidently. Check the page.')
        return TextValue('present' if value else 'blank', value, file, page, value or _norm(match.group(0)))
    return TextValue('not_found', '', '', None, None)


def rationale_value(reads: list[ReadFile]) -> TextValue:
    """Aggregate all labelled passages; upload order never chooses an authoritative answer.

    A single passage keeps its existing reading. Consistent blanks remain an applicant gap.
    Other multiple candidates remain officer checks so every source can be retained in the
    finding's pointer list without inventing precedence or changing the field wire shape.
    """
    pattern = TEXT_FIELDS['rationale'][1]
    candidates = [_rationale_candidate(read, index, match)
                  for read in reads for index, page in enumerate(read.text_pages)
                  for match in pattern.finditer(page.text)]
    # Unreadable files/pages/regions cannot establish absence. Labelled passage regions
    # are checked above; graphics elsewhere on those pages do not belong to that passage.
    # A single readable rationale still remains present beside unrelated unreadable material.
    if not any(candidate.status == 'present' for candidate in candidates):
        for read in reads:
            labelled_pages = {pointer.page - 1 for candidate in candidates for pointer in candidate.pointers
                              if pointer.file == read.name and pointer.page is not None}
            unreadable = (list(range(read.pages)) or [None]) if read.role == 'unreadable' else [
                page for page in read.unreadable_pages() if page not in labelled_pages]
            for page in unreadable:
                pointer = Pointer(file=read.name, page=page + 1 if page is not None else None)
                candidates.append(TextValue(
                    'not_found', '', read.name, pointer.page, None, [pointer],
                    'A supplied file or page region could not be read. '
                    'Check it before treating the rationale as absent.'))
    if not candidates:
        return TextValue('not_found', '', '', None, None)
    candidates.sort(key=lambda value: (value.file, value.page or 0, value.quote or '', value.status))
    if len(candidates) == 1:
        return candidates[0]
    first = candidates[0]
    pointers = [pointer for candidate in candidates for pointer in candidate.pointers]
    blank = all(candidate.status == 'blank' for candidate in candidates)
    reason = '' if blank else (
        'Multiple possible rationale sources were found. Check all indicated sources; '
        'the review does not choose which passage controls.')
    return TextValue('blank' if blank else 'not_found', '', first.file, first.page,
                     first.quote, pointers, reason)


def passage_value(reads: list[ReadFile], key: str) -> TextValue:
    """The entire answer must be established; upload order never resolves conflicting passages."""
    if key == 'rationale':
        return rationale_value(reads)
    pattern = TEXT_FIELDS[key][1]
    stop = (re.compile(_RATIONALE_STOP_LINE.pattern + r'|^[ \t]*(?:Scope|Reviewing jurisdiction):', re.M | re.I)
            if key == 'alternative_description' else None)
    candidates = [_rationale_candidate(read, index, match, stop)
                  for read in reads for index, page in enumerate(read.text_pages)
                  for match in pattern.finditer(page.text)]
    if not candidates:
        return TextValue('not_found', '', '', None, None,
                         [Pointer(file=read.name, page=page + 1) for read in reads for page in read.unreadable_pages()])
    candidates.sort(key=lambda found: (found.file, found.page or 0))
    if len(candidates) == 1:
        return candidates[0]
    first = candidates[0]
    pointers = [pointer for candidate in candidates for pointer in candidate.pointers]
    if all(candidate.status == 'blank' for candidate in candidates):
        return TextValue('blank', '', first.file, first.page, None, pointers)
    return TextValue('not_found', '', first.file, first.page, None, pointers,
                     'Multiple possible sources were found for this answer. Check the indicated pages; no controlling passage was chosen.')


def _rationale_candidate(read: ReadFile, index: int, match: re.Match, stop_pattern=None) -> TextValue:
    """Read one candidate, retaining page/graphics/boundary uncertainty and its source fragments."""
    page = read.text_pages[index]
    pointers = []
    uncertain = False
    bodies = []
    ended = False
    # Batatis's own appendix repeats a running header, so its continuation pages can be joined exactly.
    own_appendix = bool(_RUNNING_HEADER.match(page.text))
    for offset, continuation in enumerate(read.text_pages[index:]):
        heading_text = _norm(match.group(0)) if offset == 0 else None
        heading = None
        if not offset:
            raw_heading = match.group(0)
            heading = (heading_text, match.start() + len(raw_heading) - len(raw_heading.lstrip()))
        rest_start = match.end() if not offset else 0
        # Batatis puts a running header on appendix continuation pages. It is not an answer
        # or a terminating applicant source; the original page remains available by pointer.
        header = _RUNNING_HEADER.match(continuation.text) if offset else None
        if offset:
            rest_start = header.end() if header else 0
        rest = continuation.text[rest_start:]
        stop = (stop_pattern or _RATIONALE_STOP_LINE).search(rest)
        ambiguous = bool(stop and stop.groupdict().get('ambiguous')
                         and not (own_appendix and _APPENDIX_SECTION.match(rest[stop.start():].lstrip())))
        # A known multiword label can wrap in extracted text. Stop before that label,
        # but retain uncertainty rather than attributing its words/body to the rationale.
        wrapped = bool(stop and '\n' in stop.group(0).strip())
        stop_line, stop_boundary = None, None
        if stop:
            suffix = rest[stop.start():]
            stop_line = suffix.strip().split('\n', 1)[0]
            stop_boundary = (stop_line, rest_start + stop.start() + len(suffix) - len(suffix.lstrip()))
        body = _norm(rest[:stop.start()] if stop else rest)
        bodies.append(body)
        pointers.append(Pointer(file=read.name, page=continuation.page + 1, quote=body or heading_text))
        uncertain = (uncertain or (bool(offset) and not (own_appendix and header))
                     or wrapped or not continuation.text.strip()
                     or (ambiguous and body != _NO_RATIONALE)
                     or read.passage_has_marks(continuation.page, heading, stop_boundary))
        if stop and _norm(stop.group(0)).casefold().startswith('appendix page'):
            uncertain = True   # a running footer does not prove that the passage ends here
            continue
        if stop:
            ended = True
            break
    if len(bodies) > 1 and not ended:
        uncertain = True   # a joined passage must reach a labelled boundary
    if uncertain:
        reason = ('The rationale may continue across pages, contain non-text content or have an ambiguous boundary. '
                  'Its complete text could not be established; check the indicated pages.')
        return TextValue('not_found', '', read.name, page.page + 1, pointers[0].quote, pointers, reason)
    value = ' '.join(body for body in bodies if body)
    if value == _NO_RATIONALE:
        value = ''
    return TextValue('present' if value else 'blank', value or '', read.name, page.page + 1,
                     pointers[0].quote, pointers)


