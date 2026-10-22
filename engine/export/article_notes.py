"""Section C identification notes for the appendix: how each row reached the case, and the quoted sentence.

Adapted from PR #25 (``backend/export-appendix``): identify output is used only when it is already stored on the
case, and a stored quote is kept only when its words are found in the code database. Nothing here calls the
identify pipeline or a model. The quoted benchmark sentence is always re-read from the code database.
"""
from __future__ import annotations

import re

from ..models import Case
from ..process_fields import confirmed_value

_ARTICLE = re.compile(r'^(\d+\.\d+\.\d+\.\d+\.)')    # same rule as engine.identify.decisions.article_of


def article_of(provision_id: str) -> str:
    match = _ARTICLE.match(provision_id or '')
    return match.group(1) if match else provision_id


def _flat(text: str | None) -> str:
    return re.sub(r'\s+', ' ', text or '').strip()


def _card(case: Case, provision_id: str):
    result = case.identify
    if result is None:
        return None
    article = article_of(provision_id)
    return next((a for a in result.articles if a.provision == article), None)


def row_basis(case: Case, provision_id: str) -> str:
    """Where a Section C row came from. A ranking or a commit is never the decision; the applicant's is."""
    result, article = case.identify, article_of(provision_id)
    card = _card(case, provision_id)
    decision = result.decisions.get(article) if result else None
    confirmed = (decision is not None and decision.decision == 'yes') or \
        confirmed_value(case, f'citation.{article}') is not None
    if result is not None and (article in result.committed or (card is not None and card.status == 'committed')):
        found = 'Committed by code identification'
    elif card is not None:
        found = 'Listed by code identification'
    else:
        found = 'Entered by the applicant (no code identification record)'
    # Without a recorded yes or citation fact, say only what is known: the provision is in the case's benchmark
    # list (the confirm route), with no recorded decision on this article.
    how = 'confirmed by the applicant' if confirmed or card is None else \
        "in the case's benchmark list; no applicant decision is recorded for this article"
    return f'{found}; {how}.'


def identify_quote(case: Case, provision_id: str, codes) -> str | None:
    """The identification quote, only when it is word for word in the code database text of the article."""
    card = _card(case, provision_id)
    if card is None or not card.quote or codes is None:
        return None
    rec = codes.provision(card.provision, 'B')
    return _flat(card.quote) if rec and _flat(card.quote) in _flat(rec.get('text')) else None


def benchmark(case: Case, codes) -> dict | None:
    """The benchmark acceptable solution recorded by identification, re-read from the code database."""
    result = case.identify
    rec_id = result.benchmark.provision_id or result.benchmark.provision if result and result.benchmark.identified else None
    rec = codes.provision(rec_id, 'B') if rec_id and codes is not None else None
    if rec is None:
        return None
    bench = result.benchmark
    departure = bench.departure if bench.departure_status == 'confirmed' and bench.departure else None
    return {'provision_id': rec['id'], 'citation': rec['citation'], 'sentence': rec.get('text') or '',
            'departure': departure, 'departure_status': bench.departure_status}
