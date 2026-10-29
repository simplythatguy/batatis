"""Zero-provider requirement discovery over the verified NBC(AE) 2023 p2 source.

The ledger retains every discovery, including unresolved supporting requirements.
Neither a lexical hit nor graph closure is a finding of applicability/completeness.
Only caller-supplied human decisions can include/exclude a requirement or name a
confirmed departure. Nothing here writes the case or changes its question flow.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path

from engine.codes import Codes
from engine.models_identify import (BenchmarkRecord, IdentifyArticle, IdentifyResult, IdentifyTrace, ProcessRef,
                                    RequirementCondition, RequirementCoverage, RequirementDiscovery,
                                    RequirementGap, RequirementRecord, StageRecord)

from .config import IdentifyConfig
from .corpus import articles
from .requirement_corpus import LIMITS, Corpus, Key, SourceUnavailable, load, qualified
from .requirement_graph import build, external_gaps, references

IDENTITY = 'requirements-fulltext-graph-v1'
_ALTERNATIVE = re.compile(r'\balternative\s+solutions?\b', re.I)
_CONDITIONAL = re.compile(r'\b(?:if|where|except|unless|occupanc\w*|storeys?|height|building area)\b', re.I)
_SCOPE = {
    'occupancy': (re.compile(r'\boccupanc\w*\b', re.I), {'occupancy', 'building.occupancy', 'professional.occupancy'}),
    'storeys': (re.compile(r'\b(?:storeys?|building height)\b', re.I), {'storeys', 'building.storeys'}),
    'building_area_m2': (re.compile(r'\bbuilding area\b', re.I), {'building_area_m2', 'building.area_m2'}),
    'height_m': (re.compile(r'\bheight\b', re.I), {'height_m', 'building.height_m'}),
}


def _data(value):
    return value.model_dump(mode='json') if hasattr(value, 'model_dump') else value


def _fingerprint(prose: str, facts: list[dict]) -> str:
    # Full content and evidence pointers participate. Input ordering alone does not
    # invalidate a human decision; an edited value/status/source does.
    ordered = sorted(facts, key=lambda f: json.dumps(f, sort_keys=True, ensure_ascii=False))
    return hashlib.sha256(json.dumps({'strategy': IDENTITY, 'prose': prose, 'facts': ordered},
                                     sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def _conditions(text: str, facts: list[dict]) -> list[RequirementCondition]:
    conditions = []
    for name, (pattern, aliases) in _SCOPE.items():
        if not pattern.search(text):
            continue
        candidates = [f for f in facts if f.get('field') in aliases and f.get('value') is not None]
        values = {json.dumps(f['value'], sort_keys=True) for f in candidates}
        status = ('conflict' if len(values) > 1 else 'provided' if candidates and all(
            f.get('status') == 'confirmed' and f.get('kind') != 'proposed' for f in candidates) else 'unknown')
        conditions.append(RequirementCondition(field=name, status=status,
                                                fact_ids=[f['id'] for f in candidates if f.get('id')]))
    return conditions


def _human_seeds(previous: IdentifyResult | None, confirmed_provisions) -> dict[str, RequirementRecord | None]:
    seeds: dict[str, RequirementRecord | None] = {str(p): None for p in confirmed_provisions}
    if previous:
        for row in previous.requirements:
            if row.human_confirmed:
                seeds[row.id] = row
        # Legacy yes means a human named a departure; no does not exclude a
        # supporting requirement from this ledger.
        for pid, decision in previous.decisions.items():
            if decision.decision == 'yes':
                seeds.setdefault(pid, None)
        if previous.benchmark.departure_status == 'confirmed' and previous.benchmark.provision:
            seeds.setdefault(previous.benchmark.provision, None)
    return seeds


def _selected_targets(corpus: Corpus, entered: str) -> list[Key]:
    match = re.fullmatch(r'(?:NBC-AE:)?([ABC]):(.+)', entered.strip(), re.I)
    div, text = (match[1].upper(), match[2]) if match else ('B', entered)
    refs = references(text, division=div)
    if len(refs) != 1 or refs[0].external:
        return []
    return corpus.targets(refs[0].division or div, refs[0].pid)


def _dedup_gaps(gaps: list[RequirementGap]) -> list[RequirementGap]:
    unique = {}
    for gap in gaps:
        key = (gap.code, gap.reference, gap.from_requirement, gap.evidence_id,
               gap.evidence.division if gap.evidence else None,
               gap.evidence.provision_id if gap.evidence else None)
        unique.setdefault(key, gap)
    return list(unique.values())


def _record(corpus: Corpus, key: Key, facts: list[dict]) -> RequirementRecord:
    """A new ledger row for one source article: its title, citation, pages and scope conditions."""
    row = corpus.articles[key]
    text = '\n'.join(r.get('text') or '' for r in corpus.by_article.get(key, []))
    conditions = _conditions(text, facts)
    record = RequirementRecord(
        id=qualified(key), division=key[0], provision_id=key[1], title=row.get('title') or '',
        role='admin' if key[0] in ('A', 'C') else 'conditional' if _CONDITIONAL.search(text) else 'unresolved',
        citation=corpus.citation(row), pdf_page=row.get('pdf_page'), pdf_page_end=row.get('pdf_page_end'),
        source_sha256=corpus.source.text_sha256, conditions=conditions,
        review_reasons=['Discovery does not establish applicability or a departure.'])
    for condition in conditions:
        if condition.status != 'provided':
            record.review_reasons.append(f'{condition.field}: {condition.status}; scope remains unresolved.')
    return record


def _shown(corpus: Corpus, record: RequirementRecord, rank: int, quote_source: str = 'codedb') -> IdentifyArticle:
    """The article card for a verified Division B ledger row, with Section C terms from the attribution tables."""
    row = corpus.articles[('B', record.provision_id)]
    objectives, functions, missing = corpus.terms(record.provision_id, record.quote_provision_id)
    quote_row = corpus.rows.get(('B', record.quote_provision_id)) if record.quote_provision_id else None
    return IdentifyArticle(
        rank=rank, provision=record.provision_id, provision_id=record.quote_provision_id,
        title=record.title, part=row['part'], citation=corpus.citation(quote_row or row),
        link=f'/code/{record.provision_id}?division=B', quote=record.quote,
        quote_source=quote_source if record.quote else None, status='candidate',
        reason='Requirement candidate; see the source evidence and applicability review state.',
        commit_reason='Requirement discovery does not automatically confirm applicability or a departure.',
        objectives=objectives, functions=functions, attribution_missing=missing)


def _discover(prose: str, facts: list[dict], corpus: Corpus, previous: IdentifyResult | None,
              confirmed_provisions, fingerprint: str):
    records: dict[Key, RequirementRecord] = {}
    paths: dict[Key, list[str]] = {}
    evidence_pool = {}
    discoveries = {}
    search_text = prose + '\n' + '\n'.join(
        f'{f.get("field", "")}: {f.get("value", "")}' for f in facts if f.get('value') is not None)
    gaps = external_gaps(search_text)
    # Other codes may exist in docs (e.g. NFC) without parsed provisions. They
    # are outside this edition-restricted identifier even when files are present.
    gaps.extend([
        RequirementGap(code='fire_code_unavailable', message='Fire-code requirements are outside this verified NBC(AE) corpus; applicability has not been determined.'),
        RequirementGap(code='energy_code_unavailable', message='External energy-code requirements are outside this verified NBC(AE) corpus; applicability has not been determined.'),
        RequirementGap(code='tables_not_fully_parsed', message='Table contents and appendices require source-PDF review; numeric table references alone do not provide their requirements.'),
        RequirementGap(code='applicability_unresolved', message='The discovered candidates require human applicability review; this is not an exhaustive set of applicable requirements.'),
    ])

    def add(key: Key, kind: str, detail: str, *, evidence=None, origin=None, path=None):
        if key not in records:
            records[key] = _record(corpus, key, facts)
            paths[key] = path or [qualified(key)]
        record = records[key]
        discovery_key = (key, kind, origin)
        discovery = discoveries.get(discovery_key)
        if discovery is None:
            discovery = RequirementDiscovery(kind=kind, detail=detail, evidence_id=evidence.id if evidence else None,
                                              from_requirement=qualified(origin) if origin else None,
                                              path=path or paths[key])
            record.discoveries.append(discovery)
            discoveries[discovery_key] = discovery
        if evidence:
            if evidence.id not in discovery.evidence_ids:
                discovery.evidence_ids.append(evidence.id)
            evidence_pool[evidence.id] = evidence
            if evidence.id not in record.evidence_ids:
                record.evidence_ids.append(evidence.id)
            # Keep directly matched normative evidence convenient on a card.
            # Shared/reference/note passages remain complete in the evidence pool.
            if (evidence.kind == 'provision' and corpus.article_key(evidence.division, evidence.provision_id) == key
                    and evidence not in record.evidence):
                record.evidence.append(evidence)
        if (evidence and evidence.kind == 'provision' and not evidence.contextual and not record.quote
                and corpus.article_key(evidence.division, evidence.provision_id) == key):
            record.quote, record.quote_provision_id = evidence.quote, evidence.provision_id
        if kind in ('reference', 'reverse_reference') and record.role == 'unresolved':
            record.role = 'supporting'
        return record

    # Explicit ids bypass text tokenization and are examined throughout the input.
    for ref in references(search_text):
        if ref.external:
            continue
        targets = [target for div in ((ref.division,) if ref.division else ('A', 'B', 'C'))
                   for target in corpus.targets(div, ref.pid)]
        if not targets:
            gaps.append(RequirementGap(code='unresolved_input_reference', reference=ref.raw,
                                       message='The entered reference is not present in the verified NBC(AE) source and division.'))
        if not ref.division and len({k[0] for k in targets}) > 1:
            gaps.append(RequirementGap(code='ambiguous_input_division', reference=ref.raw,
                                       message='The unqualified identifier exists in multiple divisions; all matches remain candidates.'))
        for target in targets:
            row = corpus.rows.get((target[0], ref.pid))
            add(target, 'explicit', 'An entered identifier resolves in the verified source; applicability is unreviewed.',
                evidence=corpus.evidence(row) if row and row.get('text') else None)

    hits, chunks = corpus.search(search_text)
    for hit in hits:
        evidence = corpus.evidence(hit)
        if 'note_id' in hit:
            targets = corpus.note_articles.get((hit['division'], hit['note_id']), [])
            if not targets:
                gaps.append(RequirementGap(code='unlinked_note', reference=hit['note_id'], evidence=evidence,
                                           message='A matching explanatory note has no verified normative target in this corpus.'))
        else:
            targets = corpus.targets(hit['division'], hit['id'])
        for target in targets:
            add(target, 'lexical', 'A full-text lexical match is a discovery candidate, not a finding of applicability.',
                evidence=evidence)

    # Discover the complete extracted administrative subtree around alternative
    # solutions, rather than hardcoding two process references as the whole set.
    roots = [r for r in corpus.rows.values() if r['division'] in ('A', 'C')
             and _ALTERNATIVE.search(' '.join((r.get('title') or '', r.get('text') or '')))]
    for root in roots:
        for target in corpus.targets(root['division'], root['id']):
            add(target, 'administrative', 'Alternative-solution administrative context from the source and its extracted subtree.',
                evidence=corpus.evidence(root))
            for row in corpus.by_article.get(target, []):
                if row['level'] == 'sentence' and row.get('text'):
                    add(target, 'administrative', 'A sentence within the alternative-solution administrative context; conditions still require review.',
                        evidence=corpus.evidence(row))

    human = _human_seeds(previous, confirmed_provisions)
    old = {r.id: r for r in previous.requirements} if previous else {}
    legacy_changed = bool(previous and previous.input_fingerprint != fingerprint)
    source_changed = bool(previous and previous.requirement_coverage.source != corpus.source)
    for entered, prior in human.items():
        targets = _selected_targets(corpus, entered)
        if not targets:
            gaps.append(RequirementGap(code='unresolved_human_reference', reference=entered,
                                       message='A previous/current human selection could not be verified in this source; it needs review.'))
            continue
        for target in targets:
            record = add(target, 'previous' if prior else 'human',
                         'A human selected this requirement; the selection is retained separately from discovery.')
            prior = prior or old.get(record.id)
            was_confirmed = bool(prior and prior.human_confirmed)
            record.human_confirmed = True
            record.confirmation_fingerprint = prior.confirmation_fingerprint if was_confirmed else fingerprint
            if was_confirmed:
                record.confirmation_reason = prior.confirmation_reason
                record.confirmed_at = prior.confirmed_at
            changed = bool(previous and (legacy_changed or source_changed))
            pending = bool(was_confirmed and prior.needs_review)
            if changed or pending:
                record.applicability, record.needs_review = 'needs_review', True
                record.review_reasons.append('Human confirmation needs review after an input/source change or an unresolved prior review.')
            else:
                record.applicability, record.needs_review = 'confirmed', False
                record.disposition = prior.disposition if was_confirmed else 'include'
                record.review_reasons = []
            if was_confirmed:
                record.role = prior.role
            elif previous and previous.benchmark.departure_status == 'confirmed' and previous.benchmark.provision == target[1]:
                record.role = 'varied'

    # Retain confirmed ledger rows whose source provision disappeared. Their old
    # quotes/citations cannot be presented as verified against the current source.
    retained = []
    for prior in old.values():
        if prior.human_confirmed and prior.id not in {r.id for r in records.values()}:
            retained.append(_unverified_previous(prior))

    graph = build(corpus)
    queue, visited = deque(records), set()
    while queue:
        key = queue.popleft()
        if key in visited:
            continue
        visited.add(key)
        gaps.extend(graph.gaps.get(key, []))
        for direction, edges in (('reference', graph.forward.get(key, [])),
                                 ('reverse_reference', graph.reverse.get(key, []))):
            for edge in edges:
                target = edge.target if direction == 'reference' else edge.origin
                path = paths[key] + [qualified(target)]
                fresh = target not in records
                add(target, direction,
                    ('The source explicitly references this candidate; applicability is unreviewed.' if direction == 'reference' else
                     'This source passage references a discovered requirement; it is a reverse dependency candidate, not proven applicable.'),
                    evidence=edge.evidence, origin=key, path=path)
                if fresh:
                    queue.append(target)
    # Graph-only discoveries still carry unknown scope conditions and are retained.
    for key, record in records.items():
        if graph.gaps.get(key):
            record.review_reasons.append('Source references or external content have unresolved coverage gaps.')
        if not record.human_confirmed:
            record.applicability, record.disposition, record.needs_review = 'unknown', 'review', True
    ordered = [records[k] for k in corpus.articles if k in records] + retained
    for gap in gaps:
        if gap.evidence:
            evidence_pool[gap.evidence.id] = gap.evidence
            gap.evidence_id = gap.evidence.id
            gap.evidence = None
    coverage = RequirementCoverage(
        source=corpus.source, scan_status='scanned', graph_status='traversed_with_gaps' if gaps else 'traversed',
        articles_by_division=dict(Counter(k[0] for k in corpus.articles)),
        provisions_scanned=len(corpus.rows), notes_scanned=len(corpus.notes), query_chunks=chunks,
        discovered=len(ordered), human_confirmed=sum(r.human_confirmed for r in ordered),
        gaps=_dedup_gaps(gaps), limits=LIMITS)
    return ordered, coverage, list(evidence_pool.values())


def _unverified_previous(row: RequirementRecord) -> RequirementRecord:
    return row.model_copy(update=dict(provision_id=None, source_status='unavailable', source_sha256=None,
                                     citation=None, quote=None, quote_provision_id=None, evidence=[], discoveries=[],
                                     evidence_ids=[],
                                     applicability='needs_review', disposition='review', needs_review=True,
                                     review_reasons=['The previous human selection is retained, but its current source could not be verified.']))


def run(prose: str, *, codes: Codes, config: IdentifyConfig, facts=(), previous: IdentifyResult | None = None,
        confirmed_provisions=(), description_sha256: str | None = None, on_stage=None) -> IdentifyResult:
    """Production seam: deterministic discovery with no provider initialization/calls."""
    start = time.monotonic()
    fact_data = [_data(f) for f in facts]
    fingerprint = _fingerprint(prose, fact_data)
    corpus = None
    try:
        corpus = load(codes.db_path)
        records, coverage, evidence_pool = _discover(prose, fact_data, corpus, previous, confirmed_provisions, fingerprint)
        status = 'needs_review'
    except (SourceUnavailable, sqlite3.Error) as exc:
        message = str(exc) if isinstance(exc, SourceUnavailable) else 'Full-text discovery is unavailable for this code source.'
        records = [_unverified_previous(r) for r in (previous.requirements if previous else []) if r.human_confirmed]
        coverage = RequirementCoverage(scan_status='unavailable', limits=LIMITS,
                                        gaps=[RequirementGap(code='source_unavailable', message=message)], discovered=len(records))
        status = 'source_unavailable'
        corpus = None
        evidence_pool = []
    shown = []
    refs = []
    if corpus:
        for record in records:
            if record.division != 'B' or record.source_status != 'verified' or record.provision_id is None:
                continue
            shown.append(_shown(corpus, record, len(shown) + 1))
        for div, pid in (('A', '1.2.1.1.'), ('C', '2.3.1.1.')):
            row = corpus.articles.get((div, pid))
            if row:
                text = '\n'.join(r['text'] for r in corpus.by_article[(div, pid)]
                                 if r['level'] == 'sentence' and r.get('text'))
                refs.append(ProcessRef(division=div, provision_id=pid, title=row.get('title') or '',
                                       citation=corpus.citation(row), text=text, pdf_page=row.get('pdf_page'),
                                       role='Source context for alternative-solution preparation; applicability requires review.'))
    stages = []
    for stage, state in (('screen', 'done' if corpus else 'failed'), ('rerank', 'skipped'),
                         ('verify', 'skipped'), ('questions', 'done')):
        stages.append(StageRecord(stage=stage, method='requirements' if stage == 'screen' else 'none',
                                   detail='Deterministic source discovery; applicability is not scored.' if stage == 'screen' else None))
        if on_stage:
            on_stage(stage, dict(stage=stage, status=state, method='requirements' if stage == 'screen' else 'none',
                                 articles=len(shown), choices=0, committed=0))
    elapsed = round(time.monotonic() - start, 3)
    stages[0].seconds = elapsed
    trace = IdentifyTrace(
        config=config.as_dict(), config_hash=config.config_hash, exhaustive=False,
        articles_expected=coverage.articles_by_division.get('B', 0), articles_scored=0,
        ranker='full-text and explicit-reference requirement discovery', verifier='not run: human applicability review required',
        stages=stages, spend={}, usd=0, seconds=elapsed)
    return IdentifyResult(
        mode='live', source='codedb requirement discovery', narrowed=False,
        label=('Full-text and reference discovery; candidates require human review. Applicable requirements may be missing.' if corpus else
               'The NBC(AE) 2023 second-printing source could not be verified; no current citations were returned.'),
        message='Review the requirement ledger and its coverage gaps. Discovery does not determine a variance or technical compliance.',
        requirements=records, requirement_evidence=evidence_pool, requirement_status=status,
        requirement_coverage=coverage, input_fingerprint=fingerprint,
        articles=shown, benchmark=BenchmarkRecord(identified=False), process_refs=refs,
        model_ids=dict(screen=None, rerank=None, verifier=None),
        commit_policy=dict(status='human_review', reason='Applicability and departures require explicit human decisions.'),
        scored_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
        description_sha256=description_sha256 or hashlib.sha256(prose.encode()).hexdigest(), trace=trace)


def _flat(text: str | None) -> str:
    return ' '.join((text or '').split())


QUOTE_WORDS = 6                                   # the rank prompt asks for a quote of 6 to 40 words


def add_found(result: IdentifyResult, db_path, facts, found: list[tuple[str, str]]) -> list[str]:
    """Add Division B articles the model rank picked that discovery did not reach. Returns the added ids.

    Each row is built from the source like any discovered requirement (title, citation, scope conditions,
    Section C terms); the model contributes only the choice of article and a quote, which must be word for
    word in that article. The quote's sentence, when exactly one holds it, is its evidence. Applicability
    stays unreviewed.
    """
    present = {r.provision_id for r in result.requirements if r.division == 'B'}
    found = [(article, quote) for article, quote in dict(found).items() if article not in present and _flat(quote)]
    if not found or result.requirement_coverage.source is None:
        return []
    corpus, texts = load(db_path), articles(Path(db_path))
    if corpus.source != result.requirement_coverage.source:
        return []
    fact_data = [_data(f) for f in facts]
    added = []
    for article, quote in found:
        key, quote = ('B', article), _flat(quote)
        body = _flat(texts[article]['text']) if article in texts else ''
        # The card the model read starts with the title and headings; only the article's own text is a quote.
        if key not in corpus.articles or len(quote.split()) < QUOTE_WORDS or quote not in body:
            continue
        sentences = [r for r in corpus.by_article.get(key, [])
                     if r['level'] == 'sentence' and quote in _flat(r.get('text'))]
        evidence = corpus.evidence(sentences[0]) if len(sentences) == 1 else None
        record = _record(corpus, key, fact_data)
        record.quote, record.quote_provision_id = quote, evidence.provision_id if evidence else None
        record.discoveries.append(RequirementDiscovery(
            kind='model_search', path=[record.id], evidence_id=evidence.id if evidence else None,
            evidence_ids=[evidence.id] if evidence else [],
            detail='The model rank picked this article and its quote is word for word in the source; applicability is unreviewed.'))
        if evidence:
            record.evidence, record.evidence_ids = [evidence], [evidence.id]
        result.requirements.append(record)
        result.articles.append(_shown(corpus, record, len(result.articles) + 1, 'verifier'))
        added.append(article)
    result.requirement_coverage.discovered += len(added)
    return added
