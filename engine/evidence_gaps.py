"""One administrative evidence gap per provision.

backend/completeness-pipeline (PR #11) emits one gap per objective/function pair.
Replace that loop with ``group_evidence_gaps`` on the plan items that are still
uncovered. Do not copy pair text into a new gap id.

Attaching applicant evidence closes a pair, or every pair of the provision when
the evidence names no pair. Nothing here writes evidence or calls it verified.
"""
from __future__ import annotations

from typing import Literal, Sequence

from pydantic import BaseModel, ConfigDict

from .models import EvidenceItem
from .section_d import EvidencePlanItem


class OpenPair(BaseModel):
    model_config = ConfigDict(extra='forbid')
    function: str
    objective: str


class ProvisionEvidenceGap(BaseModel):
    """A gap list entry PR #11 can append without one row per pair."""

    model_config = ConfigDict(extra='forbid')
    provision_id: str
    citation: str | None = None
    pairs: list[OpenPair] = []
    severity: Literal['blocking', 'warning'] = 'blocking'
    rule: str
    field: str
    missing: str
    fix_hint: str


def evidence_covers_item(item: EvidencePlanItem, evidence: Sequence[EvidenceItem]) -> bool:
    """True when applicant-supplied evidence names this provision and this pair.

    Evidence with no objective and no function covers every pair of the provision.
    ``provided`` means the applicant attached it. It is not a professional verification.
    """
    for entry in evidence:
        if entry.status != 'provided' or entry.provision_id != item.provision_id:
            continue
        if entry.objective is None and entry.function is None:
            return True
        if entry.objective == item.objective and entry.function == item.function:
            return True
    return False


def uncovered_items(items: Sequence[EvidencePlanItem],
                    evidence: Sequence[EvidenceItem]) -> list[EvidencePlanItem]:
    return [item for item in items if item.status != 'provided' and not evidence_covers_item(item, evidence)]


def group_evidence_gaps(items: Sequence[EvidencePlanItem]) -> list[ProvisionEvidenceGap]:
    """Group open plan items by provision id, preserving first-seen order."""
    grouped: dict[str, list[EvidencePlanItem]] = {}
    for item in items:
        grouped.setdefault(item.provision_id, []).append(item)
    gaps: list[ProvisionEvidenceGap] = []
    for provision_id, group in grouped.items():
        citation = next((item.citation for item in group if item.citation), None)
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
            listed = ', '.join(f'{pair.function}–{pair.objective}' for pair in pairs)
            gaps.append(ProvisionEvidenceGap(
                provision_id=provision_id, citation=citation, pairs=pairs, severity='blocking',
                rule='evidence', field=f'evidence.{provision_id}',
                missing=f'supporting evidence for {provision_id}.',
                fix_hint=('Address these objective/function pairs with evidence the applicant supplies: '
                          f'{listed}. Select appropriate evidence types with the responsible designer; '
                          'not every ladder rung is required. Attaching evidence records what was supplied. '
                          'It does not assess or verify it.')))
        else:
            gaps.append(ProvisionEvidenceGap(
                provision_id=provision_id, citation=citation, pairs=[], severity='warning',
                rule='evidence_scope', field=f'evidence.{provision_id}.scope',
                missing=f'an identified performance benchmark for {provision_id}.',
                fix_hint=('The attribution table has no objective or function for this provision. '
                          'Ask the responsible designer which benchmark applies before selecting evidence. '
                          'No objective or function is inferred.')))
    return gaps
