"""Persisted Jev relevance probabilities; these are candidate rankings, not code approval."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

Probability = Annotated[float, Field(ge=0, le=1)]


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
    model: Literal['jev-1.13.0'] = 'jev-1.13.0'
    scored_at: str
    description_sha256: str
    stale: bool = False
    scores: dict[str, Probability]
    rerank: dict[str, Probability]
    display: dict[str, Probability]
    bands: RelevanceBands
