"""Per-article explainer and benchmark acceptable solution for the appendix.

Identify output from PR #12 is used only when it is already stored on the case
and the quoted words are in the code database. This branch does not call the
identify pipeline. Missing identify output or a missing database degrades to a
codedb snippet, or to no quotation at all. Snippets are at most 25 words.
Citations come from ``codes.citation`` and are omitted when that lookup is empty.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# NRC Publications Archive record for NBC(AE) 2023, already cited in the repo research notes.
NRC_NBC_AE_2023 = 'https://doi.org/10.4224/hz98-7h49'
SNIPPET_WORDS = 25


@dataclass(frozen=True)
class ArticleNote:
    provision_id: str
    explainer: str
    benchmark: str
    citation: str | None
    source_url: str | None


def snippet(text: str | None, limit: int = SNIPPET_WORDS) -> str | None:
    words = [word for word in re.sub(r'\s+', ' ', text or '').strip().split(' ') if word]
    if not words:
        return None
    return ' '.join(words[:limit])


def _flat(text: str | None) -> str:
    return re.sub(r'\s+', ' ', text or '').strip()


def _stored_text(case, provision_id: str) -> str | None:
    """Explainer text already on the case: a fact, or a Section C explainer object from #12."""
    fields = {f'identify.{provision_id}.explainer', f'explainer.{provision_id}'}
    found = None
    for fact in case.facts:
        if fact.field in fields and fact.export()['status'] == 'confirmed' and fact.value:
            found = str(fact.value)
    for row in case.section_c:
        if row.provision_id != provision_id:
            continue
        extra = getattr(row, 'explainer', None)
        quote = None
        if extra is not None:
            quote = extra.get('quote') if isinstance(extra, dict) else getattr(extra, 'quote', None)
        if quote:
            found = str(quote)
    return found


def _stored_benchmark_id(case, provision_id: str) -> str | None:
    fields = {
        'benchmark_acceptable_solution',
        f'identify.{provision_id}.benchmark',
        f'benchmark.{provision_id}',
    }
    found = None
    for fact in case.facts:
        if fact.field in fields and fact.export()['status'] == 'confirmed' and isinstance(fact.value, str) and fact.value.strip():
            found = fact.value.strip()
    return found


def _record(codes, provision_id: str) -> dict | None:
    if codes is None:
        return None
    try:
        rec = codes.provision(provision_id, 'B')
    except (ValueError, KeyError):
        return None
    return rec if isinstance(rec, dict) else None


def _citation(codes, provision_id: str) -> str | None:
    if codes is None:
        return None
    try:
        citation = codes.citation(provision_id, 'B')
    except (ValueError, KeyError):
        return None
    return citation if isinstance(citation, str) and citation.strip() else None


def _accepted_snippet(stored: str | None, codedb_text: str | None) -> str | None:
    """Keep a stored quote only when those words appear in the code database."""
    codedb = snippet(codedb_text)
    if not codedb:
        return None
    if not stored:
        return codedb
    kept = snippet(stored)
    if kept and kept in _flat(codedb_text):
        return kept
    return codedb


def notes_for(case, row, codes) -> ArticleNote:
    provision_id = row.provision_id
    rec = _record(codes, provision_id)
    codedb_text = rec.get('text') if rec else None
    citation = _citation(codes, provision_id)
    used = _accepted_snippet(_stored_text(case, provision_id), codedb_text)
    if used and citation:
        explainer = f'{provision_id}: {used}'
        source_url = NRC_NBC_AE_2023
    elif used:
        explainer = f'{provision_id}: {used} No citation is attached because the code database did not return one.'
        source_url = None
    else:
        explainer = f'{provision_id}: no code-database sentence is available. No citation is supplied.'
        source_url = None

    benchmark_id = _stored_benchmark_id(case, provision_id) or provision_id
    bench_rec = rec if benchmark_id == provision_id else _record(codes, benchmark_id)
    bench_citation = citation if benchmark_id == provision_id else _citation(codes, benchmark_id)
    bench_snippet = snippet(bench_rec.get('text')) if bench_rec else None
    if bench_snippet and bench_citation:
        benchmark = (f'The benchmark acceptable solution is {benchmark_id}. {bench_snippet}')
        if source_url is None:
            source_url = NRC_NBC_AE_2023
        if citation is None:
            citation = bench_citation
    elif benchmark_id != provision_id and bench_rec is None:
        benchmark = ('Identify stored a benchmark that is not in the code database. '
                     'No citation is given for it. '
                     f'The cited provision on this row remains {provision_id}.')
    else:
        benchmark = (f'The benchmark acceptable solution for this row is the cited provision {provision_id}. '
                     'No code-database sentence is available, so no quotation is given.')
    return ArticleNote(provision_id, explainer, benchmark, citation if used or bench_snippet else citation, source_url)
