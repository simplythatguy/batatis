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


def match_article(result: IdentifyResult, provision_id: str) -> str:
    """The article a decision on `provision_id` is about: an identified article card, or a verified
    Division B rule in the requirement ledger (a requirement run keeps no article cards)."""
    wanted = provision_id or ''
    article = article_of(wanted)
    for card in result.articles:
        if wanted in {card.provision, card.provision_id} or card.provision == article:
            return card.provision
    for item in result.requirements:
        if item.division == 'B' and item.source_status == 'verified' and item.provision_id == article:
            return article
    raise KeyError(provision_id)


def overlay_decisions(result: IdentifyResult) -> IdentifyResult:
    """Copy stored decisions onto the article cards. Does not write the case."""
    for article in result.articles:
        chosen = result.decisions.get(article.provision)
        article.decision = chosen.decision if chosen else None
        article.open_question_id = chosen.open_question_id if chosen and chosen.decision == 'not_sure' else None
    return result


def record_departure(case, provision_id: str, codes, *, reason: str | None = None) -> list:
    """Name `provision_id` as an acceptable solution the design departs from.

    Writes the citation fact, keeps the article in `case.provisions`, rebuilds Section C and marks
    the Division B requirement varied. Returns the Section C rows written for that article. The
    code-check card and the benchmark confirmation both come through here, so a departure leaves
    the same state whichever route recorded it.
    """
    article = article_of(provision_id)
    result: IdentifyResult = case.identify
    record = codes.provision(article, 'B') if codes is not None else None
    if record is None:
        raise KeyError(article)
    # A named sentence stays that sentence, beside any other sentence of the article the applicant said
    # differs: Section C lists what differs, not every sentence of the article.
    chosen = provision_id if provision_id != article and codes.provision(provision_id, 'B') else article
    case.facts = [f for f in case.facts if f.field != f'{CITATION_PREFIX}{article}']
    case.provisions = [p for p in case.provisions
                       if article_of(p) != article or (chosen != article and p not in (article, chosen))]
    case.facts.append(Fact(id=stable_id(case.id, 'cite', article), field=f'{CITATION_PREFIX}{article}',
                           value=article, kind='exact', status='confirmed',
                           source=Source(type='user_click', ref=article, quote=record.get('citation'))))
    case.provisions = list(dict.fromkeys([*case.provisions, chosen]))
    case.section_c = section_c_rows(case.provisions, codes) if case.provisions else []
    result.decisions[article] = ArticleDecision(decision='yes', decided_at=now(), open_question_id=None)
    from .requirement_decisions import departure
    departure(result, article, 'yes', reason=reason)
    overlay_decisions(result)
    return [row for row in case.section_c if article_of(row.provision_id) == article]


def record_decision(case, provision_id: str, decision: str, codes) -> list:
    """Apply one decision to `case` (its identify result must exist). Returns the Section C rows a yes wrote."""
    if decision not in DECISIONS:
        raise ValueError(decision)
    result: IdentifyResult = case.identify
    article = match_article(result, provision_id)
    # A card on one sentence decides that sentence, as the benchmark route does: Section C lists what differs.
    named = provision_id if article_of(provision_id) == article else article
    if decision == 'yes':
        return record_departure(case, named, codes)
    if named == article:
        case.provisions = [p for p in case.provisions if article_of(p) != article]   # the article and its sentences
    else:
        case.provisions = [p for p in case.provisions if p not in (article, named)]
    case.section_c = section_c_rows(case.provisions, codes) if case.provisions else []
    if any(article_of(p) == article for p in case.provisions):
        return []   # another sentence of this rule still differs, so its citation and Yes stand
    case.facts = [f for f in case.facts if f.field != f'{CITATION_PREFIX}{article}']
    result.decisions[article] = ArticleDecision(
        decision=decision, decided_at=now(),
        open_question_id=stable_id(case.id, 'oq', article) if decision == 'not_sure' else None)
    from .requirement_decisions import departure
    departure(result, article, decision)
    overlay_decisions(result)
    return []


def information_request(case) -> dict:
    """Officer draft: one item per not_sure decision."""
    items = []
    result: IdentifyResult | None = case.identify
    for article, chosen in (result.decisions.items() if result else []):
        if chosen.decision != 'not_sure':
            continue
        title = next((a.title for a in result.articles if a.provision == article), None) or next(
            (r.title for r in result.requirements if r.division == 'B' and r.provision_id == article), None)
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
