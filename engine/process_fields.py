"""Applicant-authored alternative-solution fields. This module supplies prompts, never answers.

Answers use the shared fact ledger: ``process.<field id>`` (the bare id is also accepted).
Only confirmed, pointed facts copied verbatim from an applicant/file passage become answers.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .codes import Codes
from .models import Case, Fact, Source
from .process_examples import ProcessExample, example_for

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
    example: ProcessExample | None = None       # precedent structure to read, never text to paste


# Risk/mitigations are required by the challenge workflow; these process citations supply
# the documentation context, without claiming that the code uses those exact field titles.
_FIELDS = (
    ('rationale', 'Rationale', 'Why are you proposing this departure from the acceptable solution?',
     ('Name the confirmed benchmark acceptable solution and the proposed departure.',
      'Explain how the design achieves at least the level of performance of the acceptable solution it '
      'replaces ("as well as", not "well enough"), and the method of analysis and why it was chosen.'),
     '2.3.1.1.(2)(a)'),
    ('risk_assessment', 'Risk assessment', 'What risks arise from the specific departure?',
     ('Identify affected people, property and failure scenarios, including failure of a measure and lapsed '
      'maintenance.',
      'Link each risk to the benchmark objective/function; identify who assesses it.'), '2.3.1.1.(3)'),
    ('mitigating_measures', 'Mitigating measures', 'What measures address each identified risk?',
     ('Link measures to risks and the Section C objectives/functions; say what happens when a measure fails '
      '(mitigation is not elimination).',
      'Point to supporting evidence and identify remaining uncertainties.'), '2.3.1.1.(3)'),
    ('assumptions_and_limits', 'Assumptions and limits', 'What assumptions and limits does your analysis rely on?',
     ('Record use, installation, exposure and project limits, and the testing procedures relied on.',
      'State assumptions about services (for example fire department response), what is unverified, and the '
      'changes that would require reassessment.'), '2.3.1.1.(3)'),
    ('maintenance_operation', 'Maintenance and operation',
     'What operation, maintenance and commissioning conditions are needed after construction?',
     ('Identify activities, intervals, commissioning and responsible people, and what happens if maintenance lapses.',
      'If none are needed, have the responsible person state that explicitly with the basis.'), '2.3.1.1.(2)(b)'),
    ('qualifications', 'Qualifications of responsible people', 'Who takes responsibility for the design and analysis?',
     ('Name each person, their scope, qualifications, experience and background.',
      'Identify professional authority where required and a single coordinator if several people are responsible '
      '(2.3.1.1.(6)).'),
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
    fact = latest_fact(case, *fields)
    if fact and fact.status == 'confirmed' and fact.kind != 'proposed':
        return fact.value
    return None


def alternative_path(case: Case) -> bool:
    """The six process fields open only after the path is alternative.

    A firm follows, a wording match to an acceptable solution, an unknown fork, and a
    not-applicable check all leave the fields closed. An unknown fork is not a variance.
    """
    from .path_decision import decide_path
    return decide_path(case).path == 'alternative'


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
                                   reviewer_looks_for=structure, citation=rec['citation'], answer=answer,
                                   example=example_for(fid)))
    return fields
