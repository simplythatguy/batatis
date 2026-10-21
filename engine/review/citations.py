"""Verify cited provisions and compare Section C rows with the Division B attribution tables.

Every check is a database lookup. Nothing here says a provision applies or that
a design meets it; mismatches name both values and ask the applicant.
"""
from __future__ import annotations

import re

from ..models_review import CitationCheck, CitationIssue, Pointer, SectionCCheck

PROVISION = re.compile(r'(?<![\w.])\d{1,2}(?:\.\d{1,3}){3}\.?(?:\s*\(\d{1,2}\))?(?:\s*\([a-z]{1,2}\))?')
CODE_TOKEN = re.compile(r'\b(?:O[SHPAE]\d(?:\.\d+)*|OA\d|F\d{2})\b')
_PAGE = re.compile(r'\bPDF\s+p{1,2}\.?\s*(\d+)', re.I)
_NO_ROW = re.compile(r'no (?:table )?row', re.I)
_APPENDIX = re.compile(r'\bsee appendix\b|\bappendix [A-Z]-?\d', re.I)


def provision_ids(text: str) -> list[str]:
    """Provision tokens as written, normalised to the codedb id shape (spaces removed, article dot kept)."""
    out = []
    for match in PROVISION.finditer(text or ''):
        token = re.sub(r'\s+', '', match.group(0))
        if '(' in token and not re.search(r'\d\.\(', token):
            token = token.replace('(', '.(', 1)
        if '(' not in token and not token.endswith('.'):
            token += '.'
        out.append(token)
    return list(dict.fromkeys(out))


def _lookup(codes, pid: str):
    try:
        return codes.provision(pid, 'B')
    except Exception:  # noqa: BLE001 - malformed or ambiguous ids are reported as not found
        return None


def verify_citation(text: str, pointer: Pointer, codes) -> list[CitationCheck]:
    """One check per provision id in `text`. With no database, every result is lookup-skipped (None)."""
    ids = provision_ids(text)
    if not ids:
        return []
    report = None
    if codes is not None:
        from codedb.validator import validate_text
        try:
            report = validate_text(text, db_path=codes.db_path)
        except Exception:  # noqa: BLE001
            report = None
    out = []
    for pid in ids:
        if codes is None:
            out.append(CitationCheck(text=text, provision_id=pid, pointer=pointer,
                                     issues=[CitationIssue(code='lookup_skipped',
                                                           message='The code database is not available; not verified.')]))
            continue
        record = _lookup(codes, pid)
        issues = []
        if report is not None:
            for error in report['errors'] + report['warnings']:
                cited = re.sub(r'\s+', '', error.get('citation') or '')
                if cited and _same_provision(cited, pid):
                    issues.append(CitationIssue(code=error['code'], message=error['message']))
                elif error['code'] in ('superseded_edition',) and not cited:
                    issues.append(CitationIssue(code=error['code'], message=error['message']))
        codes_seen = {issue.code for issue in issues}
        if record is None and 'nonexistent_provision' not in codes_seen:
            issues.append(CitationIssue(code='nonexistent_provision',
                                        message=f'{pid} was not found in NBC(AE) 2023, 2nd printing, Division B.'))
        edition_ok = 'superseded_edition' not in codes_seen
        page = _PAGE.search(text)
        page_ok = None
        if page and record is not None:
            page_ok = 'page_mismatch' not in codes_seen
        out.append(CitationCheck(
            text=text, provision_id=pid, exists=record is not None, edition_ok=edition_ok, page_ok=page_ok,
            canonical_citation=record['citation'] if record else None,
            pdf_page=record.get('pdf_page') if record else None, issues=issues, pointer=pointer))
    return out


def table_pairs(pid: str, codes) -> tuple[list[tuple[str, str]], str | None]:
    """(function, objective) pairs the Division B table attributes to `pid`, and the canonical citation."""
    from ..section_c import section_c_rows
    rows = section_c_rows([pid], codes)
    pairs = [(pair.function, pair.objective) for row in rows for pair in row.pairs]
    return list(dict.fromkeys(pairs)), rows[0].citation if rows else None


def _codes(text: str) -> set[str]:
    return set(CODE_TOKEN.findall(text or ''))


def compare_row(row: int, article: str, objective: str, function: str, pointer: Pointer, codes) -> SectionCCheck:
    ids = provision_ids(article)
    base = dict(row=row, form_objective=objective or None, form_function=function or None, pointer=pointer)
    if not ids:
        return SectionCCheck(provision_id=None, status='not_checked',
                             message='No provision number was read in this row, so it was not compared.', **base)
    pid = ids[0]
    if codes is None:
        return SectionCCheck(provision_id=pid, status='not_checked',
                             message='The code database is not available; the row was not compared.', **base)
    if _lookup(codes, pid) is None:
        return SectionCCheck(provision_id=pid, status='provision_not_found',
                             message=f'{pid} was not found in NBC(AE) 2023, 2nd printing, so the row could not be '
                                     'compared with the attribution table.', **base)
    try:
        pairs, _citation = table_pairs(pid, codes)
    except (KeyError, ValueError):
        return SectionCCheck(provision_id=pid, status='not_checked',
                             message='The attribution table could not be read for this provision.', **base)
    shown = [f'{func}-{obj}' for func, obj in pairs]
    if _APPENDIX.search(f'{objective} {function}') and not (_codes(objective) or _codes(function)):
        return SectionCCheck(provision_id=pid, table_pairs=shown, status='not_checked',
                             message='The objective and function continue in an appendix; compare them there.', **base)
    form_objectives, form_functions = _codes(objective), _codes(function)
    if not pairs:
        if form_objectives or form_functions:
            return SectionCCheck(provision_id=pid, table_pairs=[], status='mismatch',
                                 message=f'The form gives objective "{objective}" and function "{function}" for '
                                         f'{pid}, but the Division B attribution table has no row for this provision.',
                                 **base)
        return SectionCCheck(provision_id=pid, table_pairs=[], status='no_table_row',
                             message=f'The Division B attribution table has no row for {pid}; the form does not '
                                     'give a pair either.', **base)
    table_objectives = {obj for _f, obj in pairs}
    table_functions = {func for func, _o in pairs}
    if not form_objectives and not form_functions:
        if _NO_ROW.search(f'{objective} {function}'):
            message = (f'The form says there is no table row, but the Division B table attributes '
                       f'{", ".join(shown)} to {pid}.')
        else:
            message = (f'No objective or function code was read in this row. The Division B table attributes '
                       f'{", ".join(shown)} to {pid}.')
        return SectionCCheck(provision_id=pid, table_pairs=shown, status='mismatch', message=message, **base)
    wrong_obj = sorted(form_objectives - table_objectives)
    wrong_fn = sorted(form_functions - table_functions)
    if wrong_obj or wrong_fn or not form_objectives or not form_functions:
        return SectionCCheck(
            provision_id=pid, table_pairs=shown, status='mismatch',
            message=(f'The form gives objective "{objective or "(blank)"}" and function "{function or "(blank)"}" '
                     f'for {pid}; the Division B attribution table gives {", ".join(shown)}.'), **base)
    return SectionCCheck(provision_id=pid, table_pairs=shown, status='match',
                         message=f'The form\'s objective and function match the Division B table for {pid}.', **base)


def _same_provision(a: str, b: str) -> bool:
    """Equal ids, or one is the article or sentence containing the other: 3.2.1.1. holds 3.2.1.1.(2), not 3.2.1.10."""
    a, b = a.rstrip('.'), b.rstrip('.')
    short, long_ = sorted((a, b), key=len)
    return a == b or long_.startswith(short + '.(') or long_.startswith(short + '(')
