"""Wire models for the coded rules (`GET /rules`, `GET /cases/{id}/rules`)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

RuleState = Literal['follows', 'departs', 'needs_info', 'not_applicable']
RuleValue = str | float | int | bool | None


class RuleProvisionRef(BaseModel):
    id: str
    division: str
    citation: str                    # from the code database, NBC(AE) 2023 2nd printing
    pdf_page: int


class RuleQuestion(BaseModel):
    field: str                       # write the answer as a fact with this field (POST /cases/{id}/facts)
    label: str
    question: str
    why: str


class RuleInputValue(BaseModel):
    field: str
    label: str
    unit: str | None
    value: RuleValue
    fact_id: str | None = None       # the case fact the value came from (case route only)
    fact_status: Literal['confirmed', 'unconfirmed'] | None = None


class RuleComputed(BaseModel):
    name: str
    label: str
    unit: str | None
    value: RuleValue                 # null when it depends on an answer not given


class RuleResult(BaseModel):
    """One rule over one set of inputs. A departure flag against an acceptable solution, never a finding that
    the design as a whole meets the code."""
    rule_id: str
    title: str
    article: str
    state: RuleState
    state_label: str
    outcome_id: str | None           # null for needs_info
    provision: RuleProvisionRef      # the Sentence that decided the state (the rule's main Sentence for needs_info)
    message: str
    next_step: str | None            # departs only: alternative solution (Div C 2.3.1) + request for variance (s.38)
    missing: list[RuleQuestion]      # needs_info only: exactly the inputs that would decide it
    inputs: list[RuleInputValue]
    ignored_inputs: list[str]        # values present but not usable (wrong type, negative): asked again
    computed: list[RuleComputed]
    assumptions: list[str]
    not_checked: list[str]
    reviewed: bool                   # false until a domain reviewer signs the vectors
    unconfirmed_inputs: list[str] = []   # case route: inputs read from facts the applicant has not confirmed


class CaseRules(BaseModel):
    case_id: str
    case_version: int
    edition: str
    notice: str
    results: list[RuleResult]


class RuleSet(BaseModel):
    """Rule definitions for the browser evaluator (web/src/rules/evaluate.ts)."""
    version: int
    edition: str
    index: dict[str, Any]
    rules: list[dict[str, Any]]
