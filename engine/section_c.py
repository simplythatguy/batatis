"""Section C by deterministic lookup: objective/function rows from the NBC(AE) attribution tables.

No model calls. One row per Division B sentence (an article expands to its sentences; a clause stays a
clause). Attribution status is reported literally:
  direct                           - the table has a row for this provision id
  inherited from parent            - no row here; pairs are copied from a parent sentence or article,
                                     or from a clause when the sentence itself has none. attributed_via
                                     is that source id
  no row in the attribution table  - nothing on this id, its parent sentence, or its article; never guess
A cited provision is always one of those rows. When the row has no objective or function, attribution
is ``not_attributed`` and the user-facing label is ``lookup not available``. The intent statement
stays when the database has one. A codedb status of none with root method not_determined is not a
parent to copy, and a sibling sentence is not copied either.
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
            rows.extend(_row(codes.provision(c['id'], 'B'), codes) for c in targets)
        else:
            rows.append(_row(rec, codes))
    return rows


def _text(codes: Codes, code: str) -> str | None:
    d = codes.definition(code)
    return d['title'] if d else None


def _pairs(rows, codes: Codes) -> list[AttributionPair]:
    return [AttributionPair(function=f, function_text=_text(codes, f), objective=o,
                            objective_text=_text(codes, o), bracket=a['bracket'], clauses=a['clauses'] or [],
                            application_note=a['application_note'], table=a['table_id'], pdf_page=a['pdf_page'])
            for a in rows for f in a['fs'] for o in a['objectives']]


def _source_id(rows) -> str | None:
    found = list(dict.fromkeys(pid for a in rows if (pid := a.get('provision_id'))))
    if not found:
        return None
    return found[0] if len(found) == 1 else ', '.join(found)


def _exact_rows(attributions, provision_id: str):
    """Rows stored for this id. A row with no id belongs to the provision being read."""
    return [a for a in attributions or [] if a.get('provision_id', provision_id) == provision_id]


def _parent_rows(pid: str, codes: Codes):
    """Clause to sentence to article, using only rows stored on that ancestor.

    Descendant sentences of an article are not copied onto a sibling. An empty
    result means Section C must leave the objective and function blank.
    """
    try:
        parsed = ids.parse(pid)
    except ValueError:
        return [], None
    for ancestor in parsed.ancestors():
        if ancestor.level not in ('clause', 'sentence', 'article'):
            continue
        parent = codes.provision(str(ancestor), 'B')
        taken = _exact_rows(parent['attributions'], str(ancestor)) if parent else []
        if taken:
            return taken, str(ancestor)
        if ancestor.level == 'article':
            break
    return [], None


def _unattributed(rec: dict) -> bool:
    """Codedb says this provision has no attribution and no determined root.

    Parent rows are not copied onto it. That would invent an objective or function.
    """
    status = rec.get('attribution_status') or {}
    return status.get('status') == 'none' and status.get('root_method') == 'not_determined'


def _attribution(rec: dict, codes: Codes):
    """Own row, else rows lookup already inherited, else the parent chain."""
    pid = rec['id']
    rows = list(rec.get('attributions') or [])
    own = _exact_rows(rows, pid)
    if own:
        return own, 'direct', None
    if _unattributed(rec):
        return [], 'no row in the attribution table', None
    other = [a for a in rows if a.get('provision_id') != pid]
    if other:
        return other, 'inherited from parent', _source_id(other)
    inherited, via = _parent_rows(pid, codes)
    if inherited:
        return inherited, 'inherited from parent', via
    return [], 'no row in the attribution table', None


def _row(rec: dict, codes: Codes) -> SectionCRow:
    pid = rec['id']
    st = rec.get('attribution_status') or {}
    raw_status = st.get('status') or ('direct' if rec.get('attributions') else 'none')
    source_rows, status, via = _attribution(rec, codes)
    pairs = _pairs(source_rows, codes)
    if not pairs:
        status, via = 'no row in the attribution table', None
    comparisons = rec.get('intent_comparison') or []
    missing = {c['provision_id'] for c in comparisons if c.get('status') == 'provision_missing_in_ae'}
    own_intent = lambda p: p == pid or p.startswith(pid + '(')  # noqa: E731
    intents = [IntentBlock(provision_id=i['provision_id'], objective=i['objective'], brackets=i['brackets'] or [],
                           notes=i['attribution_notes'] or [], intents=i['intents'] or [], pdf_page=i['pdf_page'])
               for i in rec.get('intents') or [] if own_intent(i['provision_id']) and i['provision_id'] not in missing]
    cmp = next((c for c in comparisons if c['provision_id'] == pid and c['provision_id'] not in missing), None)
    related = st.get('root_provision') if status == 'no row in the attribution table' and raw_status == 'none' else None
    # Parent fallback already ran. An empty row is stated; it is not left blank.
    unattributed = not pairs
    return SectionCRow(
        provision_id=pid, citation=rec['citation'], attribution_status=status,
        attributed_via=via, pairs=pairs, intents=intents,
        attribution=NOT_ATTRIBUTED if unattributed else None,
        attribution_label=NOT_ATTRIBUTED_LABEL if unattributed else None,
        intent_comparison=cmp['status'] if cmp else None,
        differs=bool(cmp and cmp['status'] == 'differs'),
        only_in_intent=(cmp or {}).get('only_in_intent') or [],
        only_in_ae=(cmp or {}).get('only_in_ae') or [],
        related_root=related, related_root_method=st.get('root_method') if related else None)
