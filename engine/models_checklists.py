"""Standing-package checklists (WP-32). Data in `engine/data/jurisdictions/checklists/`, never code.

A checklist turns one published standing package (a standing posted variance or a city policy) into its
operative conditions, one per row, each with a short verified source quote and the page it is on. The
applicant answers each row: confirmed, not yet, or does not apply (with a reason).

A checklist is never a determination. A confirmed row is the applicant's own declaration; the safety codes
officer decides whether the package applies and whether its conditions are met. Plain-language text never
says the design complies, is safe, is approved or is adequate (`test_checklists.py` enforces the words).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models_jurisdictions import DATE, SLUG, PackSource, StandingPackage

QUOTE_MAX = 260          # fair dealing: a short extract per condition, never a paragraph
AnswerState = Literal['confirmed', 'not_yet', 'does_not_apply']
ANSWER_STATES: tuple[str, ...] = ('confirmed', 'not_yet', 'does_not_apply')

Subject = Literal['project', 'both_houses', 'zero_side', 'easement_side', 'both_parcels', 'building',
                  'each_house_with_suite', 'permit_documents', 'declaration']
ConditionKind = Literal['scope', 'construction', 'agreement', 'documents', 'declaration']


class _Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class SourcePointer(_Strict):
    """Where in the source PDF the condition is. `quote` is checked word for word against the reference text."""
    page: int = Field(ge=1, description='One-based page of the source PDF.')
    label: str | None = Field(default=None, description='The item label the source prints, e.g. "b) ii." or "4. a)".')
    quote: str = Field(min_length=8, max_length=QUOTE_MAX, description='A short extract, verbatim apart from whitespace.')
    lead_in: str | None = Field(default=None, max_length=QUOTE_MAX,
                                description='The sentence the item hangs from, when the item alone is not readable.')
    diagram: str | None = Field(default=None, description='A figure or detail in the source that shows this condition, with its page.')


class ChecklistCondition(_Strict):
    """One operative condition. Plain language first; the source wording sits behind a disclosure."""
    id: str = Field(pattern=SLUG)
    group: str = Field(pattern=SLUG)
    kind: ConditionKind
    subject: Subject = Field(description='What the condition is about: both houses, one side, both parcels, the permit documents...')
    plain: str = Field(min_length=12, description='Plain-language wording shown first.')
    when: str | None = Field(default=None, description='Plain-language trigger when the condition only applies in some designs.')
    one_of: str | None = Field(default=None, pattern=SLUG,
                               description='Options of one choice share this key; the applicant follows one option and marks the others does not apply.')
    option: str | None = Field(default=None, description='The option this row belongs to within `one_of`, as the source labels it.')
    may_not_apply: bool = Field(description='False when the condition always applies to a project that uses the package.')
    source: SourcePointer

    @model_validator(mode='after')
    def _options_are_labelled(self):
        if (self.one_of is None) != (self.option is None):
            raise ValueError(f'{self.id}: one_of and option go together')
        if self.one_of and not self.may_not_apply:
            raise ValueError(f'{self.id}: an option of a choice must allow does_not_apply')
        return self


class ChecklistGroup(_Strict):
    id: str = Field(pattern=SLUG)
    title: str
    plain: str = Field(description='One plain-language line under the group title.')


class SourceNote(_Strict):
    """Something in the source the applicant should know: an inconsistency, an offence warning, a figure-only note."""
    id: str = Field(pattern=SLUG)
    kind: Literal['conflict', 'warning', 'figure_only', 'scope']
    plain: str
    page: int = Field(ge=1)
    quote: str | None = Field(default=None, max_length=QUOTE_MAX,
                              description='Verified like a condition quote; null when the text is only in a figure.')


class StandingChecklist(_Strict):
    """One checklist file. `jurisdiction` and `package` must name a current standing package in a pack."""
    schema_version: Literal[1] = 1
    id: str = Field(pattern=SLUG)
    jurisdiction: str = Field(pattern=SLUG, description='Pack id.')
    package: str = Field(pattern=SLUG, description='Standing package id in that pack.')
    code: str
    title: str
    revision: str | None = None
    issued: str = Field(pattern=DATE)
    summary: str = Field(description='Plain-language: what the package lets you do instead of the Division B solution.')
    reviewed: bool = Field(description='True only after a person has read every row against the source PDF.')
    reviewed_by: str | None = None
    reviewed_on: str | None = Field(default=None, pattern=DATE)
    reference_text: str = Field(pattern=SLUG, description='Stem of the git-excluded reference/text/<stem>.jsonl the quotes are checked against.')
    source: PackSource
    groups: list[ChecklistGroup] = Field(min_length=1)
    conditions: list[ChecklistCondition] = Field(min_length=1)
    source_notes: list[SourceNote] = Field(default_factory=list)

    @model_validator(mode='after')
    def _consistent(self):
        groups = [g.id for g in self.groups]
        ids = [c.id for c in self.conditions]
        if len(set(groups)) != len(groups):
            raise ValueError('group ids repeat')
        if len(set(ids)) != len(ids):
            raise ValueError('condition ids repeat')
        for c in self.conditions:
            if c.group not in groups:
                raise ValueError(f'{c.id}: unknown group {c.group}')
        for key in {c.one_of for c in self.conditions if c.one_of}:
            if len({c.option for c in self.conditions if c.one_of == key}) < 2:
                raise ValueError(f'one_of {key} needs at least two options')
        if self.reviewed != bool(self.reviewed_by and self.reviewed_on):
            raise ValueError('reviewed needs reviewed_by and reviewed_on, and they need reviewed')
        return self


# Wire records.

class ConditionAnswer(_Strict):
    """The applicant's latest answer to one condition, read from case facts. Never a determination."""
    state: AnswerState
    reason: str | None
    fact_id: str


class CaseCondition(ChecklistCondition):
    answer: ConditionAnswer | None = Field(description='null until the applicant answers.')


class AnswerCounts(_Strict):
    total: int
    confirmed: int
    not_yet: int
    does_not_apply: int
    unanswered: int


class ChecklistView(_Strict):
    """A checklist as served. `conditions` carry `answer` only on the case route."""
    id: str
    jurisdiction: str
    package: str
    code: str
    title: str
    revision: str | None
    issued: str
    summary: str
    reviewed: bool
    source: PackSource
    groups: list[ChecklistGroup]
    source_notes: list[SourceNote]
    notice: str


class JurisdictionChecklist(ChecklistView):
    conditions: list[ChecklistCondition]


class CaseChecklist(ChecklistView):
    conditions: list[CaseCondition]
    counts: AnswerCounts
    matches_case_provisions: bool = Field(description='A provision the package varies is among the case provisions.')
    provisions: list[str] = Field(description='Provisions the package names, as printed in the pack.')


class HistoricalPackage(_Strict):
    """A superseded package. Shown for history only; never offered as a checklist."""
    id: str
    code: str
    title: str
    issued: str
    status: Literal['historical']
    historical_reason: str | None
    source: PackSource


class JurisdictionChecklists(_Strict):
    jurisdiction: str
    checklists: list[JurisdictionChecklist]
    historical: list[HistoricalPackage]
    notice: str


class CaseChecklists(_Strict):
    case_id: str
    case_version: int
    jurisdiction: str | None = Field(description='Pack id the case resolved to; null when the case names none.')
    matched_by: str | None
    checklists: list[CaseChecklist]
    historical: list[HistoricalPackage]
    none_reason: str | None = Field(description='Why no checklist is offered, when the list is empty.')
    notice: str


class ChecklistAnswerRequest(_Strict):
    condition_id: str = Field(pattern=SLUG)
    state: AnswerState
    reason: str | None = Field(default=None, max_length=1000)
    expected_version: int = Field(ge=1, strict=True)

    @model_validator(mode='after')
    def _reason_for_not_applicable(self):
        if self.state == 'does_not_apply' and not (self.reason and self.reason.strip()):
            raise ValueError('a reason is required when a condition does not apply')
        return self


class ChecklistAnswerResult(_Strict):
    case_version: int
    checklist: CaseChecklist


def historical(pkg: StandingPackage) -> HistoricalPackage:
    return HistoricalPackage(id=pkg.id, code=pkg.code, title=pkg.title, issued=pkg.issued, status='historical',
                             historical_reason=pkg.historical_reason, source=pkg.source)
