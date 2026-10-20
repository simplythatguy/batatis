"""Applicant-authored alternative-solution fields. This module supplies prompts, never answers.

Answers use the shared fact ledger: ``process.<field id>`` (the bare id is also accepted).
Only confirmed, pointed facts copied verbatim from an applicant/file passage become answers.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .codes import Codes
from .models import Case, Fact, Source

ProcessFieldId = Literal['rationale', 'risk_assessment', 'mitigating_measures',
                         'assumptions_and_limits', 'maintenance_operation', 'analysis_detail',
                         'qualifications', 'design_coordinator']


class ApplicantSource(Source):
    model_config = ConfigDict(frozen=True, extra='forbid')
    type: Literal['user_text', 'user_click', 'file']
    ref: str = Field(min_length=1)
    quote: str = Field(min_length=1)


class ApplicantText(BaseModel):
    """A source selection, not a generation interface. Provenance must be truthful at intake."""
    model_config = ConfigDict(frozen=True, extra='forbid')
    value: str = Field(min_length=1)
    author: Literal['applicant'] = 'applicant'
    kind: Literal['pointed'] = 'pointed'
    source: ApplicantSource

    @model_validator(mode='after')
    def _verbatim(self):
        if not self.value.strip() or self.value != self.source.quote:
            raise ValueError('a process answer must be a verbatim applicant/file passage, never generated text')
        return self

    @classmethod
    def from_fact(cls, fact: Fact) -> ApplicantText:
        if fact.status != 'confirmed':
            raise ValueError('the applicant must confirm the process answer')
        return cls(value=fact.value, kind=fact.kind, source=fact.source.model_dump())


class ProcessField(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')
    id: ProcessFieldId
    label: str
    prompt: str
    reviewer_looks_for: tuple[str, ...]
    citation: str | None = None
    required: Literal[True] = True
    answer: ApplicantText | None = None


# Citations are only the sentence that actually requires the field.
# NBC(AE) 2023 p2, Div C, Article 2.3.1.1. [PDF p.739] does not say "risk assessment"
# or "mitigating measures". Those two stay as good practice with no code citation.
# Sentence (3) identifies objectives, functional statements, acceptable solutions,
# assumptions, limiting or restricting factors, testing procedures, engineering studies,
# and building performance parameters. Sentences (5) and (6) have their own fields.
_FIELDS = (
    ('rationale', 'Rationale', 'Why are you proposing this departure from the acceptable solution?',
     ('Name the confirmed benchmark and the proposed departure.',
      'Identify the analytical method and the reason for choosing it.'), '2.3.1.1.(2)(a)'),
    ('risk_assessment', 'Risk assessment',
     'What risks arise from the specific departure? Good practice for this record. '
     'Article 2.3.1.1. does not require a field titled risk assessment.',
     ('Identify affected people, property and failure scenarios.',
      'Link each risk to the benchmark objective/function; identify who assesses it.'), None),
    ('mitigating_measures', 'Mitigating measures',
     'What measures address each identified risk? Good practice for this record. '
     'Article 2.3.1.1. does not require a field titled mitigating measures.',
     ('Link measures to risks and the Section C objectives/functions.',
      'Point to supporting evidence and identify remaining uncertainties.'), None),
    ('assumptions_and_limits', 'Assumptions and limits', 'What assumptions and limits does your analysis rely on?',
     ('Record use, installation, exposure and project limits.',
      'Identify unverified assumptions and changes that would require reassessment.'), '2.3.1.1.(3)'),
    ('maintenance_operation', 'Maintenance and operation',
     'What operation, maintenance and commissioning conditions are needed after construction?',
     ('Identify activities, intervals, commissioning and responsible people.',
      'If none are needed, have the responsible person state that explicitly with the basis.'), '2.3.1.1.(2)(b)'),
    ('analysis_detail', 'Detail of the Code analysis',
     'Where is the detail that conveys the design intent and supports the validity, accuracy, '
     'relevance and precision of the Code analysis?',
     ('Point to that applicant-written detail. Do not draft it.',
      'Sentence 2.3.1.1.(5) requires that detail for the information in Sentence (3).'), '2.3.1.1.(5)'),
    ('qualifications', 'Qualifications of responsible people', 'Who takes responsibility for the design and analysis?',
     ('Name each person, their scope, qualifications, experience and background.',
      'Identify professional authority where the code requires it.'),
     '2.3.1.1.(4)'),
    ('design_coordinator', 'Design coordinator',
     'If more than one person takes responsibility for different aspects of the design, who is the '
     'single person coordinating the design, Code analysis and documentation? If one person is responsible, say so.',
     ('Name that person, or state that one person is responsible. Do not appoint someone.',
      'Sentence 2.3.1.1.(6) applies when more than one person takes responsibility.'), '2.3.1.1.(6)'),
)

PROCESS_ALIASES = {
    'rationale': ('rationale',),
    'risk_assessment': ('risk_assessment', 'risk'),
    'mitigating_measures': ('mitigating_measures', 'mitigation'),
    'assumptions_and_limits': ('assumptions_and_limits', 'assumptions_limits', 'assumptions'),
    'maintenance_operation': ('maintenance_operation', 'operation_maintenance'),
    'analysis_detail': ('analysis_detail',),
    'qualifications': ('qualifications',),
    'design_coordinator': ('design_coordinator', 'coordinator'),
}


def latest_fact(case: Case, *fields: str) -> Fact | None:
    """The newest entry controls; an unconfirmed revision must not resurrect an older answer."""
    return next((fact for fact in reversed(case.facts) if fact.field in fields), None)


def confirmed_value(case: Case, *fields: str):
    fact = latest_fact(case, *fields)
    if fact and fact.status == 'confirmed' and fact.kind != 'proposed':
        return fact.value
    return None


def alternative_path(case: Case) -> bool:
    """Unresolved routing keeps the alternative-path requirements visible."""
    return confirmed_value(case, 'pathway', 'path') not in ('acceptable', 'acceptable_solution')


def process_fields(case: Case, codes: Codes) -> list[ProcessField]:
    if not alternative_path(case):
        return []
    fields = []
    for fid, label, prompt, structure, pid in _FIELDS:
        answer = None
        aliases = PROCESS_ALIASES[fid]
        fact = latest_fact(case, *(f'process.{name}' for name in aliases), *aliases)
        if fact is not None:
            try:
                answer = ApplicantText.from_fact(fact)
            except ValueError:
                pass  # An invalid or proposed value remains a gap, never a generated answer.
        citation = None
        if pid:
            rec = codes.provision(pid, 'C')
            if rec is None:
                raise KeyError(f'missing process provision: {pid}')
            citation = rec['citation']
        fields.append(ProcessField(id=fid, label=label, prompt=prompt,
                                   reviewer_looks_for=structure, citation=citation, answer=answer))
    return fields
