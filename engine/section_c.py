"""Section C by deterministic lookup: objective/function rows from the NBC(AE) attribution tables.

No model calls. One row per Division B sentence (an article expands to its sentences; a clause stays a
clause). Pairs come only from codedb ``attribution_status``:
  direct        - this provision's own attributions rows
  inherits      - the rows of ``root_provision``. ``attributed_via`` is that id
  clause_level  - no pairs on the sentence. Clause rows with status direct are listed beside it,
                  and the sentence label is ``attributed at clause level: (a)…``
  none          - no pairs and no ``attributed_via``. ``attribution`` is ``not_attributed`` and the
                  user-facing label is ``lookup not available``
A cited provision is always a row. The intent statement stays when the database has one.
National 2020 intent statements are explanatory only. They attach to Division B rows, and a comparison
status of provision_missing_in_ae is not attached.
"""
from __future__ import annotations

from codedb import ids

from .codes import Codes
from .models import AttributionPair, IntentBlock, SectionCRow

NOT_ATTRIBUTED = 'not_attributed'
NOT_ATTRIBUTED_LABEL = 'lookup not available'

def section_c_rows(provision_ids: list[str], codes: Codes) -> list[SectionCRow]:
    """Rows for Division B provisions, in input order. Raises KeyError for an id not in Division B."""
    rows: list[SectionCRow] = []
    for pid in provision_ids:
        rec = codes.provision(pid, 'B')
        if rec is None:
            raise KeyError(f'{pid} is not a Division B provision')
        if rec['level'] in ('article', 'subsection', 'section'):
            targets = [c for c in rec['children'] if c['level'] == 'sentence'] if rec['level'] == 'article' else []
            if not targets:
                raise KeyError(f'{pid}: pass an article, sentence or clause')
            for child in targets:
                rows.extend(_rows_for(codes.provision(child['id'], 'B'), codes))
        else:
            rows.extend(_rows_for(rec, codes))
    return rows


def _text(codes: Codes, code: str) -> str | None:
    d = codes.definition(code)
    return d['title'] if d else None


def _pairs(rows, codes: Codes) -> list[AttributionPair]:
    return [AttributionPair(function=f, function_text=_text(codes, f), objective=o,
                            objective_text=_text(codes, o), bracket=a['bracket'], clauses=a['clauses'] or [],
                            application_note=a['application_note'], table=a['table_id'], pdf_page=a['pdf_page'])
            for a in rows for f in a['fs'] for o in a['objectives']]


def _exact_rows(attributions, provision_id: str):
    """Rows stored for this id. A row with no id belongs to the provision being read."""
    return [a for a in attributions or [] if a.get('provision_id', provision_id) == provision_id]


def _status(rec: dict) -> dict:
    return rec.get('attribution_status') or {}


def _stored_rows(provision_id: str | None, codes: Codes):
    """Attribution rows codedb stored on this id. Descendants are not included."""
    if not provision_id:
        return []
    rec = codes.provision(provision_id, 'B')
    if not rec:
        return []
    return _exact_rows(rec.get('attributions'), provision_id)


def _clause_letters(rec: dict, codes: Codes) -> list[str]:
    """Clause marks whose codedb status is direct, in code order."""
    letters = []
    for child in rec.get('children') or []:
        if child.get('level') != 'clause':
            continue
        child_rec = codes.provision(child['id'], 'B')
        if not child_rec or _status(child_rec).get('status') != 'direct':
            continue
        try:
            letter = ids.parse(child['id']).clause
        except ValueError:
            letter = None
        if letter:
            letters.append(f'({letter})')
    return letters


def _attribution(rec: dict, codes: Codes):
    """Pairs and the reported status, taken only from attribution_status."""
    codedb_status = _status(rec).get('status')
    if codedb_status == 'direct':
        return _exact_rows(rec.get('attributions'), rec['id']), 'direct', None, None
    if codedb_status == 'inherits':
        root = _status(rec).get('root_provision')
        return _stored_rows(root, codes), 'inherited from parent', root, None
    if codedb_status == 'clause_level':
        letters = _clause_letters(rec, codes)
        label = 'attributed at clause level: ' + ', '.join(letters) if letters else 'attributed at clause level'
        return [], 'no row in the attribution table', None, label
    return [], 'no row in the attribution table', None, NOT_ATTRIBUTED_LABEL


def _rows_for(rec: dict, codes: Codes) -> list[SectionCRow]:
    """The provision row, plus each direct clause when the sentence is clause_level."""
    rows = [_row(rec, codes)]
    if _status(rec).get('status') != 'clause_level':
        return rows
    for child in rec.get('children') or []:
        if child.get('level') != 'clause':
            continue
        child_rec = codes.provision(child['id'], 'B')
        if child_rec and _status(child_rec).get('status') == 'direct':
            rows.append(_row(child_rec, codes))
    return rows


def _row(rec: dict, codes: Codes) -> SectionCRow:
    pid = rec['id']
    st = _status(rec)
    raw_status = st.get('status')
    source_rows, status, via, label = _attribution(rec, codes)
    pairs = _pairs(source_rows, codes)
    comparisons = rec.get('intent_comparison') or []
    missing = {c['provision_id'] for c in comparisons if c.get('status') == 'provision_missing_in_ae'}
    own_intent = lambda p: p == pid or p.startswith(pid + '(')  # noqa: E731
    intents = [IntentBlock(provision_id=i['provision_id'], objective=i['objective'], brackets=i['brackets'] or [],
                           notes=i['attribution_notes'] or [], intents=i['intents'] or [], pdf_page=i['pdf_page'])
               for i in rec.get('intents') or [] if own_intent(i['provision_id']) and i['provision_id'] not in missing]
    cmp = next((c for c in comparisons if c['provision_id'] == pid and c['provision_id'] not in missing), None)
    unattributed = raw_status not in ('direct', 'inherits', 'clause_level')
    related = st.get('root_provision') if unattributed else None
    return SectionCRow(
        provision_id=pid, citation=rec['citation'], attribution_status=status,
        attributed_via=via, pairs=pairs, intents=intents,
        attribution=NOT_ATTRIBUTED if unattributed else None,
        attribution_label=label if unattributed or raw_status == 'clause_level' else None,
        intent_comparison=cmp['status'] if cmp else None,
        differs=bool(cmp and cmp['status'] == 'differs'),
        only_in_intent=(cmp or {}).get('only_in_intent') or [],
        only_in_ae=(cmp or {}).get('only_in_ae') or [],
        related_root=related, related_root_method=st.get('root_method') if related else None)
