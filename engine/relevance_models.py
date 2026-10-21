"""Persisted relevance estimates; these are candidate rankings, not code approval."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Probability = Annotated[float, Field(ge=0, le=1)]

# The only `model` value a response, the schema or a stored row carries: an opaque product version.
# The scoring provider's own model pin stays private (engine/identify/screen.py) and engine/relevance.py
# maps it to this value.
PUBLIC_MODEL = 'relevance-1'
# Rows stored before the public version existed hold that pin instead. They still load, as PUBLIC_MODEL,
# and the next write stores the public value. The release before this one reads only the pin, so rolling
# back below this change needs the ROLLBACK statement in engine/tests/test_relevance.py run first.
LEGACY_MODEL_PINS = frozenset({'jev-1.13.0'})


class RelevanceBands(BaseModel):
    x: Probability
    y: Probability
    status: str

    @model_validator(mode='after')
    def _ordered_thresholds(self):
        if self.x >= self.y:
            raise ValueError('relevance bands require x < y')
        return self


class RelevanceRecord(BaseModel):
    status: Literal['scored'] = 'scored'
    model: Literal['relevance-1'] = PUBLIC_MODEL
    scored_at: str
    description_sha256: str
    stale: bool = False
    scores: dict[str, Probability]
    rerank: dict[str, Probability]
    display: dict[str, Probability]
    bands: RelevanceBands

    @field_validator('model', mode='before')
    @classmethod
    def _legacy_pin_loads_as_the_public_version(cls, value):
        """A row stored with the provider's pin loads as the public version; anything else is checked as given."""
        return PUBLIC_MODEL if isinstance(value, str) and value in LEGACY_MODEL_PINS else value
