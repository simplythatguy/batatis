"""Document review: one model pass over the request and every readable page of the attached files.

The rules and forms passes read named fields. This pass reads what a reviewer reads: what each document
is, the facts that matter with the page they are on, conflicts, the code provisions the documents cite,
what is missing for a complete application, and the next questions. It also flags records from outside
Alberta, code editions other than NBC(AE) 2023, other safety-codes disciplines and the record's status.

Nothing the model writes is kept on trust:
  - every fact, conflict, cited provision and flag excerpt must occur in the page it names (or elsewhere
    in the same file, which corrects the page); an item left without a verified excerpt is dropped;
  - a fact whose restatement carries a number its excerpts do not contain is replaced by its excerpt;
  - Batatis's own sentences (flags, missing items, questions, restatements) that state compliance,
    safety, approval or adequacy are removed, and so is any sentence with an article number the code
    database does not resolve;
  - a cited provision is matched to NBC(AE) 2023 2nd printing only through the code database.

The model sees the scrubbed copy of every text (engine.redact), as the intake model pass does, and its
excerpts are checked against that copy. Live calls need BATATIS_LIVE=1 and pass the spend gate
(engine.llm_gate). BATATIS_REVIEW_MODEL picks gpt-6-luna (default) or gpt-6.1-sol, BATATIS_REVIEW_EFFORT
the reasoning effort (Sol runs at low only). No service tier is sent: requests run on the standard tier.
"""
from __future__ import annotations

import html
import io
import json
import os
import re
import time
import unicodedata
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Callable

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .. import llm_gate
from ..models_intake import (CitedProvision, DocumentReview, EvidenceRef, ReviewConflict, ReviewedDocument,
                             ReviewFact, ReviewFlag, ReviewItem)
from ..public_names import public_review_model
from .pdf import NotAPdf, page_texts
from .rules import LEGAL_PARTS, PERSONAL, read

MODELS = {'gpt-6-luna': ('none', 'low', 'medium', 'high', 'xhigh'), 'gpt-6.1-sol': ('low',)}
DEFAULT_MODEL, DEFAULT_EFFORT = 'gpt-6-luna', 'medium'
MAX_PAGES = 400
BUDGET_CHARS = 600_000                      # page text per request, about 150K tokens
MAX_OUTPUT_TOKENS = 32_000
ATTEMPTS = 3                                # transient network and server errors only
RETRY_STATUS = {429, 500, 502, 503, 504}
# The review runs inside the intake request, so every attempt shares one deadline; on Vercel the function
# itself is cut off after a few minutes. BATATIS_REVIEW_DEADLINE_SECONDS changes it.
DEADLINE_SECONDS = 240
MIN_ATTEMPT_SECONDS = 20


def _deadline_seconds() -> float:
    try:
        return max(MIN_ATTEMPT_SECONDS, float(os.environ.get('BATATIS_REVIEW_DEADLINE_SECONDS') or DEADLINE_SECONDS))
    except ValueError:
        return DEADLINE_SECONDS
OPENAI_URL = 'https://api.openai.com/v1/chat/completions'
DESCRIPTION = 'description'
FLAG_KINDS = ('outside_alberta', 'code_edition', 'other_discipline', 'record_status', 'outcome_known', 'not_read')
FACT_STATUSES = ('stated', 'existing', 'proposed', 'assumed', 'decided', 'argued', 'condition', 'recommended',
                 'tested')

SYSTEM = """You review documents for Batatis, an assistant for Alberta alternative-solution (variance)
applications under the National Building Code - 2023 Alberta Edition, 2nd printing (NBC(AE) 2023). You
check administrative completeness and what the documents establish; you never decide whether a design
complies, is safe, is adequate, is equivalent or should be approved, and you never write the applicant's
professional evidence (rationale, risk assessment, mitigating measures, assumptions and limits).

You get the user's request and the text of the attached files, page by page. Work through all of it,
favouring the pages the request points to, and return:

documents: one entry per attached file: what kind of document it is, its title, author or issuer, date,
  and its status as the document itself states it (draft, concept or illustrative only, not for
  construction, issued, superseded or withdrawn, decided on appeal...).
flags: Batatis's own statements, each with a kind:
  - outside_alberta: the record comes from a place outside Alberta. Name the place and say that its code
    provisions, interpretations and outcomes are not NBC(AE) requirements and are not an Alberta approval
    or precedent.
  - code_edition: the documents rely on a code or edition other than NBC(AE) 2023 (for example the
    Alberta Building Code 2014, NBC(AE) 2019, a national NBC edition, or another jurisdiction's code), or
    they do not state an edition. Name what they cite, and say the edition that governs a current
    application must be confirmed.
  - other_discipline: the matter falls under another safety-codes discipline or regulation (Fire Code,
    Plumbing Code, electrical, gas, elevating devices, occupational health and safety, energy, zoning).
    Keep it separate from NBC(AE) building requirements.
  - record_status: what the record is and is not (a published guide example, a worked example, a design
    study, research or product evidence, a regulator's interpretation or variance) and that it is not an
    application or a site-specific approval, when that matters.
  - outcome_known: the documents report a decision or outcome; say what was decided, by whom, and that it
    does not approve a new project.
  - not_read: a file or pages that could not be read (images without text, missing pages).
facts: the facts a reviewer needs, each as one plain sentence with its status (stated, existing,
  proposed, assumed, decided, argued, condition, recommended, tested) and at least one evidence excerpt.
  Cover every specific thing the request asks about. Include the values that matter: dimensions,
  distances, areas, heights, storeys, occupancies and classifications, ratings, test results and their
  limits, dates, reference numbers, the code provisions relied on, conditions, who argued what and what
  was decided. Keep a party's position separate from a decision, and existing conditions separate from
  proposals and assumptions. Be thorough: twenty to forty facts is normal for a long record.
conflicts: values or statements that disagree within or between documents, with an excerpt for each side.
provisions: every code provision the documents cite (article, sentence, clause or section), written as
  the document writes it, with the code or edition the document names for it.
missing: what a complete, code-referenced application or the reviewer's question still needs that the
  documents do not supply: specific drawings, calculations, test or evaluation reports, professional
  reports and seals, the risk assessment, mitigating measures and assumptions/limits on the alternative
  path, authority records, the governing edition. Say why each is needed. Be specific to this case.
questions: the next questions for the applicant, designer or authority, specific to this case, with why.

Evidence excerpts are copied character for character from one page of one file (or from the request),
at most 300 characters, and name that file id and page. Never cite a provision number that the documents
do not contain. Never state or imply that anything complies, is safe, is adequate or is approved."""


def schema() -> dict:
    evidence = {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
                                           'required': ['file', 'page', 'quote'],
                                           'properties': {'file': {'type': 'string'},
                                                          'page': {'type': ['integer', 'null']},
                                                          'quote': {'type': 'string'}}}}

    def obj(**props):
        return {'type': 'object', 'additionalProperties': False, 'required': list(props), 'properties': props}
    text = {'type': 'string'}
    nullable = {'type': ['string', 'null']}
    return obj(
        documents={'type': 'array', 'items': obj(file=text, kind=text, title=nullable, author=nullable,
                                                 date=nullable, status=nullable)},
        flags={'type': 'array', 'items': obj(kind={'type': 'string', 'enum': list(FLAG_KINDS)}, text=text,
                                             evidence=evidence)},
        facts={'type': 'array', 'items': obj(text=text, status={'type': 'string', 'enum': list(FACT_STATUSES)},
                                             evidence=evidence)},
        conflicts={'type': 'array', 'items': obj(text=text, evidence=evidence)},
        provisions={'type': 'array', 'items': obj(cited=text, code=nullable, evidence=evidence)},
        missing={'type': 'array', 'items': obj(text=text, why=text)},
        questions={'type': 'array', 'items': obj(text=text, why=text)},
    )


class _Input(BaseModel):
    model_config = ConfigDict(strict=True)


class _InputEvidence(_Input):
    file: str = ''
    page: int | None = Field(default=None, ge=1)
    quote: str = ''


class _InputText(_Input):
    text: str = ''
    why: str = ''


class _InputStatement(_InputText):
    evidence: list[_InputEvidence] = Field(default_factory=list)
    status: str = ''
    kind: str = ''


class _InputProvision(_Input):
    cited: str = ''
    code: str | None = None
    evidence: list[_InputEvidence] = Field(default_factory=list)


class _InputDocument(_Input):
    file: str = ''
    kind: str = 'document'
    title: str | None = None
    author: str | None = None
    date: str | None = None
    status: str | None = None


class _Payload(_Input):
    """Validate custom transports too; omitted optional collections remain valid sparse responses."""
    documents: list[_InputDocument] = Field(default_factory=list)
    flags: list[_InputStatement] = Field(default_factory=list)
    facts: list[_InputStatement] = Field(default_factory=list)
    conflicts: list[_InputStatement] = Field(default_factory=list)
    provisions: list[_InputProvision] = Field(default_factory=list)
    missing: list[_InputText] = Field(default_factory=list)
    questions: list[_InputText] = Field(default_factory=list)


class _Usage(_Input):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class _ReportedUsage(_Input):
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)


# ---------------------------------------------------------------- reading the files

class _Html(HTMLParser):
    SKIP = {'script', 'style', 'noscript', 'svg', 'head', 'nav', 'footer'}
    BLOCK = {'p', 'br', 'div', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'td', 'th', 'section', 'article'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCK:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def _html(data: bytes) -> str:
    parser = _Html()
    parser.feed(data.decode('utf-8', errors='replace'))
    text = html.unescape(''.join(parser.parts))
    return re.sub(r'\n\s*\n+', '\n\n', re.sub(r'[ \t]+', ' ', text)).strip()


def _docx(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = z.read('word/document.xml').decode('utf-8', errors='replace')
    return html.unescape(re.sub(r'<[^>]+>', '', re.sub(r'</w:p>', '\n', xml))).strip()


@dataclass
class Source:
    ref: str                                   # 'description' or a file id
    name: str
    pages: list[tuple[int | None, str]] = field(default_factory=list)
    page_count: int = 0
    unread: str | None = None                  # why nothing was read


def read_source(file_id: str, name: str, data: bytes, *, media_type: str | None = None) -> Source:
    lower = name.lower()
    source = Source(file_id, name)
    try:
        if lower.endswith(('.html', '.htm')):
            source.pages, source.page_count = [(None, _html(data))], 1
        elif media_type == 'text/plain' or lower.endswith('.txt'):
            source.pages, source.page_count = [(None, data.decode('utf-8', errors='replace'))], 1
        elif lower.endswith('.docx'):
            source.pages, source.page_count = [(None, _docx(data))], 1
        else:
            source.page_count, source.pages = page_texts(data, MAX_PAGES)
    except (NotAPdf, zipfile.BadZipFile, KeyError):
        source.unread = 'not a readable PDF, HTML, text or Word file'
    if not source.unread and not any(text.strip() for _, text in source.pages):
        source.unread = 'no text layer (an image or a scan)'
    return source


_PAGE_REF = re.compile(r'\b(?:pdf\s+)?pp?\.?\s*(\d{1,4})(?:\s*[-–]\s*(\d{1,4}))?', re.I)
_WORD = re.compile(r'[a-z]{4,}')


def _select(request: str, sources: list[Source], budget: int) -> list[Source]:
    """All pages when they fit; otherwise the pages the request names, each file's first pages, and the
    pages that share the most words with the request, until the budget is spent. Page order is kept."""
    if sum(len(t) for s in sources for _, t in s.pages) <= budget:
        return sources
    named: set[int] = set()
    for m in _PAGE_REF.finditer(request):
        start = int(m.group(1))
        end = int(m.group(2) or start)
        named.update(range(start, min(end, start + 10) + 1))
    words = set(_WORD.findall(request.lower()))
    scored = []
    for si, s in enumerate(sources):
        for pi, (number, text) in enumerate(s.pages):
            if number in named or pi < 2:
                rank = 0
            else:
                rank = 1 + 1 / (1 + len(words & set(_WORD.findall(text.lower()))))
            scored.append((rank, si, pi, len(text)))
    keep, spent = set(), 0
    for rank, si, pi, size in sorted(scored):
        if spent + size > budget:
            continue
        keep.add((si, pi))
        spent += size
    return [Source(s.ref, s.name, [p for pi, p in enumerate(s.pages) if (si, pi) in keep], s.page_count, s.unread)
            for si, s in enumerate(sources)]


# ---------------------------------------------------------------- checking what the model wrote

def _normalized(text: str) -> str:
    text = unicodedata.normalize('NFKC', text or '').replace('­', '')
    text = re.sub(r'[‘’‚‛′`]', "'", text)
    text = re.sub(r'[“”„″]', '"', text)
    text = re.sub(r'[‐-―−]', '-', text)
    return re.sub(r'([^\W\d_])-\s*\n\s*([^\W\d_])', r'\1\2', text)


def _fold(text: str) -> str:
    return re.sub(r'\s+', ' ', _normalized(text)).strip().casefold()


def _excerpt_spans(quote: str, text: str) -> list[tuple[int, int]]:
    """The excerpt occurs in the text. An excerpt shortened with '...' passes only when every one of its
    fragments occurs, in order: a short invented fragment between two real ones fails."""
    q = _fold(quote).strip(' ."\'')
    body = _fold(text)
    parts = [p.strip(' ."\'') for p in re.split(r'\s*(?:\.\.\.|\u2026)\s*', q)]
    if any(not p for p in parts[1:-1]) or sum(len(p) for p in parts) < 6:
        return []
    patterns = []
    for part in (p for p in parts if p):
        pattern = (r'(?<!\w)' if part[0].isalnum() else '') + re.escape(part)
        pattern += r'(?!\w)' if part[-1].isalnum() else ''
        patterns.append(re.compile(pattern))
    numbers = list(re.finditer(r'\d+(?:[.,]\d+)*', body))

    def matches(pattern, at=0):
        return (m for m in pattern.finditer(body, at)
                if not any(n.start() < edge < n.end() for n in numbers for edge in (m.start(), m.end())))

    spans = []
    for first in matches(patterns[0]):
        end = first.end()
        for pattern in patterns[1:]:
            match = next(matches(pattern, end), None)
            if match is None:
                break
            end = match.end()
        else:
            spans.append((first.start(), end))
    return spans


def _occurs(quote: str, text: str) -> bool:
    return bool(_excerpt_spans(quote, text))


def _assertion_spans(quote: str, text: str) -> list[tuple[int, int]]:
    """Expand excerpts to source statements, retaining labelled rows and wrapped words."""
    text = _normalized(text)
    body = _fold(text)
    articles = list(_ARTICLE.finditer(body))
    rows = re.split(r'\r?\n(?=[^\r\n:]{1,60}:)', text)
    row_boundaries, offset = [], 0
    for row in filter(None, map(_fold, rows)):
        if offset:
            row_boundaries.append(offset)
        offset += len(row) + 1
    boundaries = [0, *row_boundaries, *(m.end() for m in re.finditer(r'(?<=[.!?;])\s+', body)
                       if not any(a.start() < m.start() <= a.end() for a in articles)), len(body)]
    return [(max(b for b in boundaries if b <= start), min(b for b in boundaries if b >= end))
            for start, end in _excerpt_spans(quote, text)]


PLACEHOLDER = re.compile(r'\[(?:name|email|phone|address|postal code|personal detail)\]', re.I)


def hidden(scrubbed: str, original: str) -> list[tuple[int, int, str]] | None:
    """(start, end, original value) for each placeholder in `scrubbed`, or None when the two do not align.

    Scrubbing only replaces spans with placeholders, so the text between placeholders is the original text
    verbatim; matching those literal pieces in order recovers exactly what each placeholder hid."""
    marks = []
    for match in PLACEHOLDER.finditer(scrubbed):
        if marks and not scrubbed[marks[-1][1]:match.start()].strip():
            marks[-1] = (marks[-1][0], match.end())
        else:
            marks.append((match.start(), match.end()))
    if not marks:
        return []
    pattern, last = [], 0
    greedy = []
    for start, end in marks:
        literal = re.escape(scrubbed[last:start])
        pattern.append(literal + '(.+?)')
        greedy.append(literal + '(.+)')
        last = end
    pattern.append(re.escape(scrubbed[last:]) + r'\Z')
    greedy.append(re.escape(scrubbed[last:]) + r'\Z')
    match = re.match(''.join(pattern), original, re.S)
    other = re.match(''.join(greedy), original, re.S)
    if match is None or other is None or match.groups() != other.groups():
        return None
    return [(start, end, match.group(i + 1)) for i, (start, end) in enumerate(marks)]


def restore(quote: str, scrubbed: str, original: str) -> tuple[str, list[str]] | None:
    """The original wording behind an excerpt of a scrubbed text, and the value each placeholder hid.

    The provider only ever saw the scrubbed text; this maps a verified excerpt back to the applicant's
    own document for display. None when the excerpt hides nothing or cannot be aligned exactly."""
    if not PLACEHOLDER.search(quote):
        return None
    words = re.findall(r'\S+', quote)
    matches = list(re.finditer(r'\s+'.join(re.escape(w) for w in words), scrubbed, re.I))
    if len(matches) != 1:
        return None
    span = (matches[0].start(), matches[0].end())
    spans = hidden(scrubbed, original)
    if not spans:
        return None
    pieces, values, at = [], [], span[0]
    ambiguous = False
    for start, end, value in spans:
        if start < span[1] and end > span[0] and (start < span[0] or end > span[1]):
            return None                         # one part of adjacent placeholders has no unique original span
        if start < span[0] or end > span[1]:
            continue
        pieces += [scrubbed[at:start], value]
        values.append(value)
        ambiguous |= len(PLACEHOLDER.findall(scrubbed[start:end])) > 1
        at = end
    pieces.append(scrubbed[at:span[1]])
    text = ''.join(pieces).strip()
    return (text, [] if ambiguous else values) if values and text else None


class _Checker:
    def __init__(self, request: str, sources: list[Source], originals: dict | None = None):
        self.request = request
        self.sources = {s.ref: s for s in sources}
        self.originals = originals or {}          # (ref, page) -> unscrubbed text, for display only
        self.hidden: dict[tuple, list[str] | None] = {}
        self.placeholder_kinds: dict[tuple, set[str]] = {}
        self.anchors: dict[tuple, list[tuple[int, int]]] = {}
        self.assertions: dict[tuple, set[str]] = {}

    def _shown(self, quote: str, key: tuple, scrubbed: str) -> str:
        restored = restore(quote, scrubbed, self.originals.get(key, ''))
        text, values = restored if restored is not None else (quote, None)
        identity = (*key, text)
        self.hidden[identity] = values
        self.placeholder_kinds[identity] = {_fold(kind) for kind in PLACEHOLDER.findall(quote)}
        self.anchors[identity] = _assertion_spans(quote, scrubbed)
        body = _fold(scrubbed)
        self.assertions[identity] = {body[start:end].strip() for start, end in self.anchors[identity]}
        return text

    def evidence(self, raw: list[dict]) -> list[EvidenceRef]:
        out = []
        for item in raw or []:
            quote = str(item.get('quote') or '').strip()
            ref = str(item.get('file') or '')
            if not quote:
                continue
            if ref in (DESCRIPTION, 'request') or ref not in self.sources:
                if _occurs(quote, self.request):
                    out.append(EvidenceRef(source_ref=DESCRIPTION,
                                           quote=self._shown(quote, (DESCRIPTION, None), self.request)))
                    continue
            source = self.sources.get(ref)
            if source is None:
                continue
            page = item.get('page')
            ordered = sorted(source.pages, key=lambda p: (p[0] != page, abs((p[0] or 0) - (page or 0))))
            hit = next(((number, text) for number, text in ordered if _occurs(quote, text)), None)
            if hit is not None:
                out.append(EvidenceRef(source_ref=ref, page=hit[0], quote=self._shown(quote, (ref, hit[0]), hit[1])))
        return out

    def unscrub(self, text: str, evidence: list[EvidenceRef]) -> str:
        """Put a hidden value back into a restatement only when it cannot be the wrong one: every placeholder
        in the excerpts hid the same value. Otherwise the restatement keeps its placeholders."""
        relevant = [(e.source_ref, e.page, e.quote) for e in evidence
                    if self.placeholder_kinds.get((e.source_ref, e.page, e.quote))]
        if any(not self.hidden.get(key) for key in relevant):
            return text
        values = {v for key in relevant for v in self.hidden[key]}
        kinds = {kind for key in relevant for kind in self.placeholder_kinds[key]}
        if not PLACEHOLDER.search(text) or len(values) != 1 or len(kinds) != 1:
            return text
        if not {_fold(kind) for kind in PLACEHOLDER.findall(text)} <= kinds:
            return text
        value = values.pop()
        return PLACEHOLDER.sub(lambda m: value, text)

    def independent(self, evidence: list[EvidenceRef]) -> bool:
        """Two distinct, uniquely located source statements, without overlapping or copied assertions."""
        for i, left in enumerate(evidence):
            for right in evidence[i + 1:]:
                if _occurs(left.quote, right.quote) or _occurs(right.quote, left.quote):
                    continue
                a = self.anchors.get((left.source_ref, left.page, left.quote), [])
                b = self.anchors.get((right.source_ref, right.page, right.quote), [])
                if len(a) != 1 or len(b) != 1:
                    continue
                if (self.assertions[(left.source_ref, left.page, left.quote)]
                        & self.assertions[(right.source_ref, right.page, right.quote)]):
                    continue
                if (left.source_ref, left.page) != (right.source_ref, right.page):
                    return True
                if a[0][1] <= b[0][0] or b[0][1] <= a[0][0]:
                    return True
        return False


# A number not glued to a preceding digit or point: "2x6" reads as 2 and 6.
_NUMBER = re.compile(r'(?<![\d.])\d[\d,]*(?:\.\d+)?')
_CLAIM = re.compile(
    r"\b(?:is|are|was|were|will\s+be|would\s+be|appears\s+to\s+be|seems)\s+(?:[a-z]+ly\s+(?:and\s+)?)*(?:code[- ])?"
    r"(?:compliant|safe|approved|acceptable|adequate|sufficient|equivalent)\b"
    r"|\b(?:complies|comply)\s+with\b|\bmeets?\s+(?:all\s+)?(?:of\s+)?(?:the\s+)?(?:code|requirements|NBC)\b"
    r"|\bsatisf(?:ies|y)\s+(?:all\s+)?(?:the\s+)?(?:code|requirements)\b", re.I)
# Attribution, conditions and required evidence apply to a predicate and its shared-subject coordination.
_HEDGE = re.compile(r"\b(?:without|whether|if|nor|neither|unless|before|until|asks?|confirm|show(?:s|ing)?\s+that|"
                    r"demonstrate[sd]?|evidence\s+that|decides?|decided|determin\w+|found|finds|claims?|states?|"
                    r"stated|argued?|says?|said|reports?|reported|asserts?|according\s+to|opinion|"
                    r"must|shall|should|required\s+to|requires?|need(?:s|ed)?\s+to)\b", re.I)
_CLAUSE = re.compile(r"([,;:]\s*(?:and\b)?|(?<=[.!?])\s+|\b(?:and|but|because|while|whereas|so|although)\b)", re.I)
_PREDICATE = re.compile(r'\s*(?:is|are|was|were|will|would|appears|seems|meets?|complies|comply|satisfies|satisfy)\b', re.I)
_NEGATION = re.compile(r"\b(?:(?:does|do|did)\s+not|cannot|can't|never)\s*$", re.I)
_QUESTION = re.compile(r'\s*(?:does|do|did|is|are|was|were|will|would|can|could|should|how|what|why|whether)\b', re.I)
_ARTICLE = re.compile(r'(?<![\w.])(\d{1,2}\s*\.\s*\d{1,2}\s*\.\s*\d{1,2}\s*\.\s*\d{1,3})'
                      r'\.?(?:\s*\(\s*(?:\d+|[a-z]+)\s*\))*(?!\w|\.\d)', re.I)


def _numbers(text: str) -> set[str]:
    out = set()
    for m in _NUMBER.finditer(text or ''):
        value = m.group(0).replace(',', '')
        if '.' in value:
            value = value.rstrip('0').rstrip('.')
        out.add(value.lstrip('0') or '0')
    return out


def sentences(text: str) -> list[str]:
    return [s for s in re.split(r'(?<=[.!?])\s+(?=[A-Z("\'])', (text or '').strip()) if s]


def verdict(sentence: str) -> bool:
    """A sentence that states compliance, safety, approval or adequacy in its own voice."""
    parts = _CLAUSE.split(sentence)
    claims = list(_CLAIM.finditer(sentence))
    scope = False
    offset = 0
    for i in range(0, len(parts), 2):
        clause = parts[i]
        end = offset + len(clause)
        shared = i > 0 and 'and' in parts[i - 1].casefold() and _PREDICATE.match(clause)
        if not shared:
            scope = False
        question = sentence.rstrip().endswith('?') and _QUESTION.match(clause)
        for m in claims:
            if not offset <= m.start() < end:
                continue
            before = clause[:m.start() - offset]
            if not (scope or question or _HEDGE.search(before) or _NEGATION.search(before)):
                return True
        scope = scope or bool(question) or any(_HEDGE.search(clause[:m.start() - offset])
                             for m in claims if offset <= m.start() < end)
        offset = end + (len(parts[i + 1]) if i + 1 < len(parts) else 0)
    return False


def _clean(text: str, resolves: Callable[[str], bool]) -> str:
    """Batatis's own sentence(s) without outright verdicts or unresolvable article numbers."""
    return ' '.join(s for s in sentences(text)
                    if not verdict(s) and all(resolves(re.sub(r'\s+', '', m.group(1)) + '.')
                                               for m in _ARTICLE.finditer(s)))


def _cites_in(cited: str, evidence: list[EvidenceRef]) -> bool:
    """The provision's own identifier occurs in a verified excerpt."""
    normalize = lambda s: re.sub(r'\s+', '', _fold(s)).rstrip('.')
    articles = [normalize(m.group(0)) for m in _ARTICLE.finditer(cited)]
    supported = [normalize(m.group(0)) for e in evidence for m in _ARTICLE.finditer(e.quote)]
    if not all(any(actual == wanted or actual.startswith(wanted + '(') for actual in supported)
               for wanted in articles):
        return False
    body = _fold(' '.join(e.quote for e in evidence))
    tokens = re.findall(r'[A-Za-z]*\d[\w.()/-]*', _ARTICLE.sub('', cited))
    if not tokens:
        return bool(articles) or _fold(cited) in body
    return all(re.search(r'(?<![\w.])' + re.escape(_fold(t).rstrip('.')) + r'(?!\w|\.\d)', body)
               for t in tokens)


def _current_alberta(code: str | None) -> bool:
    label = _fold(code or '')
    years = set(re.findall(r'\b(?:19|20)\d{2}\b', label))
    if years != {'2023'}:
        return False
    label = re.sub(r'[^a-z0-9]+', ' ', label)
    return bool(re.search(r'\bnbc ae 2023\b|\bnational building code (?:of canada )?(?:2023 alberta edition|alberta edition 2023)\b', label))


# ---------------------------------------------------------------- the pass

# (system, user, schema, model, effort) -> (payload, usage). Raise GateClosed when the call may not be made.
Transport = Callable[[str, str, dict, str, str], tuple[dict, dict]]


class GateClosed(Exception):
    def __init__(self, source: str):
        self.source = source
        super().__init__(source)


def configured() -> tuple[str, str]:
    model = (os.environ.get('BATATIS_REVIEW_MODEL') or DEFAULT_MODEL).strip()
    effort = (os.environ.get('BATATIS_REVIEW_EFFORT') or ('low' if model == 'gpt-6.1-sol' else DEFAULT_EFFORT)).strip()
    if model not in MODELS or effort not in MODELS[model]:
        raise ValueError(f'review model/effort must be one of {MODELS}')
    return model, effort


def personal_values(texts: list[str]) -> list[str]:
    """Names, addresses and identifiers the intake rules read anywhere in these texts, for scrubbing.

    A lot, block or section number alone identifies no one and would corrupt other numbers if replaced
    everywhere, so short numeric legal-description parts are left out; every other personal field is kept."""
    out = set()
    for text in texts:
        reading = read(text)
        for hit in [*reading.hits, *(h for hits in reading.conflicts.values() for h in hits)]:
            value = str(hit.value).strip()
            if hit.field not in PERSONAL or not value:
                continue
            if hit.field in LEGAL_PARTS and value.isdigit() and len(value) < 5:
                continue
            out.add(value)
    return sorted(out, key=len, reverse=True)


def _unread_flags(sources: list[Source], sent: list[Source]) -> list[ReviewFlag]:
    """What could not be read, stated by Batatis itself rather than left to the model."""
    out = []
    included = {s.ref: len(s.pages) for s in sent}
    for s in sources:
        if s.unread:
            out.append(ReviewFlag(kind='not_read', text=f'{s.name} was not read: {s.unread}.'))
            continue
        missing = s.page_count - included.get(s.ref, 0)
        if missing > 0:
            reasons = []
            if s.page_count > MAX_PAGES:
                reasons.append(f'only the first {MAX_PAGES} pages can be read')
            if min(s.page_count, MAX_PAGES) > len(s.pages):
                reasons.append('some pages have no text layer (scans or images)')
            if len(s.pages) > included.get(s.ref, 0):
                reasons.append('some readable pages exceed the review text budget')
            out.append(ReviewFlag(kind='not_read', text=f'{missing} of {s.page_count} pages of {s.name} were not read: '
                                                        f'{"; ".join(reasons)}.'))
    return out


def run(request: str, files: list[tuple[str, str, bytes]], *, outbound: Callable[[str, list[str]], str],
        transport: Transport | None, status: str, codes=None, sources: list[Source] | None = None) -> DocumentReview:
    """One review of the request and files. `outbound(text, personal)` scrubs a text before the model sees it."""
    if transport is None:
        return DocumentReview(status='off')
    model, effort = configured()
    if sources is None:
        sources = [read_source(file_id, name, data) for file_id, name, data in files]
    # Personal details read from any page the review may send, the request and the file names are scrubbed
    # from all of them, not only those the first-pages rules pass happened to read.
    personal = personal_values([request or '', *(s.name for s in sources), *(t for s in sources for _, t in s.pages)])
    scrub = lambda text: outbound(text, personal)    # noqa: E731
    scrubbed = [Source(s.ref, f'Attachment {i + 1}', [(n, scrub(t)) for n, t in s.pages], s.page_count, s.unread)
                for i, s in enumerate(sources)]
    request_out = scrub(request or '')
    sent = _select(request_out, scrubbed, BUDGET_CHARS)
    user = json.dumps({
        'request': request_out,
        'files': [{'file': s.ref, 'name': s.name, 'pages_in_file': s.page_count,
                   **({'not_read': s.unread} if s.unread else {}),
                   'pages': [{'page': n, 'text': t} for n, t in s.pages]} for s in sent],
    }, ensure_ascii=False)
    version = public_review_model(model)
    try:
        payload, usage = transport(SYSTEM, user, schema(), model, effort)
        payload = _Payload.model_validate(payload).model_dump()
        usage = _Usage.model_validate(usage).model_dump()
    except GateClosed as closed:
        return DocumentReview(status='gate_closed', model=version, effort=effort, reason=closed.source,
                              flags=_unread_flags(sources, sent), input_tokens=None, output_tokens=None)
    except Exception as exc:                     # provider text may carry request details; keep only the type
        return DocumentReview(status='failed', model=version, effort=effort, reason=type(exc).__name__,
                              flags=_unread_flags(sources, sent), input_tokens=None, output_tokens=None)

    def resolves(article: str) -> bool:
        if codes is None:
            return False
        try:
            return any(codes.provision(article, d) for d in ('B', 'A', 'C'))
        except Exception:
            return False

    originals = {(s.ref, n): t for s in sources for n, t in s.pages}
    originals[(DESCRIPTION, None)] = request or ''
    check = _Checker(request_out, sent, originals)
    dropped = 0
    review = DocumentReview(status=status, model=version, effort=effort, flags=_unread_flags(sources, sent),
                            pages_sent=sum(len(s.pages) for s in sent),
                            input_tokens=usage.get('input_tokens'),
                            output_tokens=usage.get('output_tokens'))
    known = {s.ref for s in sources}
    for d in payload.get('documents') or []:
        if d.get('file') in known:
            review.documents.append(ReviewedDocument(
                file_id=d['file'], kind=_clean(d.get('kind') or 'document', resolves) or 'document',
                title=_clean(d.get('title') or '', resolves) or None,
                author=_clean(d.get('author') or '', resolves) or None,
                date=_clean(d.get('date') or '', resolves) or None,
                status=_clean(d.get('status') or '', resolves) or None))
    for f in payload.get('flags') or []:
        text = _clean(f.get('text') or '', resolves)
        if not text or f.get('kind') not in FLAG_KINDS:
            dropped += 1
            continue
        review.flags.append(ReviewFlag(kind=f['kind'], text=text, evidence=check.evidence(f.get('evidence'))))
    for f in payload.get('facts') or []:
        evidence = check.evidence(f.get('evidence'))
        if not evidence or f.get('status') not in FACT_STATUSES:
            dropped += 1
            continue
        text = check.unscrub(_clean(f.get('text') or '', resolves), evidence)
        if not text or _clean(text, resolves) != text:
            text = 'The source contains the quoted statement.'
        if not _numbers(text) <= _numbers(' '.join(e.quote for e in evidence)):
            text = evidence[0].quote                 # the restatement added a number: show the excerpt instead
            if _clean(text, resolves) != text:
                text = 'The source contains the quoted statement.'
        review.facts.append(ReviewFact(text=text, status=f['status'], evidence=evidence))
    for c in payload.get('conflicts') or []:
        evidence = check.evidence(c.get('evidence'))
        text = check.unscrub(_clean(c.get('text') or '', resolves), evidence)
        if (not check.independent(evidence) or not text or _clean(text, resolves) != text
                or not _numbers(text) <= _numbers(' '.join(e.quote for e in evidence))):
            dropped += 1
            continue
        review.conflicts.append(ReviewConflict(text=text, evidence=evidence))
    for p in payload.get('provisions') or []:
        evidence = check.evidence(p.get('evidence'))
        cited = str(p.get('cited') or '').strip()
        if not evidence or not cited or not _cites_in(cited, evidence):
            dropped += 1
            continue
        m = _ARTICLE.search(cited)
        resolved, division = None, None
        outside = any(f.kind == 'outside_alberta' for f in review.flags)
        if (m and codes is not None and not outside and _current_alberta(p.get('code'))
                and any(_current_alberta(e.quote) for e in evidence)):
            for d in ('B', 'A', 'C'):
                try:
                    hit = codes.provision(re.sub(r'\s+', '', m.group(1)) + '.', d)
                except Exception:
                    hit = None
                if hit:
                    resolved, division = hit['id'], d
                    break
        review.provisions.append(CitedProvision(cited=cited[:120], code=(p.get('code') or None),
                                                resolves_to=resolved, division=division, evidence=evidence))
    for name in ('missing', 'questions'):
        for item in payload.get(name) or []:
            text, why = _clean(item.get('text') or '', resolves), _clean(item.get('why') or '', resolves)
            if not text:
                dropped += 1
                continue
            getattr(review, name).append(ReviewItem(text=text, why=why))
    review.dropped = dropped
    return review


# ---------------------------------------------------------------- transports

def openai_transport(client_ip: str | None = None) -> Transport:
    """Chat Completions with a strict schema, metered, on the standard tier (no service tier is sent).

    Every attempt reserves its own worst case through the spend gate before it is sent. A failed attempt
    keeps its reservation, since it may have been billed; only the successful attempt settles to its usage.
    Dropped connections and 429/5xx answers are retried, all within one deadline."""
    def call(system: str, user: str, body_schema: dict, model: str, effort: str) -> tuple[dict, dict]:
        import httpx
        max_input = len((system + user + json.dumps(body_schema)).encode()) // 3 + 256
        body = {'model': model, 'max_completion_tokens': MAX_OUTPUT_TOKENS, 'reasoning_effort': effort,
                'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
                'response_format': {'type': 'json_schema',
                                    'json_schema': {'name': 'document_review', 'strict': True, 'schema': body_schema}}}
        deadline = time.monotonic() + _deadline_seconds()
        for attempt in range(ATTEMPTS):
            remaining = deadline - time.monotonic()
            if remaining < MIN_ATTEMPT_SECONDS:
                raise TimeoutError('review deadline reached')
            decision = llm_gate.authorize(model=model, max_input_tokens=max_input,
                                          max_output_tokens=MAX_OUTPUT_TOKENS, client_ip=client_ip, provider='openai')
            if not decision.allowed:
                raise GateClosed(decision.source)
            dispatched = False
            try:
                with httpx.Client(timeout=remaining, follow_redirects=False) as client:
                    headers = {'Authorization': 'Bearer ' + os.environ['OPENAI_API_KEY']}
                    remaining = deadline - time.monotonic()
                    if remaining < MIN_ATTEMPT_SECONDS:
                        raise TimeoutError('review deadline reached')
                    client.timeout = httpx.Timeout(remaining)
                    dispatched = True
                    response = client.post(OPENAI_URL, json=body, headers=headers)
            except Exception as exc:
                if not dispatched or isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)):
                    llm_gate.release(decision)
                if (not isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadError, httpx.ReadTimeout,
                                         httpx.RemoteProtocolError, httpx.WriteError, httpx.PoolTimeout))
                        or attempt + 1 >= ATTEMPTS):
                    raise
                time.sleep(2 * (attempt + 1))
                continue
            if response.status_code in RETRY_STATUS and attempt + 1 < ATTEMPTS:
                time.sleep(2 * (attempt + 1))
                continue
            response.raise_for_status()
            data = response.json()
            tokens = {}
            try:
                usage = _ReportedUsage.model_validate(data.get('usage'))
            except ValidationError:
                pass                            # dispatched, but its cost is unknown: keep the reservation
            else:
                tokens = {'input_tokens': usage.prompt_tokens, 'output_tokens': usage.completion_tokens}
                llm_gate.record(model=model, reserved_usd=decision.reserved_usd, **tokens)
            return json.loads(data['choices'][0]['message']['content']), tokens
        raise TimeoutError('review attempts exhausted')
    return call


def fake_transport(system: str, user: str, body_schema: dict, model: str, effort: str) -> tuple[dict, dict]:
    """Deterministic stand-in: names each file and quotes its first line as a stated fact. Not a measurement."""
    data = json.loads(user)
    documents, facts = [], []
    for f in data['files']:
        documents.append({'file': f['file'], 'kind': 'document', 'title': f['name'], 'author': None, 'date': None,
                          'status': None})
        for page in f['pages'][:1]:
            line = next((ln.strip() for ln in page['text'].splitlines() if len(ln.strip()) >= 12), '')
            if line:
                facts.append({'text': line[:200], 'status': 'stated',
                              'evidence': [{'file': f['file'], 'page': page['page'], 'quote': line[:200]}]})
    payload = {'documents': documents, 'flags': [], 'facts': facts, 'conflicts': [], 'provisions': [],
               'missing': [], 'questions': []}
    return payload, {'input_tokens': len(system + user) // 4, 'output_tokens': 50 * (len(facts) + 1)}


def default_transport(client_ip: str | None = None) -> tuple[Transport | None, str]:
    if (os.environ.get('BATATIS_PROVIDER') or '').strip().lower() == 'fake' and not os.environ.get('VERCEL'):
        return fake_transport, 'fake'
    if llm_gate.live_enabled('openai') and os.environ.get('BATATIS_REVIEW', '1') != '0':
        return openai_transport(client_ip), 'live'
    return None, 'off'


__all__ = ['run', 'read_source', 'default_transport', 'openai_transport', 'fake_transport', 'configured', 'schema',
           'SYSTEM', 'GateClosed']
