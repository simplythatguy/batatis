"""Conservative text citation scanner with document/division and source-page context.

Markdown, JSON and YAML are scanned as text (no execution or YAML dependencies).
Every error has a stable code and location. A clean report proves only the citations
recognized here, never that a technical claim or an application is correct.
"""
from __future__ import annotations

import json
import re
from contextlib import closing
from pathlib import Path

from . import ids, store
from .api import AmbiguousProvisionError, attribution_rows, record, resolve
from .attributions import parse_bracket
from .sources import DOCS, NATIONAL_CONTEXT_RE, SUPERSEDED_PATTERNS, load_pages

_CITATION = re.compile(
    r'(?<![\w.])(?P<note>A-)?(?P<id>\d{1,2}(?:\.\d{1,3}){3,6}\.?(?:\s*\(\d{1,2}\)'
    r'(?:\s*\([a-z]{1,2}\))?(?:\s*\([ivx]+\))?)?)(?![\w.]|\s*\(\d)')
_SHORT = re.compile(r'\b(?:Section|Subsection)\s+(?P<id>\d{1,2}(?:\.\d{1,3}){1,2}\.?)(?![\w.])', re.I)
_PAIR = re.compile(r'\[\s*F\d+[^\]\n]*-\s*O[^\]\n]*\]')
_PAGE = re.compile(r'\bPDF\s+p{1,2}\.?\s*(\d+)(?:\s*[-–]\s*(\d+))?', re.I)
_DIV = re.compile(r'\bDiv(?:ision)?\.?[\s"\':=]+([ABC])\b', re.I)
_FAMILY = re.compile(r'\b(NBC|NFC)(?:\s*[-(]\s*AE\)?)?|National\s+(Building|Fire)\s+Code', re.I)
_INTENT = re.compile(r'\bIntent\s+Statements?\b', re.I)
_EXPLANATORY = re.compile(r'\b(?:explanatory|historical|history|superseded|not\s+(?:Alberta\s+)?law|'
                          r'not\s+(?:the\s+)?(?:adopted|governing)|context\s+only|do\s+not\s+cite|never\s+cite)\b', re.I)
_EXTENSIONS = {'.md', '.markdown', '.json', '.jsonl', '.yaml', '.yml'}


def _report():
    return {'ok': True, 'files_checked': 0, 'citations_checked': 0, 'errors': [], 'warnings': []}


def _issue(report, path, text, offset, code, citation, message, warning=False):
    line = text.count('\n', 0, offset) + 1
    col = offset - text.rfind('\n', 0, offset)
    report['warnings' if warning else 'errors'].append(
        {'path': str(path), 'line': line, 'column': col, 'code': code, 'citation': citation, 'message': message})


def _scope(context, default_doc):
    found = list(_FAMILY.finditer(context))
    family = None
    if found:
        m = found[-1]
        family = (m.group(1) or ('NBC' if m.group(2).lower() == 'building' else 'NFC')).upper()
    doc = family + '-AE' if family else default_doc
    # An earlier intent citation must not turn a later Alberta-law citation into
    # an intent lookup. Source kind belongs to the most recent document mention.
    tail = context[found[-1].end():] if found else context
    return doc, bool(_INTENT.search(tail))


def _pairs(rows):
    return {(f, o) for r in rows for f in r['fs'] for o in r['objectives']}


def _page_count(con, doc):
    metadata = con.execute("SELECT value FROM meta WHERE key='stats'").fetchone()
    sources = json.loads(metadata[0]).get('sources',{}) if metadata else {}
    if sources.get(doc,{}).get('pdf_pages'):
        return sources[doc]['pdf_pages']
    # Compatibility with earlier local builds. New builds can validate using
    # SQLite alone, without retaining all extracted source page files.
    return len(load_pages(doc))


_NFC_TEXT = {}


def _nfc_article_pages(pid, doc):
    """PDF pages of the NFC(AE) 2023 text where the article of `pid` appears. Used only for documents the database
    does not build: it proves the article is printed on those pages, not that the sentence text matches."""
    if doc != 'NFC-AE':
        return []
    article = pid.split('(')[0].rstrip('.')
    if 'pages' not in _NFC_TEXT:
        _NFC_TEXT['pages'] = list(load_pages(doc))
        _NFC_TEXT['found'] = {}
    if article not in _NFC_TEXT['found']:
        pattern = re.compile(r'(?<![\d.])' + re.escape(article) + r'\.(?!\d)')
        _NFC_TEXT['found'][article] = [p.page for p in _NFC_TEXT['pages'] if pattern.search(p.raw)]
    return _NFC_TEXT['found'][article]


def _scan(text, path, con, report, default_doc):
    # Paragraphs allow a citation followed by its attribution on the next line, but
    # reset at headings/list rows so an unrelated paragraph cannot supply a target.
    previous = []
    paragraph_scope = ''
    paragraph_division = None
    offset = 0
    for line in text.splitlines(keepends=True):
        if not line.strip() or re.match(r'^\s*#{1,6}\s', line):
            previous = []
            paragraph_scope = ''
            paragraph_division = None
        elif line.lstrip().startswith('|'):
            # A table row stands alone: an earlier row's document or intent mention must not leak into it.
            previous = []
            paragraph_scope = ''
        scope = paragraph_scope + ' ' + line
        doc, intent = _scope(scope, default_doc)
        prior_scope = paragraph_scope  # context from earlier lines only, never this line's later text
        if _FAMILY.search(line):
            paragraph_scope = line
        for pattern, reason in SUPERSEDED_PATTERNS:
            for m in re.finditer(pattern, line, re.I):
                if not _EXPLANATORY.search(line):
                    _issue(report, path, text, offset+m.start(), 'superseded_edition', m.group(),
                           f'{reason}; cite NBC(AE)/NFC(AE) 2023 p2, or label historical context explicitly')
        for m in re.finditer(NATIONAL_CONTEXT_RE, line, re.I):
            if not (_INTENT.search(line) or _EXPLANATORY.search(line)):
                _issue(report, path, text, offset+m.start(), 'national_edition_as_law', m.group(),
                       'National 2020/2025 editions are explanatory only; label that context or cite Alberta 2023 p2')
        candidates = []
        matches = sorted(list(_CITATION.finditer(line)) + list(_SHORT.finditer(line)), key=lambda m:m.start())
        for i, m in enumerate(matches):
            before = line[:m.start()]
            if re.search(r'(?:\bv\s*|\b(?:version|ver|release)[\s"\':=]+|https?://[^\s]*|\d\.)$', before, re.I):
                continue
            # A table number resolves to the table registry, rather than a body article.
            table = bool(re.search(r'\bTable\s*$', before, re.I))
            note = bool(m.groupdict().get('note'))
            raw = re.sub(r'\s+', '', m.group('id'))
            report['citations_checked'] += 1
            try:
                pid = ids.canon(raw)
            except ValueError as exc:
                _issue(report,path,text,offset+m.start(),'malformed_provision',m.group(),str(exc))
                continue
            # Prefer the closest division before this id, or an explicit "of Division X" after it.
            divs = list(_DIV.finditer(before))
            after = line[m.end():matches[i+1].start() if i+1<len(matches) else len(line)]
            post_div = re.search(r'\bof\s+Division\s+([ABC])\b', after, re.I)
            scope_divs = list(_DIV.finditer(paragraph_scope))
            div = post_div.group(1).upper() if post_div else (
                divs[-1].group(1).upper() if divs else (scope_divs[-1].group(1).upper() if scope_divs else paragraph_division))
            local_doc, local_intent = _scope(before, doc)
            # Source kind follows the latest mention before this citation, not later text on the same line.
            _, before_intent = _scope(prior_scope + ' ' + before, doc)
            # Citations labelled as another edition or jurisdiction (2019, BC, or the video's own numbers) are historical:
            # they are reported as warnings, never as nonexistent 2023 ids.
            historical = (bool(re.search(r'\b2019\b', before[-32:])) or bool(
                re.match(r'\W{0,3}(?:\(2019\)|in 2019|2019 (?:text|sentence|numbering|version|edition))', line[m.end():], re.I))
                or bool(re.search(r'\b(?:BC|British Columbia)\s+(?:(?:sentence|article|clause)\s+)?$', before, re.I))
                or bool(re.search(r"\b2019\s*\((?:historical|the video's edition)\)|the video's (?:numbers|numbering)", line, re.I)))
            target = {'start':m.start(), 'end':m.end(), 'id':pid, 'doc':local_doc,
                      'division':div, 'row':None, 'attrs':[], 'intent':local_intent if _FAMILY.search(before) else before_intent,
                      'pages':[], 'invalid':False}
            has_doc = con.execute('SELECT 1 FROM provisions WHERE doc=? LIMIT 1', (local_doc,)).fetchone()
            if not has_doc:
                pages = [] if (table or note) else _nfc_article_pages(pid, local_doc)
                if pages:
                    target['pages'] = [(p, p) for p in pages]
                    _issue(report,path,text,offset+m.start(),'nfc_text_only',m.group(),
                           f'{local_doc} is not built; the article is printed on PDF p.{", ".join(map(str, pages))}. '
                           'The sentence wording is not checked against the database', True)
                else:
                    _issue(report,path,text,offset+m.start(),'unsupported_document',m.group(),
                           f'{local_doc} is not built; no citation check can be certified for this document')
                    target['invalid'] = True
            elif target['intent']:
                source = 'NBC-2020-IS' if local_doc == 'NBC-AE' else 'NFC-2020-IS'
                rows = [record(r) for r in con.execute('SELECT * FROM intents WHERE source=? AND provision_id=?', (source,pid))]
                target['pages'] = [(r['pdf_page'],r['pdf_page_end']) for r in rows]
                target['attrs'] = [{'fs':b.fs,'objectives':b.objectives,'pdf_page':r['pdf_page']} for r in rows
                                   for raw_b in r['brackets'] if (b:=parse_bracket(raw_b))]
                if not rows:
                    _issue(report,path,text,offset+m.start(),'nonexistent_intent',m.group(),
                           f'No {source} entry for {pid}; use lookup to find a supported entry')
                    target['invalid'] = True
            elif note or table:
                # Lettered tables keep their letter after the id: Table 9.23.3.5.-A.
                letter = re.match(r'-([A-Z])(?!\w)', line[m.end():]) if table else None
                if note:
                    rows = con.execute('SELECT * FROM notes WHERE doc=? AND note_id=?'+
                                       (' AND division=?' if div else ''),
                                       (local_doc,'A-'+pid,div) if div else (local_doc,'A-'+pid)).fetchall()
                else:
                    table_id = 'Table '+pid+(f'-{letter.group(1)}' if letter else '')
                    rows = con.execute('SELECT *,pdf_page AS pdf_page_end FROM code_tables WHERE doc=? AND table_id=?'+
                                       (' AND division=?' if div else ''),
                                       (local_doc,table_id,div) if div else (local_doc,table_id)).fetchall()
                if not rows:
                    shown = m.group()+(letter.group(0) if letter and not note else '')
                    if historical and not note:
                        _issue(report,path,text,offset+m.start(),'historical_number',shown,
                               f'{shown} is labelled as another edition or jurisdiction; no NBC(AE) 2023 table is checked under this number', True)
                    else:
                        _issue(report,path,text,offset+m.start(),'nonexistent_note' if note else 'nonexistent_table',shown,
                               f'No {"note" if note else "table"} {shown} in {local_doc}'+(f' Div {div}' if div else ''))
                    target['invalid'] = True
                target['pages'] = [(r['pdf_page'],r['pdf_page_end']) for r in rows]
                if table and rows:
                    end = con.execute('SELECT MAX(pdf_page) FROM attributions WHERE doc=? AND table_id=?',
                                      (local_doc,'Table '+pid)).fetchone()[0]
                    if end is not None:
                        target['pages'] = [(r['pdf_page'],max(r['pdf_page_end'],end)) for r in rows]
            else:
                try:
                    row = resolve(con,pid,local_doc,div)
                except AmbiguousProvisionError as exc:
                    _issue(report,path,text,offset+m.start(),'ambiguous_division',m.group(),str(exc))
                    target['invalid'] = True
                    row = None
                if row:
                    target['row'] = row
                    target['division'] = row['division']
                    end = row['pdf_page_end']
                    if row['level'] in ('article','subsection','section'):
                        end = con.execute('SELECT MAX(pdf_page_end) FROM provisions WHERE doc=? AND division=? AND '
                                          '(id=? OR id LIKE ?)',(local_doc,row['division'],pid,pid+'%')).fetchone()[0]
                    target['pages'] = [(row['pdf_page'],end)]
                    target['attrs'] = attribution_rows(con,row)
                elif not target['invalid']:
                    if historical:
                        _issue(report,path,text,offset+m.start(),'historical_number',m.group(),
                               f'{pid} is labelled as another edition or jurisdiction; no NBC(AE) 2023 provision is checked under this number. '
                               'Record the 2023 equivalent or mark it not-found', True)
                    else:
                        _issue(report,path,text,offset+m.start(),'nonexistent_provision',m.group(),
                               f'{pid} does not exist in {local_doc}'+(f' Div {div}' if div else '')+
                               '; check the id, division and edition with codedb lookup')
                    target['invalid'] = True
            candidates.append(target)
        active = candidates or previous
        pair_events = []
        for m in _PAIR.finditer(line):
            report['citations_checked'] += 1
            bracket = parse_bracket(m.group())
            eligible = [t for t in candidates if t['start'] < m.start()] or active
            targets = [eligible[-1]] if eligible else []
            if bracket is None:
                _issue(report,path,text,offset+m.start(),'malformed_attribution',m.group(),
                       'Expected [Fxx-Oxx] or grouped codes such as [F10,F12-OS1.5]')
                continue
            if targets and any(t['invalid'] for t in targets):
                continue  # report the bad target once, without cascading pair/page failures
            rows = [r for t in targets for r in t['attrs']]
            wanted = set(bracket.pairs)
            if not targets:
                rows = [record(r) for r in con.execute('SELECT * FROM attributions WHERE doc=?',(doc,))]
            allowed = _pairs(rows)
            if wanted - allowed:
                missing = ', '.join(f'[{f}-{o}]' for f,o in sorted(wanted-allowed))
                context = ', '.join(t['id'] for t in targets) or doc+' attribution tables'
                _issue(report,path,text,offset+m.start(),'attribution_not_in_table',m.group(),
                       f'{missing} is not attributed to {context}; inspect lookup attributions and their application notes')
            elif not targets:
                _issue(report,path,text,offset+m.start(),'unbound_attribution',m.group(),
                       'Pair exists in the table, but no provision is linked in this paragraph; add its provision id',True)
            pairs_by_page = {}
            for row in rows:
                pairs_by_page.setdefault(row['pdf_page'],set()).update(_pairs([row]))
            pair_events.append((m.end(), [p for p,pairs in pairs_by_page.items() if wanted <= pairs],targets))
        for m in _PAGE.finditer(line):
            report['citations_checked'] += 1
            start,end = int(m.group(1)),int(m.group(2) or m.group(1))
            eligible = [t for t in candidates if t['start'] < m.start()] or active
            target = eligible[-1] if eligible else None
            pair = next((event for event in reversed(pair_events) if event[0] < m.start() and
                         (not candidates or not target or event[0] > target['end'])),None)
            ranges = [(p,p) for p in pair[1]] if pair else (target['pages'] if target else [])
            page_doc = target['doc'] if target else doc
            is_intent = target['intent'] if target else intent
            if is_intent:
                page_doc = 'NBC-2020-IS' if page_doc=='NBC-AE' else 'NFC-2020-IS'
            if target and target['invalid']:
                continue
            page_count = _page_count(con,page_doc)
            if end < start or start < 1 or end > page_count:
                _issue(report,path,text,offset+m.start(),'invalid_page',m.group(),
                       f'PDF page range must be within 1–{page_count} for {page_doc}')
            elif ranges and not all(any(a-1<=p<=b+1 for a,b in ranges) for p in range(start,end+1)):
                kind = 'attribution table' if pair else ('intent' if is_intent else 'provision')
                expected = ', '.join(str(a) if a==b else f'{a}–{b}' for a,b in sorted(set(ranges)))
                _issue(report,path,text,offset+m.start(),'page_mismatch',m.group(),
                       f'{kind} source is PDF p.{expected} (±1 allowed); cited p.{start}'+(f'–{end}' if end!=start else ''))
            elif not ranges:
                _issue(report,path,text,offset+m.start(),'unbound_page',m.group(),
                       'Page is in range, but no provision or attribution is linked; add a source citation',True)
        if candidates:
            previous = candidates
        divisions = list(_DIV.finditer(line))
        if divisions:
            paragraph_division = divisions[-1].group(1).upper()
        offset += len(line)


def validate_text(text: str, *, path='<text>', doc='NBC-AE', db_path=None):
    """Check citation text and return a JSON-serializable report; warnings do not fail."""
    if doc not in DOCS or DOCS[doc].kind != 'code':
        raise ValueError('doc must name a registered Alberta code')
    report = _report()
    with closing(store.connect(db_path)) as con:
        _scan(text,path,con,report,doc)
    report['files_checked'] = 1
    report['ok'] = not report['errors']
    return report


def validate(paths, *, doc='NBC-AE', db_path=None):
    """Validate a path or iterable of paths. Directories recurse over Markdown/JSON/YAML.

    Missing/unreadable/unsupported files are errors, never silent successful checks.
    """
    if doc not in DOCS or DOCS[doc].kind != 'code':
        raise ValueError('doc must name a registered Alberta code')
    if isinstance(paths,(str,Path)):
        paths = [paths]
    report = _report()
    selected = set()
    for item in paths:
        p = Path(item)
        if p.is_dir():
            selected.update(f for f in p.rglob('*') if f.is_file() and f.suffix.lower() in _EXTENSIONS)
        else:
            selected.add(p)
    with closing(store.connect(db_path)) as con:
        for p in sorted(selected):
            if p.suffix.lower() not in _EXTENSIONS:
                _issue(report,p,'',0,'unsupported_file',str(p),'Use Markdown, JSON, JSONL or YAML input')
                continue
            try:
                text = p.read_text(encoding='utf8')
            except (OSError,UnicodeError) as exc:
                _issue(report,p,'',0,'unreadable_file',str(p),str(exc))
                continue
            _scan(text,p,con,report,doc)
            report['files_checked'] += 1
    if not selected:
        _issue(report,'<input>','',0,'no_files','', 'No supported files found; provide Markdown/JSON/YAML paths')
    report['ok'] = not report['errors']
    return report
