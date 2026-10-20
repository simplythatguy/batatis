"""Human decisions on identify articles.

A model probability is a ranking hint. It does not add a citation to the case.
The applicant decides yes, no, or not sure for each ranked article.
"""
from __future__ import annotations

import hashlib
import re

from engine.completeness import Gap
from engine.models import Fact, Source

_ARTICLE = re.compile(r'^(\d+\.\d+\.\d+\.\d+\.)')
DECISIONS = {'yes', 'no', 'not_sure'}
CITATION_PREFIX = 'citation.'
QUESTION_PREFIX = 'open_question.'


def article_of(provision_id: str) -> str:
    match = _ARTICLE.match(provision_id or '')
    return match.group(1) if match else provision_id


def question_text(article: str, title: str | None) -> str:
    named = f'{article} ({title})' if title else article
    return (f'Does Division B Article {named} apply to this proposal? '
            'A model ranking is not a decision that it applies.')


def _stable_id(case_id: str, kind: str, article: str) -> str:
    digest = hashlib.sha256(f'{case_id}:{kind}:{article}'.encode()).hexdigest()[:12]
    return f'{kind}_{digest}'


def _article_from_field(field: str, prefix: str) -> str | None:
    if field.startswith(prefix):
        return field[len(prefix):]
    return None


def match_article(result: dict, provision_id: str) -> dict:
    """The ranked article addressed by an article id or a sentence id."""
    wanted = provision_id or ''
    wanted_article = article_of(wanted)
    for article in result.get('articles') or []:
        provision = article.get('provision') or ''
        sentence = article.get('provision_id') or ''
        if wanted in {provision, sentence} or provision == wanted_article:
            return article
    raise KeyError(provision_id)


def overlay_decisions(result: dict, case) -> dict:
    """Copy stored decisions onto identify articles. Does not write the case."""
    by_article: dict[str, dict] = {}
    for fact in case.facts:
        article = _article_from_field(fact.field, CITATION_PREFIX)
        if article and fact.source.type == 'user_click' and fact.status == 'confirmed':
            by_article[article] = {'decision': 'yes', 'open_question_id': None}
        article = _article_from_field(fact.field, QUESTION_PREFIX)
        if article and fact.status == 'open':
            by_article[article] = {'decision': 'not_sure', 'open_question_id': fact.id}
    excluded = set()
    for article in result.get('articles') or []:
        key = article.get('provision') or ''
        marker = (result.get('decisions') or {}).get(key) or {}
        if marker.get('decision') == 'no':
            excluded.add(key)
    for article in result.get('articles') or []:
        key = article.get('provision') or ''
        chosen = by_article.get(key)
        if chosen:
            article['decision'] = chosen['decision']
            article['open_question_id'] = chosen['open_question_id']
        elif key in excluded:
            article['decision'] = 'no'
            article['open_question_id'] = None
        else:
            article['decision'] = article.get('decision') if article.get('decision') in DECISIONS else None
            if article['decision'] != 'not_sure':
                article['open_question_id'] = None
        article['excluded'] = article.get('decision') == 'no'
    return result


def _drop(case, article: str) -> None:
    case.facts = [fact for fact in case.facts
                  if _article_from_field(fact.field, CITATION_PREFIX) != article
                  and _article_from_field(fact.field, QUESTION_PREFIX) != article]


def _remember_no(result: dict, article: str) -> None:
    decisions = dict(result.get('decisions') or {})
    decisions[article] = {'decision': 'no'}
    result['decisions'] = decisions


def _forget_no(result: dict, article: str) -> None:
    decisions = dict(result.get('decisions') or {})
    decisions.pop(article, None)
    result['decisions'] = decisions


def record_decision(case, result: dict, provision_id: str, decision: str, codes) -> dict:
    """Apply one decision. The same decision twice leaves one citation or one question."""
    if decision not in DECISIONS:
        raise ValueError(decision)
    article_row = match_article(result, provision_id)
    article = article_row.get('provision') or article_of(provision_id)
    _drop(case, article)
    case.provisions = [item for item in case.provisions if item != article]
    if decision == 'yes':
        record = None
        if codes is not None:
            record = codes.provision(article, 'B')
        if record is None:
            raise KeyError(article)
        case.facts.append(Fact(
            id=_stable_id(case.id, 'cite', article),
            field=f'{CITATION_PREFIX}{article}',
            value=article,
            kind='exact',
            source=Source(type='user_click', ref=article, quote=record.get('citation')),
            status='confirmed',
        ))
        case.provisions = list(dict.fromkeys([*case.provisions, article]))
        from engine.section_c import section_c_rows
        case.section_c = section_c_rows(case.provisions, codes)
        _forget_no(result, article)
    elif decision == 'not_sure':
        text = question_text(article, article_row.get('title'))
        case.facts.append(Fact(
            id=_stable_id(case.id, 'oq', article),
            field=f'{QUESTION_PREFIX}{article}',
            value=text,
            kind='exact',
            source=Source(type='user_click', ref=article, quote=text),
            status='open',
        ))
        case.section_c = _refresh_section_c(case, codes)
        _forget_no(result, article)
    else:
        case.section_c = _refresh_section_c(case, codes)
        _remember_no(result, article)
    overlay_decisions(result, case)
    return result


def _refresh_section_c(case, codes):
    if codes is None:
        kept = set(case.provisions)
        return [row for row in case.section_c if row.provision_id in kept or article_of(row.provision_id) in kept]
    if not case.provisions:
        return []
    from engine.section_c import section_c_rows
    return section_c_rows(case.provisions, codes)


def decision_gaps(case, codes=None) -> list[Gap]:
    """Open identify questions, one gap each, with the stable question id."""
    gaps = []
    for fact in case.facts:
        article = _article_from_field(fact.field, QUESTION_PREFIX)
        if not article or fact.status != 'open':
            continue
        citation = None
        if codes is not None:
            try:
                citation = codes.citation(article, 'B')
            except Exception:
                citation = None
        gaps.append(Gap(
            id=fact.id,
            section='C',
            field=f'identify.{article}',
            message=str(fact.value or question_text(article, None)),
            severity='warning',
            fix_hint=('Ask the applicant whether this article applies. '
                      'The question does not decide that it applies.'),
            citation=citation,
        ))
    return gaps


def information_request(case) -> dict:
    """Officer draft. Each not_sure decision is one item."""
    items = []
    for fact in case.facts:
        article = _article_from_field(fact.field, QUESTION_PREFIX)
        if not article or fact.status != 'open':
            continue
        items.append({'id': fact.id, 'provision_id': article, 'text': str(fact.value or '')})
    return {'case_id': case.id, 'items': items}
