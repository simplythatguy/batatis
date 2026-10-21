"""The applicant's yes, no or not sure on identified articles.

Ported from PR #12. A model ranking, even a commit, is not a decision: only `yes` adds the article
to the case's provisions and Section C (by lookup). #12 stored not_sure as a fact with status
`open`; dev's facts have no such status, so decisions live on the stored identify result
(`case.identify.decisions`), and `yes` also leaves a confirmed `citation.<article>` user_click fact
as the audit trail. The same decision twice leaves one citation or one question.
"""
from __future__ import annotations

import hashlib
import re

from engine.completeness import Gap
from engine.models import Fact, Source, now
from engine.models_identify import ArticleDecision, IdentifyResult
from engine.section_c import section_c_rows

_ARTICLE = re.compile(r'^(\d+\.\d+\.\d+\.\d+\.)')
DECISIONS = ('yes', 'no', 'not_sure')
CITATION_PREFIX = 'citation.'


def article_of(provision_id: str) -> str:
    match = _ARTICLE.match(provision_id or '')
    return match.group(1) if match else provision_id


def question_text(article: str, title: str | None) -> str:
    named = f'{article} ({title})' if title else article
    return (f'Does Division B Article {named} apply to this proposal? '
            'A model ranking is not a decision that it applies.')


def stable_id(case_id: str, kind: str, article: str) -> str:
    return f'{kind}_' + hashlib.sha256(f'{case_id}:{kind}:{article}'.encode()).hexdigest()[:12]


def match_article(result: IdentifyResult, provision_id: str):
    wanted = provision_id or ''
    for article in result.articles:
        if wanted in {article.provision, article.provision_id} or article.provision == article_of(wanted):
            return article
    raise KeyError(provision_id)


def overlay_decisions(result: IdentifyResult) -> IdentifyResult:
    """Copy stored decisions onto the article cards. Does not write the case."""
    for article in result.articles:
        chosen = result.decisions.get(article.provision)
        article.decision = chosen.decision if chosen else None
        article.open_question_id = chosen.open_question_id if chosen and chosen.decision == 'not_sure' else None
    return result


def record_decision(case, provision_id: str, decision: str, codes) -> list:
    """Apply one decision to `case` (its identify result must exist). Returns the Section C rows a yes wrote."""
    if decision not in DECISIONS:
        raise ValueError(decision)
    result: IdentifyResult = case.identify
    card = match_article(result, provision_id)
    article = card.provision
    case.facts = [f for f in case.facts if f.field != f'{CITATION_PREFIX}{article}']
    case.provisions = [p for p in case.provisions if p != article]
    written = []
    if decision == 'yes':
        record = codes.provision(article, 'B') if codes is not None else None
        if record is None:
            raise KeyError(article)
        case.facts.append(Fact(id=stable_id(case.id, 'cite', article), field=f'{CITATION_PREFIX}{article}',
                               value=article, kind='exact', status='confirmed',
                               source=Source(type='user_click', ref=article, quote=record.get('citation'))))
        case.provisions = list(dict.fromkeys([*case.provisions, article]))
    case.section_c = section_c_rows(case.provisions, codes) if case.provisions else []
    if decision == 'yes':
        written = [row for row in case.section_c if article_of(row.provision_id) == article]
    result.decisions[article] = ArticleDecision(
        decision=decision, decided_at=now(),
        open_question_id=stable_id(case.id, 'oq', article) if decision == 'not_sure' else None)
    overlay_decisions(result)
    return written


def information_request(case) -> dict:
    """Officer draft: one item per not_sure decision."""
    items = []
    result: IdentifyResult | None = case.identify
    for article, chosen in (result.decisions.items() if result else []):
        if chosen.decision != 'not_sure':
            continue
        title = next((a.title for a in result.articles if a.provision == article), None)
        items.append({'id': chosen.open_question_id, 'provision_id': article, 'text': question_text(article, title)})
    return {'case_id': case.id, 'items': items}


def decision_gaps(case, codes=None) -> list[Gap]:
    """One warning gap per not_sure decision, for the completeness list (not wired into /gaps here)."""
    gaps = []
    for item in information_request(case)['items']:
        gaps.append(Gap(id=item['id'], section='C', field=f"identify.{item['provision_id']}", message=item['text'],
                        severity='warning', citation=codes.citation(item['provision_id'], 'B') if codes else None,
                        fix_hint='Ask the applicant whether this article applies. The question does not decide it.'))
    return gaps
