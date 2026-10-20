"""Map a cited appeal article toward NBC(AE) 2023, or leave it unmapped.

A pre-2023 number is never written through as a 2023 citation. The same identifier
in the code database is not enough: promotion needs a title or sentence comparison
against the edition the decision actually cited, and this set does not carry that text.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

_TOKEN = re.compile(
    r'\d{1,2}(?:\.\d{1,3}){1,3}\.?'
    r'(?:\(\d{1,2}\))?(?:\([a-z]{1,2}\))?'
    r'(?:\((?:i|ii|iii|iv|v|vi|vii|viii|ix|x|xi|xii)\))?'
)
_OBJECTIVE = re.compile(r'\b(?:OS|OP|OH|OA|OE)\d|\bF\d{2}\b')
_CLAUSE_LIST = re.compile(r'\([a-z]\)\s*,')
_PRE2023 = 'pre-2023 citation'


def edition_bucket(code_edition: str) -> str:
    """Collapse the researcher's edition string to the four buckets in the brief."""
    text = code_edition or ''
    low = text.lower()
    if 'uncertain' in low or 'not stated' in low or 'does not name' in low:
        return 'unspecified'
    if '2019' in low and 'nbc' in low:
        return 'NBC(AE) 2019'
    if '2014' in low and 'abc' in low and '2006' not in low:
        return 'ABC 2014'
    if '2006' in low:
        return 'ABC 2006'
    return 'unspecified'


def _division(text: str) -> str | None:
    """Extract an explicit Division A, B or C label, leaving unstated divisions unresolved."""
    match = re.search(r'Division\s+([ABC])\b', text or '')
    return match.group(1) if match else None


def _parse_id(raw: str) -> str | None:
    """Parse and canonicalize a source provision token without inventing an identifier."""
    match = _TOKEN.search(raw or '')
    if not match:
        return None
    token = match.group(0)
    try:
        from codedb.ids import canon
        return canon(token)
    except (ImportError, ValueError):
        return None


def _row(raw: str, code: str, division: str | None, part: str, **fields) -> dict:
    """Construct an unmapped source-citation record with its reason and provenance."""
    return {
        'source_article': raw,
        'source_code': code,
        'source_division': division,
        'source_part': part,
        'parsed_id': fields.get('parsed_id'),
        'nbc_ae_2023': None,
        'method': None,
        'confidence': None,
        'unmapped_reason': fields['unmapped_reason'],
    }


def classify_article(article: dict, edition: str) -> dict:
    """One source article. ``nbc_ae_2023`` stays null until a comparison earns it."""
    raw = (article.get('article') or '').strip()
    code = article.get('code') or ''
    division_text = article.get('division') or ''
    part = article.get('part') or ''
    division = _division(division_text)
    low = raw.lower()
    building = bool(re.search(r'\b(?:ABC|NBC)\b', code))
    fire_only = bool(re.search(r'\b(?:AFC|NFC|NFPA)\b', code)) and not building

    if fire_only or (not building and re.search(r'\b(?:AFC|NFC)\b', raw)):
        return _row(raw, code, division, part,
                    unmapped_reason='Fire-code or other-standard citation, not an NBC(AE) article.')
    if edition == 'unspecified':
        return _row(raw, code, division, part,
                    unmapped_reason='The decision does not name the code edition.')
    if 'typo' in division_text.lower():
        return _row(raw, code, division, part,
                    unmapped_reason='The decision text may mis-number this article. It was left unmapped rather than corrected by guess.')
    if low.startswith('a-') or 'appendix' in low or '(note)' in low or low.startswith('note'):
        return _row(raw, code, division, part,
                    unmapped_reason='Appendix note. A note id is not recorded as an NBC(AE) 2023 article citation.')
    if 'table' in low:
        return _row(raw, code, division, part,
                    unmapped_reason='Table citation. Not mapped without a verified NBC(AE) 2023 table id.')
    if raw.startswith(('Part ', 'Subsection', 'Section ')):
        return _row(raw, code, division, part, unmapped_reason='Not an article identifier.')
    if 'definition' in low:
        return _row(raw, code, division, part, parsed_id=_parse_id(raw),
                    unmapped_reason='Definition citation. Not mapped as an article gold label.')
    if _OBJECTIVE.search(raw):
        return _row(raw, code, division, part,
                    unmapped_reason='Objective or functional-statement label, not a Division B article to carry forward as gold.')
    if raw.startswith('10.') or part.strip().startswith('Part 10'):
        return _row(raw, code, division, part, parsed_id=_parse_id(raw),
                    unmapped_reason='ABC 2006 Part 10 is Alberta-specific and is not treated as an NBC(AE) 2023 article.')
    if '/' in raw or _CLAUSE_LIST.search(raw):
        return _row(raw, code, division, part,
                    unmapped_reason='Combined citation or clause list. Components were not split into 2023 articles.')
    parsed = _parse_id(raw)
    if parsed is None:
        return _row(raw, code, division, part,
                    unmapped_reason='Identifier could not be parsed as a provision id, so it was not reconstructed.')
    return _row(
        raw, code, division, part, parsed_id=parsed,
        unmapped_reason=(
            f'{_PRE2023}; codedb was not available to compare titles or sentence text, '
            'so this number is not an NBC(AE) 2023 citation.'
        ),
    )


def attempt_mapping(entry: dict, db_path: Path | None) -> dict:
    """Lookup hook. Same-identifier hits stay unmapped when source text is absent."""
    out = dict(entry)
    if out.get('nbc_ae_2023') or db_path is None:
        return out
    parsed = out.get('parsed_id')
    division = out.get('source_division')
    if not parsed or division not in {'A', 'B', 'C'}:
        return out
    if not str(out.get('unmapped_reason') or '').startswith(_PRE2023):
        return out
    con = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    try:
        found = con.execute(
            "SELECT 1 FROM provisions WHERE doc='NBC-AE' AND division=? AND id=?",
            (division, parsed),
        ).fetchone()
    finally:
        con.close()
    out['nbc_ae_2023'] = None
    if found is None:
        out['method'] = 'codedb_lookup'
        out['confidence'] = 'none'
        out['unmapped_reason'] = 'Identifier is not in the NBC(AE) 2023 database.'
        return out
    out['method'] = 'same_identifier_in_codedb'
    out['confidence'] = 'insufficient'
    out['unmapped_reason'] = (
        'The same identifier is present in the NBC(AE) 2023 database, but no source-edition '
        'title or sentence text was available to compare, so it is not recorded as a 2023 citation.'
    )
    return out
