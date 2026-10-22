"""Explicit "not applicable" facts: how an applicant says a form field genuinely does not apply.

Batatis never fills a blank to make a form look complete. A field shows N/A on the exported form only when the
applicant has confirmed a ``not_applicable.<key>`` fact for it, with their own reason, for example
``not_applicable.permit_number = "No building permit has been applied for yet"``.

Rules:
- the fact must be confirmed, applicant-sourced (``user_text`` or ``user_click``) and not proposed;
- its value is the applicant's reason (a non-empty string) or ``True``; ``False`` or blank withdraws it;
- only the keys below may be marked N/A. Owner, mailing address, request date, municipal address, the code
  field, the description and the six process fields always apply, so an N/A on them is a blocking finding;
- a field with both a confirmed value and a confirmed N/A is a contradiction the applicant resolves; Batatis
  does not pick one.
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import Case, Fact

PREFIX = 'not_applicable.'
LABEL = 'N/A'

# Group keys expand to their members (the form's legal description is lot/block/plan OR an ATS location).
GROUPS: dict[str, tuple[str, ...]] = {
    'lot_block_plan': ('lot', 'block', 'plan'),
    'ats': ('ats_qtr', 'ats_sec', 'ats_twp', 'ats_rge', 'ats_mer'),
    'owner_rep': ('owner_rep_name', 'owner_rep_signature_date'),
}
# Whole unused rows of the form's Section C and Section D tables ("these are all the provisions/documents").
ROWS = {'section_c': 'section_c.unused_rows', 'section_d': 'section_d.unused_rows'}
ALLOWED = frozenset({'owner_rep_name', 'owner_rep_signature_date', 'permit_number', *GROUPS['lot_block_plan'],
                     *GROUPS['ats'], *ROWS.values()})
_ALIASES = {'permit': 'permit_number', 'representative': 'owner_rep_name', 'applicant_name': 'owner_rep_name',
            'section_c': ROWS['section_c'], 'section_d': ROWS['section_d']}
# The value facts that fill each key (the export's own aliases), used to detect a value-and-N/A contradiction.
VALUE_FIELDS: dict[str, tuple[str, ...]] = {
    'owner_rep_name': ('owner_rep_name', 'representative', 'applicant_name'),
    'permit_number': ('permit_number', 'permit', 'section_b.permit_number'),
}
_APPLICANT_SOURCES = ('user_text', 'user_click')


@dataclass(frozen=True)
class NotApplicable:
    key: str                 # canonical fact key, e.g. permit_number or section_c.unused_rows
    reason: str              # the applicant's words, or a fixed sentence when the applicant only ticked N/A
    fact_id: str
    source_ref: str
    via: str                 # the fact field that set it (a group key expands to several keys)


def _latest(case: Case) -> dict[str, Fact]:
    out: dict[str, Fact] = {}
    for fact in case.facts:
        if fact.field.startswith(PREFIX):
            out[fact.field] = fact
    return out


def _keys(name: str) -> tuple[str, ...]:
    name = _ALIASES.get(name, name)
    return GROUPS.get(name, (name,))


def _honoured(fact: Fact) -> bool:
    value = fact.value
    return (fact.export()['status'] == 'confirmed' and fact.source.type in _APPLICANT_SOURCES
            and (value is True or (isinstance(value, str) and value.strip() != '')))


def _reason(fact: Fact) -> str:
    if isinstance(fact.value, str):
        return ' '.join(fact.value.split())
    return 'Marked not applicable by the applicant (no reason given).'


def not_applicable(case: Case) -> dict[str, NotApplicable]:
    """Confirmed applicant N/A facts on allowed keys, by canonical key. Disallowed keys are never honoured."""
    out: dict[str, NotApplicable] = {}
    for field, fact in _latest(case).items():
        if not _honoured(fact):
            continue
        for key in _keys(field.removeprefix(PREFIX)):
            if key in ALLOWED:
                out[key] = NotApplicable(key, _reason(fact), fact.id, fact.source.ref, field)
    return out


def _has_value(case: Case, key: str) -> bool:
    for name in VALUE_FIELDS.get(key, (key,)):
        fact = next((f for f in reversed(case.facts) if f.field == name), None)
        if fact is not None and fact.export()['status'] == 'confirmed' and fact.value is not None \
                and str(fact.value).strip() != '':
            return True
    return False


def problems(case: Case) -> list[tuple[str, str, str]]:
    """(field, message, fix hint) for N/A facts that cannot be honoured: a key that always applies, or a key
    that also has a confirmed value. Unconfirmed N/A facts are already reported as unconfirmed facts."""
    out = []
    for field, fact in _latest(case).items():
        if not _honoured(fact):
            if fact.export()['status'] == 'confirmed' and fact.source.type not in _APPLICANT_SOURCES \
                    and fact.value not in (False, None, ''):
                out.append((field, 'an applicant-confirmed "not applicable" statement; this one does not come '
                                   'from the applicant.',
                            'Only the applicant can mark a field not applicable. Ask them to confirm it.'))
            continue
        for key in _keys(field.removeprefix(PREFIX)):
            if key not in ALLOWED:
                out.append((field, f'a value for "{key}"; this field always applies and cannot be marked '
                                   'not applicable.', f'Ask the applicant to enter the {key.replace("_", " ")}.'))
            elif _has_value(case, key):
                out.append((field, f'one answer for "{key}"; it has both a value and a "not applicable" '
                                   'statement.', 'Ask the applicant which one is right and withdraw the other.'))
    return out
