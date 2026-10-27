"""Verify cited provisions and compare Section C rows with the Division B attribution tables.

Every check is a database lookup. Nothing here says a provision applies or that
a design meets it; mismatches name both values and ask the applicant.
"""
from __future__ import annotations

import re

from ..models_review import CitationCheck, CitationIssue, Pointer, SectionCCheck

PROVISION = re.compile(r'(?<![\w.])\d{1,2}(?:\.\d{1,3}){3}\.?(?:\s*\(\d{1,2}\))?(?:\s*\([a-z]+\))*')
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


def _lookup(codes, pid: str, division='B'):
    return codes.provision(pid, division)


def verify_citation(text: str, pointer: Pointer, codes) -> list[CitationCheck]:
    """Resolve each occurrence in its own written division/edition/page context."""
    matches = list(PROVISION.finditer(text or ''))
    out = []
    division_pattern = re.compile(r'\bDiv(?:ision)?\.?\s*([ABC])\b', re.I)
    family = re.compile(r'\b(?:NBC\s*\(AE\)|ABC|Alberta Building Code|National Building Code)'
                        r'[^\n]{0,15}?(?:2023|2020|2019|2014)\b', re.I)
    for index, match in enumerate(matches):
        pid = provision_ids(match.group(0))[0]
        divisions = list(division_pattern.finditer(text[:match.start()]))
        division = divisions[-1].group(1).upper() if divisions else None
        if divisions:
            bridge = text[divisions[-1].end():match.start()]
            bridge = re.sub(r'\b(?:Sentence|Article|Clause|Subclause|Table)\b', '', bridge, flags=re.I)
            if not re.fullmatch(r'[\s,:;.()\d-]*', bridge):
                division = None
        # "Note A-x" names an explanatory note (the former Appendix A) in any division, not Division A.
        note = re.search(r'\bNote\s+A-$', text[:match.start()], re.I) is not None
        families = list(family.finditer(text[:match.start()]))
        start = families[-1].start() if families else max(0, text.rfind('\n', 0, match.start()) + 1)
        # Keep only this occurrence's trailing pinpoint, never the next citation's page.
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        context = text[start:min(end, match.end() + 180)]
        if division and not division_pattern.search(context[:context.find(match.group(0))]):
            context = f'Division {division} ' + context
        if codes is None:
            out.append(CitationCheck(text=context, provision_id=pid, pointer=pointer,
                issues=[CitationIssue(code='lookup_skipped', message='The code database is not available; not verified.')]))
            continue
        try:
            if note and division is None:
                record = next(filter(None, (_lookup(codes, pid, d) for d in 'ABC')), None)
            else:
                record = _lookup(codes, pid, division)
        except Exception:
            out.append(CitationCheck(text=context, provision_id=pid, pointer=pointer,
                issues=[CitationIssue(code='source_unresolved',
                    message=f'The source for {pid} could not be resolved; check its division and code database.')]))
            continue
        issues = []
        try:
            from codedb.validator import validate_text
            edition = families[-1].group(0) if families else 'NBC(AE) 2023'
            resolved_division = division or (record.get('division') if record else None)
            validation = edition + (f' Division {resolved_division} ' if resolved_division else ' ') + text[match.start():min(end, match.end() + 180)]
            report = validate_text(validation, db_path=codes.db_path)
        except Exception:
            report = None
        if report:
            for error in report['errors'] + report['warnings']:
                cited = re.sub(r'\s+', '', error.get('citation') or '')
                if (cited and _same_provision(cited, pid)) or (not cited and error['code'] == 'superseded_edition'):
                    issues.append(CitationIssue(code=error['code'], message=error['message']))
        codes_seen = {issue.code for issue in issues}
        if record is None and 'nonexistent_provision' not in codes_seen:
            issues.append(CitationIssue(code='nonexistent_provision',
                message=f'{pid} was not found in NBC(AE) 2023, 2nd printing'
                        + (f', Division {division}.' if division else '.')))
        out.append(CitationCheck(text=context, provision_id=pid, exists=record is not None,
            edition_ok='superseded_edition' not in codes_seen,
            page_ok=('page_mismatch' not in codes_seen) if record and _PAGE.search(context) else None,
            canonical_citation=re.sub(r'\bDiv ([ABC])\b', r'Division \1', record['citation']) if record else None,
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
    try:
        record = _lookup(codes, pid)
    except Exception:  # noqa: BLE001 - do not turn a failed source lookup into false nonexistence
        return SectionCCheck(provision_id=pid, status='not_checked',
                             message='The provision source could not be resolved.', **base)
    if record is None:
        return SectionCCheck(provision_id=pid, status='provision_not_found',
                             message=f'{pid} was not found in NBC(AE) 2023, 2nd printing, so the row could not be '
                                     'compared with the attribution table.', **base)
    try:
        pairs, _citation = table_pairs(pid, codes)
        from ..section_c import section_c_rows
        canonical = section_c_rows([pid], codes)
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
    if form_objectives != table_objectives or form_functions != table_functions:
        return SectionCCheck(
            provision_id=pid, table_pairs=shown, status='mismatch',
            message=(f'The form gives objective "{objective or "(blank)"}" and function "{function or "(blank)"}" '
                     f'for {pid}; the Division B attribution table gives {", ".join(shown)}.'), **base)
    # Separate objective and function columns lose pair relationships when both vary.
    # Do not claim an exact match from a matching set of independent column values.
    if ((len(table_objectives) > 1 and len(table_functions) > 1)
            or len(canonical) != 1 or any(pair.clauses or pair.application_note for current in canonical for pair in current.pairs)):
        return SectionCCheck(provision_id=pid, table_pairs=shown, status='not_checked',
                             message='The columns name all codes, but exact pair relationships and conditions need comparison with the table.', **base)
    return SectionCCheck(provision_id=pid, table_pairs=shown, status='match',
                         message=f'The form\'s objective and function match the Division B table for {pid}.', **base)


def complete_visible_attribution(read, row_number, pid, codes) -> bool:
    """Exact complete table witness from visible appendix text, including every pair and condition."""
    if codes is None:
        return False
    from ..section_c import section_c_rows
    from ..export.appendix import _nrc
    from ..export.text import faithful_font_text
    try:
        rows = section_c_rows([pid], codes)
        if len(rows) != 1:
            return False
        canonical = rows[0]
        expected = ['Function Objective Source']
        for pair in canonical.pairs:
            for code, prose in ((pair.function, pair.function_text), (pair.objective, pair.objective_text)):
                definition = codes.definition(code)
                expected.append(f'{code} {_nrc(prose, (definition or {}).get("citation") or canonical.citation)}'.strip())
            expected.append(f'NBC(AE) 2023 Div B {pair.table}, PDF p. {pair.pdf_page}'
                + (f'; clauses {", ".join(pair.clauses)}' if pair.clauses else '')
                + (f'; {_nrc(pair.application_note, canonical.citation)}' if pair.application_note else ''))
        compact = lambda value: re.sub(r'\s+', '', faithful_font_text(value))
        expected_text = compact(' '.join(expected))
        unsafe = set(read.unreadable_pages())
        text = '\n'.join(page.text if page.page not in unsafe else '\nUNREADABLE\n' for page in read.text_pages)
        start_pattern = re.compile(rf'(?m)^C-{row_number}\s+{re.escape(pid)}\s*\nCitation:')
        for start in start_pattern.finditer(text):
            end = text.find('Provision text:', start.end())
            status = text.find('Attribution status:', start.end(), end if end >= 0 else len(text))
            table = text.find('Function Objective Source', status, end) if end >= 0 and status >= 0 else -1
            if table < 0:
                continue
            body = text[table:end]
            # Running continuation headers are layout, never table data.
            body = re.sub(r'Batatis appendix to SCC variance form - case [^\n]+\n', '', body)
            body = re.sub(r'Appendix page \d+\s*', '', body)
            first_header = body.find('Function Objective Source')
            body = body[:first_header + len('Function Objective Source')] + body[first_header + len('Function Objective Source'):].replace('Function Objective Source', '')
            if compact(body) == expected_text:
                return True
    except (KeyError, ValueError, OSError):
        pass
    return False


def _same_provision(a: str, b: str) -> bool:
    """Equal ids, or one is the article or sentence containing the other: 3.2.1.1. holds 3.2.1.1.(2), not 3.2.1.10."""
    a, b = a.rstrip('.'), b.rstrip('.')
    short, long_ = sorted((a, b), key=len)
    return a == b or long_.startswith(short + '.(') or long_.startswith(short + '(')
