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

import difflib
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

from .. import llm_gate
from ..models_intake import (CitedProvision, DocumentReview, EvidenceRef, ReviewConflict, ReviewedDocument,
                             ReviewFact, ReviewFlag, ReviewItem)
from .pdf import NotAPdf, page_texts

MODELS = {'gpt-6-luna': ('none', 'low', 'medium', 'high', 'xhigh'), 'gpt-6.1-sol': ('low',)}
DEFAULT_MODEL, DEFAULT_EFFORT = 'gpt-6-luna', 'medium'
MAX_PAGES = 400
BUDGET_CHARS = 600_000                      # page text per request, about 150K tokens
MAX_OUTPUT_TOKENS = 32_000
ATTEMPTS = 3                                # transient network and server errors only
RETRY_STATUS = {429, 500, 502, 503, 504}
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


def read_source(file_id: str, name: str, data: bytes) -> Source:
    lower = name.lower()
    source = Source(file_id, name)
    try:
        if lower.endswith(('.html', '.htm')):
            source.pages, source.page_count = [(None, _html(data))], 1
        elif lower.endswith('.txt'):
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

def _fold(text: str) -> str:
    text = unicodedata.normalize('NFKC', text or '').replace('­', '')
    text = re.sub(r'[‘’‚‛′`]', "'", text)
    text = re.sub(r'[“”„″]', '"', text)
    text = re.sub(r'[‐-―−]', '-', text)
    text = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', text)      # a word broken across a line
    return re.sub(r'\s+', ' ', text).strip().casefold()


def _occurs(quote: str, text: str) -> bool:
    q = _fold(quote).strip(' ."\'')
    if len(q) < 6:
        return False
    body = _fold(text)
    if q in body:
        return True
    parts = [p.strip() for p in re.split(r'\s*(?:\.\.\.|…)\s*', q) if len(p.strip()) >= 6]
    if len(parts) < 2:
        return False
    at = 0
    for part in parts:
        at = body.find(part, at)
        if at < 0:
            return False
        at += len(part)
    return True


PLACEHOLDER = re.compile(r'\[(?:name|email|phone|address|postal code|personal detail)\]')


def _span(quote: str, text: str) -> tuple[int, int] | None:
    words = re.findall(r'\S+', quote)
    if not words:
        return None
    m = re.search(r'\s+'.join(re.escape(w) for w in words), text, re.I)
    return (m.start(), m.end()) if m else None


def restore(quote: str, scrubbed: str, original: str) -> tuple[str, list[str]] | None:
    """The original wording behind an excerpt of a scrubbed text, and the value each placeholder hid.

    The provider only ever saw the scrubbed text; this maps a verified excerpt back to the applicant's
    own document for display. None when the excerpt hides nothing or cannot be aligned."""
    if not PLACEHOLDER.search(quote):
        return None
    span = _span(quote, scrubbed)
    if span is None:
        return None
    ops = difflib.SequenceMatcher(None, scrubbed, original, autojunk=False).get_opcodes()

    def to_original(index: int, end: bool) -> int:
        for tag, i1, i2, j1, j2 in ops:
            if i1 <= index < i2:
                return j1 + (index - i1) + (1 if end else 0) if tag == 'equal' else (j2 if end else j1)
        return len(original)
    start, stop = to_original(span[0], False), to_original(span[1] - 1, True)
    hidden = [original[to_original(m.start(), False):to_original(m.end() - 1, True)].strip()
              for m in PLACEHOLDER.finditer(scrubbed, span[0], span[1])]
    text = original[start:stop].strip()
    return (text, hidden) if text else None


class _Checker:
    def __init__(self, request: str, sources: list[Source], originals: dict | None = None):
        self.request = request
        self.sources = {s.ref: s for s in sources}
        self.originals = originals or {}          # (ref, page) -> unscrubbed text, for display only
        self.hidden: dict[str, list[str]] = {}    # verified quote -> values its placeholders hid

    def _shown(self, quote: str, key: tuple, scrubbed: str) -> str:
        restored = restore(quote, scrubbed, self.originals.get(key, ''))
        if restored is None:
            return quote
        text, hidden = restored
        self.hidden[text] = hidden
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
        """Put the hidden values back into a restatement when its placeholders line up with its excerpts."""
        values = [v for e in evidence for v in self.hidden.get(e.quote, [])]
        slots = PLACEHOLDER.findall(text)
        if not slots or len(slots) != len(values):
            return text
        for value in values:
            text = PLACEHOLDER.sub(lambda m: value, text, count=1)
        return text


_NUMBER = re.compile(r'(?<![\w.])\d[\d,]*(?:\.\d+)?')
_CLAIM = re.compile(
    r"\b(?:is|are|was|were|will\s+be|would\s+be|appears\s+to\s+be|seems)\s+(?:fully\s+)?(?:code[- ])?"
    r"(?:compliant|safe|approved|acceptable|adequate|sufficient|equivalent)\b"
    r"|\b(?:complies|comply)\s+with\b|\bmeets?\s+(?:all\s+)?(?:of\s+)?(?:the\s+)?(?:code|requirements|NBC)\b"
    r"|\bsatisf(?:ies|y)\s+(?:all\s+)?(?:the\s+)?(?:code|requirements)\b", re.I)
_HEDGE = re.compile(r"\b(?:not|never|no|cannot|can't|isn't|aren't|without|whether|if|nor|neither|unless|"
                    r"does\s+not|do\s+not|did\s+not|before|until|asks?|confirm|show(?:s|ing)?\s+that|"
                    r"demonstrate[sd]?|evidence\s+that|decides?|determin\w+|claims?|states?|argued?|says?|"
                    r"according\s+to|reports?)\b", re.I)
_ARTICLE = re.compile(r'(?<![\d.])(\d{1,2}\.\d{1,2}\.\d{1,2}\.\d{1,3})\.?(?:\(\d+\)(?:\([a-z]+\))?)?')


def _numbers(text: str) -> set[str]:
    out = set()
    for m in _NUMBER.finditer(text or ''):
        value = m.group(0).replace(',', '')
        if '.' in value:
            value = value.rstrip('0').rstrip('.')
        out.add(value.lstrip('0') or '0')
    return out


def _clean(text: str, resolves: Callable[[str], bool]) -> str:
    """Batatis's own sentence(s) without outright verdicts or unresolvable article numbers."""
    kept = []
    for sentence in re.split(r'(?<=[.!?])(?<!\d\.)\s+(?=[A-Z("\'])', (text or '').strip()):
        if not sentence:
            continue
        verdict = any(not _HEDGE.search(sentence[:m.start()]) for m in _CLAIM.finditer(sentence)) \
            and not sentence.rstrip().endswith('?')
        if verdict or any(not resolves(m.group(1) + '.') for m in _ARTICLE.finditer(sentence)):
            continue
        kept.append(sentence)
    return ' '.join(kept)


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


def run(request: str, files: list[tuple[str, str, bytes]], *, outbound: Callable[[str], str],
        transport: Transport | None, status: str, codes=None) -> DocumentReview:
    """One review of the request and files. `outbound` scrubs a text before the model sees it."""
    if transport is None:
        return DocumentReview(status='off')
    model, effort = configured()
    sources = [read_source(file_id, name, data) for file_id, name, data in files]
    scrubbed = [Source(s.ref, s.name, [(n, outbound(t)) for n, t in s.pages], s.page_count, s.unread) for s in sources]
    request_out = outbound(request or '')
    sent = _select(request_out, scrubbed, BUDGET_CHARS)
    user = json.dumps({
        'request': request_out,
        'files': [{'file': s.ref, 'name': s.name, 'pages_in_file': s.page_count,
                   **({'not_read': s.unread} if s.unread else {}),
                   'pages': [{'page': n, 'text': t} for n, t in s.pages]} for s in sent],
    }, ensure_ascii=False)
    try:
        payload, usage = transport(SYSTEM, user, schema(), model, effort)
    except GateClosed as closed:
        return DocumentReview(status='gate_closed', model=model, effort=effort, reason=closed.source)
    except Exception as exc:                     # provider text may carry request details; keep only the type
        return DocumentReview(status='failed', model=model, effort=effort, reason=type(exc).__name__)

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
    review = DocumentReview(status=status, model=model, effort=effort,
                            pages_sent=sum(len(s.pages) for s in sent),
                            input_tokens=int(usage.get('input_tokens') or 0),
                            output_tokens=int(usage.get('output_tokens') or 0))
    known = {s.ref for s in sources}
    for d in payload.get('documents') or []:
        if d.get('file') in known:
            review.documents.append(ReviewedDocument(
                file_id=d['file'], kind=_clean(d.get('kind') or 'document', resolves) or 'document',
                title=d.get('title'), author=d.get('author'), date=d.get('date'),
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
        if not text or not _numbers(text) <= _numbers(' '.join(e.quote for e in evidence)):
            text = evidence[0].quote                 # the restatement added a number: show the excerpt instead
        review.facts.append(ReviewFact(text=text, status=f['status'], evidence=evidence))
    for c in payload.get('conflicts') or []:
        evidence = check.evidence(c.get('evidence'))
        text = _clean(c.get('text') or '', resolves)
        if len(evidence) < 2 or not text:
            dropped += 1
            continue
        review.conflicts.append(ReviewConflict(text=text, evidence=evidence))
    for p in payload.get('provisions') or []:
        evidence = check.evidence(p.get('evidence'))
        cited = str(p.get('cited') or '').strip()
        if not evidence or not cited:
            dropped += 1
            continue
        m = _ARTICLE.search(cited)
        resolved, division = None, None
        if m and codes is not None:
            for d in ('B', 'A', 'C'):
                try:
                    hit = codes.provision(m.group(1) + '.', d)
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
    """Chat Completions with a strict schema, metered: reserve before, record after. No retry, no service tier."""
    def call(system: str, user: str, body_schema: dict, model: str, effort: str) -> tuple[dict, dict]:
        import httpx
        max_input = len((system + user + json.dumps(body_schema)).encode()) // 3 + 256
        decision = llm_gate.authorize(model=model, max_input_tokens=max_input, max_output_tokens=MAX_OUTPUT_TOKENS,
                                      client_ip=client_ip, provider='openai')
        if not decision.allowed:
            raise GateClosed(decision.source)
        body = {'model': model, 'max_completion_tokens': MAX_OUTPUT_TOKENS, 'reasoning_effort': effort,
                'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
                'response_format': {'type': 'json_schema',
                                    'json_schema': {'name': 'document_review', 'strict': True, 'schema': body_schema}}}
        data = None
        for attempt in range(ATTEMPTS):
            try:
                with httpx.Client(timeout=600, follow_redirects=False) as client:
                    response = client.post(OPENAI_URL, json=body,
                                           headers={'Authorization': 'Bearer ' + os.environ['OPENAI_API_KEY']})
                if response.status_code in RETRY_STATUS and attempt + 1 < ATTEMPTS:
                    time.sleep(2 * (attempt + 1))
                    continue
                response.raise_for_status()
                data = response.json()
                break
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadError, httpx.ReadTimeout,
                    httpx.RemoteProtocolError, httpx.WriteError, httpx.PoolTimeout):
                # The connection dropped; nothing usable came back. The gate keeps the first reservation.
                if attempt + 1 >= ATTEMPTS:
                    raise
                time.sleep(2 * (attempt + 1))
        usage = data.get('usage') or {}
        tokens = {'input_tokens': usage.get('prompt_tokens', 0), 'output_tokens': usage.get('completion_tokens', 0)}
        llm_gate.record(model=model, reserved_usd=decision.reserved_usd, **tokens)
        return json.loads(data['choices'][0]['message']['content']), tokens
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
