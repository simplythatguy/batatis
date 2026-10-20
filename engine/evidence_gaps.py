"""One administrative evidence gap per provision.

backend/completeness-pipeline (PR #11) emits one gap per objective/function pair.
Replace that loop with ``group_evidence_gaps`` on the plan items that are still
uncovered. Do not copy pair text into a new gap id.

Listing applicant evidence closes a pair, or every pair of the provision when
the evidence names no pair. The closure reason is ``evidence listed (not reviewed)``.
Nothing here writes evidence, reviews it, or calls it verified.
"""
from __future__ import annotations

import re
from typing import Literal, Sequence

from pydantic import BaseModel, ConfigDict

from codedb import ids

from .models import Case, EvidenceItem
from .section_c import NOT_ATTRIBUTED_LABEL
from .section_d import (
    ALTERNATIVE_EVIDENCE_TYPES, CONFIDENCE_LADDER, EvidencePlanItem,
)


class OpenPair(BaseModel):
    model_config = ConfigDict(extra='forbid')
    function: str
    objective: str


# Why an open evidence gap leaves the list. Listing is not a review.
CLOSURE_REASON = 'evidence listed (not reviewed)'
# Plan items still say ``provided`` until #26. Evidence rows say ``evidence_listed``.
# Either value means the applicant listed it. Merge order can land either name first.
LISTED_STATUSES = frozenset({'provided', 'evidence_listed'})


class EvidenceClosure(BaseModel):
    """A gap that left the list because the applicant listed evidence."""

    model_config = ConfigDict(extra='forbid')
    provision_id: str
    pairs: list[OpenPair] = []
    reason: Literal['evidence listed (not reviewed)'] = CLOSURE_REASON


# Confirmed fact ``provision_role`` = ``<role>:<provision id>``.
# departure / affected take an evidence gap. supporting / citing do not.
DEPARTURE_ROLES = frozenset({'departure', 'affected'})
OUT_OF_SCOPE_ROLES = frozenset({'supporting', 'citing'})
_ROLE_VALUE = re.compile(r'^(departure|affected|supporting|citing):(\S+)$')
_PRIORITY_LIMIT = 5


class ProvisionEvidenceGap(BaseModel):
    """A gap list entry PR #11 can append without one row per pair."""

    model_config = ConfigDict(extra='forbid')
    provision_id: str
    citation: str | None = None
    pairs: list[OpenPair] = []
    evidence_types: list[str] = []
    severity: Literal['blocking', 'warning'] = 'blocking'
    priority: bool = False
    rule: str
    field: str
    missing: str
    fix_hint: str


def evidence_covers_item(item: EvidencePlanItem, evidence: Sequence[EvidenceItem]) -> bool:
    """True when applicant-supplied evidence names this provision and this pair.

    Evidence with no objective and no function covers every pair of the provision.
    ``evidence_listed`` means the applicant listed it. It is not a review and not a
    check that the evidence is sufficient.
    """
    for entry in evidence:
        if entry.status not in LISTED_STATUSES or entry.provision_id != item.provision_id:
            continue
        if entry.objective is None and entry.function is None:
            return True
        if entry.objective == item.objective and entry.function == item.function:
            return True
    return False


def uncovered_items(items: Sequence[EvidencePlanItem],
                    evidence: Sequence[EvidenceItem]) -> list[EvidencePlanItem]:
    return [item for item in items if item.status not in LISTED_STATUSES and not evidence_covers_item(item, evidence)]


def provision_roles(case: Case) -> dict[str, str]:
    """Latest confirmed role for each provision. Proposed or unconfirmed labels are ignored."""
    roles: dict[str, str] = {}
    for fact in case.facts:
        if fact.field != 'provision_role' or fact.status != 'confirmed' or fact.kind == 'proposed':
            continue
        if not isinstance(fact.value, str):
            continue
        match = _ROLE_VALUE.match(fact.value.strip())
        if match:
            roles[match.group(2)] = match.group(1)
    return roles


def _under(provision_id: str, root_id: str) -> bool:
    if provision_id == root_id:
        return True
    try:
        parsed = ids.parse(provision_id)
    except ValueError:
        return False
    return any(str(ancestor) == root_id for ancestor in parsed.ancestors())


def evidence_provision_ids(case: Case) -> list[str]:
    """Stored provisions that take an evidence gap.

    With no role labels, every confirmed provision is in scope. Once a label
    exists, only ``departure`` and ``affected`` stay. ``supporting`` and
    ``citing`` are the citing chain and do not get an evidence gap. Sentences
    of a departure article are in scope through :func:`provision_in_scope`.
    """
    confirmed = list(dict.fromkeys(case.provisions))
    roles = provision_roles(case)
    if not roles:
        return confirmed
    return [pid for pid in confirmed
            if roles.get(pid) in DEPARTURE_ROLES and roles.get(pid) not in OUT_OF_SCOPE_ROLES]


def provision_in_scope(case: Case, provision_id: str) -> bool:
    """True when this provision, or a departure article that contains it, takes a gap.

    A sentence marked ``citing`` stays out of scope even when its article is a departure.
    With no role labels, only an id stored on the case is in scope.
    """
    if provision_roles(case).get(provision_id) in OUT_OF_SCOPE_ROLES:
        return False
    roles = provision_roles(case)
    confirmed = list(dict.fromkeys(case.provisions))
    if not roles:
        return provision_id in confirmed
    return any(roles.get(root) in DEPARTURE_ROLES and _under(provision_id, root) for root in confirmed)


def scoped_plan_items(case: Case, items: Sequence[EvidencePlanItem]) -> list[EvidencePlanItem]:
    return [item for item in items if provision_in_scope(case, item.provision_id)]


def _evidence_types(items: Sequence[EvidencePlanItem]) -> list[str]:
    """Ladder order, one mention each. Types are copied from the plan, not invented."""
    order = list(CONFIDENCE_LADDER) + list(ALTERNATIVE_EVIDENCE_TYPES)
    found: list[str] = []
    for item in items:
        for kind in item.recommended_types:
            if kind not in found:
                found.append(kind)
    return sorted(found, key=lambda kind: (order.index(kind) if kind in order else len(order), found.index(kind)))


def _type_list(types: Sequence[str]) -> str:
    return ', '.join(types) if types else 'the evidence types the responsible designer selects'


def _missing_evidence(provision_id: str, types: Sequence[str], pairs: Sequence[OpenPair]) -> str:
    """The completeness message names the provision and each missing evidence item."""
    listed = _type_list(types)
    if pairs:
        named = ', '.join(f'{pair.function}/{pair.objective}' for pair in pairs)
        return f'supporting evidence for {provision_id} ({named}): {listed}.'
    return f'supporting evidence for {provision_id}: {listed}.'


def group_evidence_gaps(items: Sequence[EvidencePlanItem]) -> list[ProvisionEvidenceGap]:
    """One gap per provision. Pairs and evidence types sit on that gap, not in new rows."""
    grouped: dict[str, list[EvidencePlanItem]] = {}
    for item in items:
        grouped.setdefault(item.provision_id, []).append(item)
    gaps: list[ProvisionEvidenceGap] = []
    for provision_id, group in grouped.items():
        citation = next((item.citation for item in group if item.citation), None)
        types = _evidence_types(group)
        paired = [item for item in group if item.objective and item.function]
        if paired:
            pairs: list[OpenPair] = []
            seen = set()
            for item in paired:
                key = (item.function, item.objective)
                if key in seen:
                    continue
                seen.add(key)
                pairs.append(OpenPair(function=item.function, objective=item.objective))
            type_list = _type_list(types)
            gaps.append(ProvisionEvidenceGap(
                provision_id=provision_id, citation=citation, pairs=pairs, evidence_types=types,
                severity='blocking', rule='evidence', field=f'evidence.{provision_id}',
                missing=_missing_evidence(provision_id, types, pairs),
                fix_hint=(f'List evidence the applicant supplies for this provision. '
                          f'{len(pairs)} objective/function pairs are on this gap. '
                          f'Evidence types to discuss: {type_list}. '
                          'Select appropriate evidence types with the responsible designer; '
                          'not every ladder rung is required. Listing evidence records what was named. '
                          'It does not assess or verify it.')))
        else:
            type_list = _type_list(types)
            gaps.append(ProvisionEvidenceGap(
                provision_id=provision_id, citation=citation, pairs=[], evidence_types=types,
                severity='warning', rule='evidence_scope', field=f'evidence.{provision_id}.scope',
                missing=_missing_evidence(provision_id, types, ()),
                fix_hint=(f'{NOT_ATTRIBUTED_LABEL}. '
                          f'Evidence types to discuss: {type_list}. '
                          'No objective or function is on this gap. '
                          'No objective or function is inferred.')))
    return gaps


def rank_gaps(gaps: list) -> list:
    """Blocking gaps first. The first five are ``priority``. Every gap stays in the list."""
    ordered = sorted(gaps, key=lambda gap: gap.severity != 'blocking')
    for index, gap in enumerate(ordered):
        gap.priority = index < _PRIORITY_LIMIT
    return ordered


def evidence_closures(before: Sequence[EvidencePlanItem],
                      after: Sequence[EvidencePlanItem]) -> list[EvidenceClosure]:
    """Pairs that were open and are now covered, each with the listing reason."""
    still = {item.id for item in after}
    closed = [item for item in before if item.id not in still]
    return [EvidenceClosure(provision_id=gap.provision_id, pairs=list(gap.pairs))
            for gap in group_evidence_gaps(closed)]
