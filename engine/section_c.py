"""Section C by deterministic lookup: objective/function rows from the NBC(AE) attribution tables.

No model calls. One row per Division B sentence (an article expands to its sentences; a clause stays a
clause). Attribution status is reported literally:
  direct                           - the table has a row for the sentence (or for its clauses)
  inherited from parent            - a clause with no row of its own takes its sentence's row
  no row in the attribution table  - nothing in the table; Section C must say so, never guess
National 2020 intent statements are attached as explanatory text only, with a flag when their
attribution differs from NBC(AE) 2023.
"""
from __future__ import annotations

import re

from .codes import Codes
from .models import INTENT_LABEL, AttributionPair, Explainer, IntentBlock, SectionCRow

_STATUS = {'direct': 'direct', 'clause_level': 'direct', 'inherits': 'inherited from parent',
           'none': 'no row in the attribution table'}


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


def _row(rec: dict, codes: Codes) -> SectionCRow:
    pid = rec['id']
    st = rec.get('attribution_status') or {}
    raw_status = st.get('status') or ('direct' if rec['attributions'] else 'none')
    pairs = [AttributionPair(function=f, function_text=_text(codes, f), objective=o,
                             objective_text=_text(codes, o), bracket=a['bracket'], clauses=a['clauses'] or [],
                             application_note=a['application_note'], table=a['table_id'], pdf_page=a['pdf_page'])
             for a in rec['attributions'] for f in a['fs'] for o in a['objectives']]
    status = _STATUS[raw_status]
    if status != 'no row in the attribution table' and not pairs:
        status = 'no row in the attribution table'
    own = lambda p: p == pid or p.startswith(pid + '(')            # noqa: E731  sentence and its clauses
    intents = [IntentBlock(provision_id=i['provision_id'], objective=i['objective'], brackets=i['brackets'] or [],
                           notes=i['attribution_notes'] or [], intents=i['intents'] or [], pdf_page=i['pdf_page'])
               for i in rec['intents'] if own(i['provision_id'])]
    cmp = next((c for c in rec['intent_comparison'] if c['provision_id'] == pid), None)
    related = st.get('root_provision') if raw_status == 'none' else None
    return SectionCRow(
        provision_id=pid, citation=rec['citation'], attribution_status=status,
        attributed_via=st.get('root_provision') if raw_status == 'inherits' else None,
        pairs=pairs, intents=intents,
        intent_comparison=cmp['status'] if cmp else None,
        differs=bool(cmp and cmp['status'] == 'differs'),
        only_in_intent=(cmp or {}).get('only_in_intent') or [],
        only_in_ae=(cmp or {}).get('only_in_ae') or [],
        related_root=related, related_root_method=st.get('root_method') if related else None,
        explainer=_explainer(rec, status, pairs, intents))


def _quote(text: str, limit: int = 240) -> str | None:
    flat = re.sub(r'\s+', ' ', text or '').strip()
    if not flat:
        return None
    if len(flat) <= limit:
        return flat
    cut = flat[:limit]
    return cut.rsplit(' ', 1)[0] if ' ' in cut else cut


def _explainer(rec: dict, status: str, pairs: list[AttributionPair], intents: list[IntentBlock]) -> Explainer | None:
    """Template over codedb text. Null when the sentence has no text to quote."""
    quote = _quote(rec.get('text') or '')
    if not quote:
        return None
    objs = list(dict.fromkeys(p.objective for p in pairs))
    fns = list(dict.fromkeys(p.function for p in pairs))
    bits = [f'Division B {rec["id"]} is quoted from the code database. Attribution status: {status}.']
    if objs or fns:
        bits.append(f'Objectives: {", ".join(objs) or "none"}. Functions: {", ".join(fns) or "none"}.')
    else:
        bits.append('The NBC(AE) attribution table has no objective or function for this sentence.')
    bits.append(f'{INTENT_LABEL}.' if intents else 'No national intent statement is attached to this sentence.')
    return Explainer(text=' '.join(bits), quote=quote, source='deterministic')
