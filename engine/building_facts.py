"""Typed building facts the professional-involvement screen reads.

Field names are ``ProfessionalFacts`` in engine/professional.py, plus ``span_m``
from engine/section_d_issues.py. This module does not decide that a design complies or is safe.
"""
from __future__ import annotations

from typing import Annotated

from pydantic import ConfigDict, Field

from .models import Case, Fact, Source
from .professional import ProfessionalFacts


class BuildingFactsUpdate(ProfessionalFacts):
    """Partial update. Omitted fields stay as they are. Null is not a clear.

    JSON numbers such as ``18`` are accepted for metre fields. Occupancy is still
    the closed list on ``ProfessionalFacts``.
    """

    model_config = ConfigDict(extra='forbid', strict=False)
    span_m: Annotated[float, Field(gt=0, allow_inf_nan=False)] | None = None


def _quote(value) -> str:
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return str(value)


def write_building_facts(case: Case, update: BuildingFactsUpdate) -> list[str]:
    """Append one confirmed applicant fact per field that was sent."""
    data = {name: value for name, value in update.model_dump(exclude_unset=True).items() if value is not None}
    if not data:
        raise ValueError('no building facts were sent')
    for name, value in data.items():
        case.facts.append(Fact(
            field=name, value=value, kind='pointed', status='confirmed',
            source=Source(type='user_text', ref='applicant', quote=_quote(value))))
    return list(data)
