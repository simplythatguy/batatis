"""Group current canonical evidence tasks, retaining exact plan-item scope.

PR 30 supplies the applicant wording and one-entry-per-provision presentation.
Coverage comes only from current section_d_plan/check_completeness on the store's
owned-file-normalized Case. Listing text, matching a pair on another provision,
or a withdrawn auto_link=False document cannot close a task here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..completeness import Gap
from ..section_d import EvidencePlanItem


def pair_words(function_text: str | None, objective_text: str | None) -> str | None:
    parts = [part.strip() for part in (function_text, objective_text) if part and part.strip()]
    return '; '.join(parts) if parts else None


def list_documents(provision_id: str) -> str:
    return (f"List the documents you'll rely on for Sentence {provision_id}, "
            "for example a test report, a listing, or a registered professional's opinion. "
            "Batatis records what you list; it doesn't review it. Attach the case-owned file "
            "and explicitly link the relevant plan items; a listing alone does not close attachment gaps.")


@dataclass
class EvidenceTaskGroup:
    provision_id: str
    gaps: list[Gap]
    items: list[EvidencePlanItem]

    @property
    def field(self) -> str:
        return f'evidence.{self.provision_id}'

    @property
    def wording(self) -> str:
        # Current plan performance_issue preserves function/objective wording,
        # clause conditions and the comparison prompt without inferring a pair.
        return ' '.join(dict.fromkeys(item.performance_issue for item in self.items))


def group_evidence_gaps(gaps: Sequence[Gap], items: Sequence[EvidencePlanItem]) -> list[EvidenceTaskGroup]:
    """Group only the actual canonical open tasks; never calculate new coverage."""
    by_field = {f'evidence.{item.id}': item for item in items}
    grouped: dict[str, EvidenceTaskGroup] = {}
    for gap in gaps:
        item = by_field.get(gap.field)
        if not gap.id.startswith('evidence:') or item is None:
            continue
        group = grouped.setdefault(item.provision_id, EvidenceTaskGroup(item.provision_id, [], []))
        group.gaps.append(gap)
        group.items.append(item)
    return list(grouped.values())
