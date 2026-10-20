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
                         'assumptions_and_limits', 'maintenance_operation', 'qualifications']


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
    citation: str
    required: Literal[True] = True
    answer: ApplicantText | None = None


# Risk/mitigations are required by the challenge workflow; these process citations supply
# the documentation context, without claiming that the code uses those exact field titles.
_FIELDS = (
    ('rationale', 'Rationale', 'Why are you proposing this departure from the acceptable solution?',
     ('Name the confirmed benchmark and the proposed departure.',
      'Identify the analytical method and the reason for choosing it.'), '2.3.1.1.(2)(a)'),
    ('risk_assessment', 'Risk assessment', 'What risks arise from the specific departure?',
     ('Identify affected people, property and failure scenarios.',
      'Link each risk to the benchmark objective/function; identify who assesses it.'), '2.3.1.1.(3)'),
    ('mitigating_measures', 'Mitigating measures', 'What measures address each identified risk?',
     ('Link measures to risks and the Section C objectives/functions.',
      'Point to supporting evidence and identify remaining uncertainties.'), '2.3.1.1.(3)'),
    ('assumptions_and_limits', 'Assumptions and limits', 'What assumptions and limits does your analysis rely on?',
     ('Record use, installation, exposure and project limits.',
      'Identify unverified assumptions and changes that would require reassessment.'), '2.3.1.1.(3)'),
    ('maintenance_operation', 'Maintenance and operation',
     'What operation, maintenance and commissioning conditions are needed after construction?',
     ('Identify activities, intervals, commissioning and responsible people.',
      'If none are needed, have the responsible person state that explicitly with the basis.'), '2.3.1.1.(2)(b)'),
    ('qualifications', 'Qualifications of responsible people', 'Who takes responsibility for the design and analysis?',
     ('Name each person, their scope, qualifications, experience and background.',
      'Identify professional authority where required and a coordinator if several people are responsible.'),
     '2.3.1.1.(4)'),
)

PROCESS_ALIASES = {
    'rationale': ('rationale',),
    'risk_assessment': ('risk_assessment', 'risk'),
    'mitigating_measures': ('mitigating_measures', 'mitigation'),
    'assumptions_and_limits': ('assumptions_and_limits', 'assumptions_limits', 'assumptions'),
    'maintenance_operation': ('maintenance_operation', 'operation_maintenance'),
    'qualifications': ('qualifications',),
}


def latest_fact(case: Case, *fields: str) -> Fact | None:
    """The newest entry controls; an unconfirmed revision must not resurrect an older answer."""
    return next((fact for fact in reversed(case.facts) if fact.field in fields), None)


def confirmed_value(case: Case, *fields: str):
    """A confirmed applicant or file fact. ``demo_seed`` never supplies one.

    A seed-written value does not close a completeness gap and is not
    professional evidence, even when its status is ``confirmed``.
    """
    fact = latest_fact(case, *fields)
    if (fact and fact.status == 'confirmed' and fact.kind != 'proposed'
            and fact.source.type != 'demo_seed'):
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
        rec = codes.provision(pid, 'C')
        if rec is None:
            raise KeyError(f'missing process provision: {pid}')
        fields.append(ProcessField(id=fid, label=label, prompt=prompt,
                                   reviewer_looks_for=structure, citation=rec['citation'], answer=answer))
    return fields
