"""The API-visible output of one run as plain text, plus the pieces the deterministic checks read.

`report` is what the judge reads: every part of the case an applicant or officer can be shown after
intake, identification and the plan, in a fixed order. `system_text` is the text Batatis writes in
its own voice (never a quote from a document or from the code), for the claim guardrail.
`provisions` is every provision id the output presents, for the article and citation checks.
"""
from __future__ import annotations

import re

ARTICLE = re.compile(r'(?<![\d.])(\d{1,2}\.\d{1,2}\.\d{1,2}\.\d{1,3})\.?(?:\(\d+\)(?:\([a-z]+\))?)?')


def _val(value) -> str:
    return value if isinstance(value, str) else repr(value)


def _origin(case: dict, fact: dict) -> str:
    source = fact.get('source') or {}
    if source.get('type') == 'file':
        names = {f['file_id']: f['name'] for f in (case.get('intake') or {}).get('files') or []}
        page = f' p.{source["page"]}' if source.get('page') else ''
        return f'{names.get(source.get("ref"), source.get("ref"))}{page}'
    return 'request text'


def _redirected(case: dict) -> bool:
    """The web skips identification when intake redirects to another regime, so nothing of it is shown."""
    plan = (case.get('intake') or {}).get('plan') or {}
    return (plan.get('scope') or {}).get('status') == 'redirect'


def _where(case: dict, ref: dict) -> str:
    names = {f['file_id']: f['name'] for f in (case.get('intake') or {}).get('files') or []}
    if ref.get('source_ref') == 'description':
        return 'request text'
    page = f' p.{ref["page"]}' if ref.get('page') else ''
    return f'{names.get(ref.get("source_ref"), ref.get("source_ref"))}{page}'


def _quotes(case: dict, refs: list[dict]) -> str:
    return ' / '.join(f'"{r["quote"]}" ({_where(case, r)})' for r in refs)


def _review(case: dict) -> list[str]:
    review = (case.get('intake') or {}).get('review') or {}
    if review.get('status') not in ('live', 'fake'):
        return []
    names = {f['file_id']: f['name'] for f in (case.get('intake') or {}).get('files') or []}
    out = ['DOCUMENT REVIEW']
    for d in review.get('documents') or []:
        parts = [d.get('kind'), d.get('title'), d.get('author'), d.get('date'), d.get('status')]
        out.append(f'- {names.get(d["file_id"], d["file_id"])}: ' + '; '.join(x for x in parts if x))
    if review.get('flags'):
        out.append('Flags:')
        out += [f'- [{f["kind"]}] {f["text"]}' for f in review['flags']]
    if review.get('facts'):
        out.append('Facts:')
        for f in review['facts']:
            quoted = '' if f['text'] == f['evidence'][0]['quote'] else f' {_quotes(case, f["evidence"])}'
            where = f' ({_where(case, f["evidence"][0])})' if not quoted else ''
            out.append(f'- [{f["status"]}] {f["text"]}{quoted}{where}')
    if review.get('conflicts'):
        out.append('Conflicts:')
        out += [f'- {c["text"]} {_quotes(case, c["evidence"])}' for c in review['conflicts']]
    if review.get('provisions'):
        out.append('Provisions the documents cite:')
        for p in review['provisions']:
            code = f' ({p["code"]})' if p.get('code') else ''
            match = (f'; in NBC(AE) 2023 2nd printing this resolves to {p["resolves_to"]} (Division {p["division"]})'
                     if p.get('resolves_to') else '; not matched to an NBC(AE) 2023 provision')
            out.append(f'- {p["cited"]}{code}{match} ({_where(case, p["evidence"][0])})')
    if review.get('missing'):
        out.append('Missing for a complete application or review:')
        out += [f'- {m["text"]} (why: {m["why"]})' for m in review['missing']]
    if review.get('questions'):
        out.append('Questions to ask next:')
        out += [f'- {q["text"]} (why: {q["why"]})' for q in review['questions']]
    return out


def report(result: dict) -> str:
    case = result.get('case')
    if not case:
        return 'NO OUTPUT: the run failed before the case was built.\n' + '\n'.join(result.get('errors') or [])
    intake = case.get('intake') or {}
    plan = intake.get('plan') or {}
    lines: list[str] = []

    lines.append('DOCUMENTS')
    for f in intake.get('files') or []:
        read = f'{len(f.get("pages_read") or [])} of {f.get("pages") or 0} pages read'
        why = f'; {f["reason"]}' if f.get('reason') else ''
        lines.append(f'- {f["name"]}: {f["status"]} ({read}){why}')

    lines += _review(case)

    scope = plan.get('scope') or {}
    if scope:
        lines.append('SCOPE')
        regime = scope.get('regime') or {}
        text = scope.get('status', '')
        if regime:
            text += f': {regime.get("name")} ({regime.get("code")}); take it to {regime.get("route")}'
        if scope.get('message'):
            text += f'. {scope["message"]}'
        lines.append('- ' + text)
    fork = plan.get('fork') or {}
    if fork:
        lines.append(f'- Alternative-solution path: {fork.get("variance_needed")}. {fork.get("explanation", "")}')

    # Facts read from the request only repeat the user's own words; the judge never credits them for a
    # review or boundary point. Facts read from the attached files come second.
    facts = [f for f in case.get('facts') or [] if f.get('field') != 'project.description']
    for title, from_request in (('FROM THE REQUEST TEXT (the user\'s own words, repeated)', True),
                                ('FACTS READ FROM THE DOCUMENTS (unconfirmed until the applicant confirms them)', False)):
        group = [f for f in facts if ((f.get('source') or {}).get('type') != 'file') == from_request]
        if not group:
            continue
        lines.append(title)
        for fact in group:
            value, quote = _val(fact.get('value')), (fact.get('source') or {}).get('quote') or ''
            shown = f'"{value}"' if value == quote or not quote else f'{value} ("{quote}")'
            label = 'statement' if str(fact.get('field', '')).startswith('statement.') else fact.get('field')
            status = '' if fact.get('kind') in ('pointed', 'exact', 'computed') else f' [{fact.get("kind")}]'
            lines.append(f'- [{_origin(case, fact)}] {label}: {shown}{status}')

    if intake.get('conflicts'):
        lines.append('CONFLICTS')
        for c in intake['conflicts']:
            quotes = ' / '.join(f'"{q}"' for q in c.get('quotes') or [])
            lines.append(f'- {c["field"]}: {", ".join(_val(v) for v in c.get("values") or [])} ({quotes})')
    if intake.get('unresolved_citations'):
        lines.append('CITATIONS NOT FOUND IN NBC(AE) 2023 2ND PRINTING')
        for u in intake['unresolved_citations']:
            lines.append(f'- {u["entered"]}')

    identify = None if _redirected(case) else case.get('identify')
    if identify:
        lines.append('CODE IDENTIFICATION')
        if identify.get('label'):
            lines.append(f'- {identify["label"]}')
        if identify.get('message'):
            lines.append(f'- {identify["message"]}')
        for article in identify.get('articles') or []:
            p = article.get('probability')
            score = f', relevance {p:.2f}' if isinstance(p, (int, float)) else ''
            lines.append(f'- {article["rank"]}. {article["provision"]} {article.get("title") or ""} '
                         f'[{article.get("status")}{score}]')
        for q in identify.get('questions') or []:
            lines.append(f'- Question: {q}')

    if plan.get('questions'):
        lines.append('QUESTIONS FOR THE APPLICANT')
        for q in plan['questions']:
            lines.append(f'- {q["text"]} (why: {q.get("why", "")})')
    steps = (plan.get('pre_application') or {}).get('steps') or []
    if steps:
        lines.append('BEFORE YOU APPLY')
        for s in steps:
            lines.append(f'- {s["title"]}: {s["text"]}')
    if plan.get('route_notice'):
        lines.append('ROUTE NOTICE')
        lines.append('- ' + plan['route_notice']['summary'])

    gaps = result.get('gaps') or []
    if gaps:
        lines.append('MISSING FOR A COMPLETE APPLICATION')
        for g in gaps:
            lines.append(f'- [Section {g["section"]}] {g["message"]}')
    return '\n'.join(lines)


def system_text(result: dict) -> list[str]:
    """Batatis's own sentences: scope, fork, questions, labels, steps, notes and gaps. Never document quotes."""
    case = result.get('case') or {}
    intake = case.get('intake') or {}
    plan = intake.get('plan') or {}
    review = intake.get('review') or {}
    out = [f.get('text', '') for f in review.get('flags') or []]
    out += [f'{m.get("text", "")} {m.get("why", "")}' for m in [*(review.get('missing') or []), *(review.get('questions') or [])]]
    out += [f.get('text', '') for f in review.get('facts') or []
            if f.get('text') not in {e.get('quote') for e in f.get('evidence') or []}]
    out += [c.get('text', '') for c in review.get('conflicts') or []]
    out += [d.get('status') or '' for d in review.get('documents') or []]
    scope = plan.get('scope') or {}
    out += [scope.get('message') or '']
    out += [(plan.get('fork') or {}).get('explanation') or '']
    out += [q.get('text', '') + ' ' + q.get('why', '') for q in plan.get('questions') or []]
    identify = {} if _redirected(case) else case.get('identify') or {}
    out += [identify.get('label') or '', identify.get('message') or '']
    out += [s.get('text', '') for s in (plan.get('pre_application') or {}).get('steps') or []]
    out += [g.get('message', '') for g in result.get('gaps') or []]
    return [t for t in out if t]


def provisions(result: dict) -> set[str]:
    """Article ids (a.b.c.d.) the output presents: identified articles, claimed provisions and any in Batatis's text."""
    case = result.get('case') or {}
    found: set[str] = set()
    for article in ({} if _redirected(case) else case.get('identify') or {}).get('articles') or []:
        m = ARTICLE.match(str(article.get('provision') or ''))
        if m:
            found.add(m.group(1) + '.')
    for fact in case.get('facts') or []:
        if fact.get('field') == 'claimed_provision':
            m = ARTICLE.match(str(fact.get('value') or ''))
            if m:
                found.add(m.group(1) + '.')
    for text in system_text(result):
        found |= {m.group(1) + '.' for m in ARTICLE.finditer(text)}
    for cited in ((case.get('intake') or {}).get('review') or {}).get('provisions') or []:
        m = ARTICLE.match(str(cited.get('resolves_to') or ''))
        if m:
            found.add(m.group(1) + '.')
    return found
