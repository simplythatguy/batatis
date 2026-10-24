"""Persisted relevance estimates; these are candidate rankings, not code approval."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Probability = Annotated[float, Field(ge=0, le=1)]

# Responses and stored rows carry opaque product versions. Private provider pins are mapped
# by engine/relevance.py; old rows keep their historical version and absent provenance.
PUBLIC_MODEL = 'relevance-1'
DECISIONS_PUBLIC_MODEL = 'relevance-2'
ELEPHANT_PUBLIC_MODEL = 'relevance-3'
# Rows stored before the public version existed hold that pin instead. They still load, as PUBLIC_MODEL,
# and the next write stores the public value. The release before this one reads only the pin, so rolling
# back below this change follows the runbook beside ROLLBACK in engine/tests/test_relevance.py: stop
# current-release writers, run the statement, then promote the previous release.
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
    model: Literal['relevance-1', 'relevance-2', 'relevance-3'] = PUBLIC_MODEL
    config_hash: str | None = None           # absent on historical rows; never infer it on reads
    model_ids: dict[str, str | None] = {}    # opaque per-stage versions, absent on historical rows
    scored_at: str
    description_sha256: str
    stale: bool = False
    scores: dict[str, Probability]
    rerank: dict[str, Probability]
    display: dict[str, Probability]
    bands: RelevanceBands

    @field_validator('model_ids')
    @classmethod
    def _stage_models_are_public(cls, value):
        from .public_names import public_model_id
        return {stage: public_model_id(pin) for stage, pin in value.items()}

    @field_validator('model', mode='before')
    @classmethod
    def _legacy_pin_loads_as_the_public_version(cls, value):
        """A row stored with the provider's pin loads as the public version; anything else is checked as given."""
        return PUBLIC_MODEL if isinstance(value, str) and value in LEGACY_MODEL_PINS else value
