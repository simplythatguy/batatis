"""Select project passages before field extraction; preserve original page offsets.

Attachment presence and quote identity do not establish project ownership. Unclassified
passages stay available to document review, but cannot answer project questions. This is
a conservative structural reader, not a semantic classifier of arbitrary reports.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Sequence

from .pdf import Page, Widget
from .rules import PERSONAL, project_labels, read

Context = Literal['project', 'reference', 'unknown']

_PROJECT = re.compile(r'(?i)^(?:current\s+project|our\s+project|project\s+(?:brief|description|summary|details|information))\b')
_OWN = re.compile(r"(?i)\b(?:we\s+are\s+(?:building|proposing|constructing)|our\s+(?:proposed|new)\s+(?:building|house|project))\b")
_REFERENCE = re.compile(
    r'(?i)^(?:archived?\b|policy\b|guide\b|guidance\b|instructions\b|'
    r'variance\s+SPV[-\s]|'
    r'(?:example|sample|demonstration|historical|case\s+study)\b|'
    r'(?:appendix\b.*|quoted\s+|reference\s+)(?:policy|guidance|guide|material|example|requirements)\b|'
    r'.{0,90}\b(?:submission\s+guide|application\s+instructions)\b)')
# These are descriptions of a requirement or another scenario, even inside a project brief.
_CONDITIONAL = re.compile(r'(?i)^(?:if\b|where\b|for\s+example\b|for\s+reference\b|'
                          r'according\s+to\b|(?:the\s+)?(?:policy|guide|code)\s+(?:states|requires|says)\b|[>“"])')
_TEMPLATE = re.compile(r'(?i)^request\s+for\s+(?:a\s+)?specific\s+variance\b')
_ISSUER = re.compile(r'(?i)^(?:(?:consultant|architect|engineer|designer|issuer|company)\b.{0,35}'
                     r'\b(?:office|contact|address)|(?:office|contact)\s*(?:address\s*)?:)')


@dataclass(frozen=True)
class ProjectPage:
    number: int
    text: str                              # excluded characters replaced by spaces, newlines retained


def _advance(state: Context, line: str) -> Context:
    if state == 'reference' or _REFERENCE.search(line) or _CONDITIONAL.search(line):
        return 'reference'
    if _PROJECT.search(line) or _OWN.search(line):
        return 'project'
    return state


def project_pages(pages: Sequence[Page], *, admit: Context = 'project') -> list[ProjectPage]:
    """Only positive project context is admitted. Reference sections end inherited context.

    `admit='unknown'` returns the passages with no marker either way (a plain set of drawings): they
    may only propose values the applicant confirms; reference sections are never admitted.

    A document that starts as reference material cannot promote its example 'Project brief'
    headings or first-person declarations. Completed widgets are handled separately.
    """
    state: Context = 'unknown'
    result = []
    for page in pages:
        kept = []
        for line in page.text.splitlines(keepends=True):
            stripped = line.strip()
            state = 'reference' if _TEMPLATE.search(stripped) else _advance(state, stripped)
            admitted = state == admit and not _ISSUER.search(stripped)
            # Letterhead, office contact details and report dates are not site/applicant fields.
            # Keep only explicitly named project labels; body building facts remain readable.
            project_line = line
            if admitted:
                reading = read(line)
                labels = project_labels(line)
                hits = [*reading.hits, *(hit for hits in reading.conflicts.values() for hit in hits)]
                admin = [h for h in hits if h.field in PERSONAL or h.field == 'request_date']
                chars = list(line)
                for hit in admin:
                    if any(label.field == hit.field and label.start <= hit.start and hit.end <= label.end
                           for label in labels):
                        continue
                    chars[hit.start:hit.end] = ' ' * (hit.end - hit.start)
                project_line = ''.join(chars)
            kept.append(project_line if admitted else ''.join(c if c in '\r\n' else ' ' for c in line))
        result.append(ProjectPage(page.number, ''.join(kept)))
    return result


def reference_widget(pages: Sequence[Page], widget: Widget) -> bool:
    """Use the context above this widget, including earlier pages and same-page headings.

    A normal application title does not invalidate filled fields. Example/archived/quoted
    sections do, even when the document began with actual project information.
    """
    state: Context = 'unknown'
    for page in pages:
        if page.number > widget.page:
            break
        offset = 0
        for line in page.text.splitlines(keepends=True):
            box = page.box(offset, offset + len(line))
            offset += len(line)
            if page.number == widget.page and box is not None and box[3] < widget.rect[1]:
                continue
            state = _advance(state, line.strip())
    return state == 'reference'
