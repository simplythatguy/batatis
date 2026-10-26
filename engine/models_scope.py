"""Source-backed scope conditions, not a finding of code applicability."""
from typing import Literal

from pydantic import BaseModel, Field


class ScopeBasis(BaseModel):
    division: Literal['A'] = 'A'
    provision_id: str
    citation: str
    quote: str


class ScopeCondition(BaseModel):
    field: str
    status: Literal['met', 'not_met', 'unknown', 'conflict']
    values: list[str | float | int | bool | None] = Field(default_factory=list)
    fact_ids: list[str] = Field(default_factory=list)
    explanation: str


class PartScopeAssessment(BaseModel):
    part: Literal[9] = 9
    status: Literal['not_determined', 'boundary_not_met', 'conditions_met_scope_unresolved'] = 'not_determined'
    conditions: list[ScopeCondition] = Field(default_factory=list)
    basis: list[ScopeBasis] = Field(default_factory=list)
    limitation: str = ('This evaluates only supplied scope conditions. It does not establish that Part 9 applies, '
                       'choose every governing Part, or exclude details invoked by another requirement.')
