"""Section D issues: what the applicant's evidence must address.

Each issue recommends evidence and, where Division C says so, professional involvement.
It does not conclude that a design complies, is safe, or that a supplied opinion is adequate.
Citations are copied from codedb lookups. A reference that does not resolve becomes no citation
and a question.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from .codes import Codes
from .models import Case
from .process_fields import ProcessField, alternative_path, confirmed_value, process_fields
from .professional import ProfessionalFacts, ProfessionalReason, ProfessionalResult, professional_involvement
from .section_d import ALTERNATIVE_EVIDENCE_TYPES, CONFIDENCE_LADDER, EvidencePlanItem, section_d_plan

# NBC(AE) 2023 p2, Div B, Sentence 9.23.1.1.(1) limits prescriptive wood framing to spans of
# 12.20 m or less. Sentence 9.23.1.1.(2) sends framing outside that limit to Part 4. The
# citation is attached only when that sentence resolves in codedb.
PART9_MAX_SPAN_M = 12.20

PracticeValue = bool | Literal['unknown']
IssueStatus = Literal['open', 'addressed', 'needs_professional']

# Reason codes professional.py emits, in the order a Division C rule should be shown.
_YES_PRIORITY = (
    'part4', 'truss_part4', 'preserved_wood_foundation', 'general_building', 'ahj_direction',
    'suppression', 'fire_alarm', 'truss_design',
)
_RULE_IDS = {
    'general_building': ('2.4.1.1.(3)', 'C'),
    'general_exception': ('2.4.1.1.(1)', 'C'),
    'general_unresolved': ('2.4.1.1.(1)', 'C'),
    'secondary_suites': ('2.4.1.1.(2)', 'C'),
    'ahj_direction': ('2.4.1.1.(4)', 'C'),
    'special_safety': ('2.4.1.1.(4)', 'C'),
    'part4': ('2.4.1.2.(1)', 'C'),
    'part4_unknown': ('2.4.1.2.(1)', 'C'),
    'preserved_wood_foundation': ('2.4.1.2.(2)', 'C'),
    'foundation_unknown': ('2.4.1.2.(2)', 'C'),
    'truss_design': ('9.23.14.11.(2)', 'B'),
    'truss_part4': ('2.4.1.2.(1)', 'C'),
    'trusses_unknown': ('2.4.1.2.(1)', 'C'),
    'suppression': ('2.4.1.3.(1)', 'C'),
    'suppression_unknown': ('2.4.1.3.(1)', 'C'),
    'fire_alarm': ('2.4.1.4.(1)', 'C'),
    'fire_alarm_unknown': ('2.4.1.4.(1)', 'C'),
    'design_scope': ('2.4.1.1.(3)', 'C'),
    'professional_law': ('2.4.1.1.(5)', 'C'),
}
_YES_TEXT = {
    'part4': 'The stated work is Part 4 design. Recommend a registered professional skilled in that work.',
    'truss_part4': 'Wood roof-truss connections are stated on a Part 4 route. Recommend a registered professional skilled in that work.',
    'preserved_wood_foundation': 'A Part 4 preserved-wood foundation is stated. Recommend professional retention for installation field reviews before construction.',
    'general_building': 'The stated height, area or dwelling count is outside the general exceptions. Recommend that a registered professional authenticate the applicable drawings and specifications.',
    'ahj_direction': 'The authority has required professional authentication for the stated scope. Recommend naming that professional and the scope.',
    'suppression': 'A fire-suppression system is stated for a building outside the general exceptions. Recommend documenting professional retention for design, field review and witnessing of testing.',
    'fire_alarm': 'A fire-alarm system is stated for a building outside the general exceptions. Recommend documenting professional retention for design, field review and witnessing of verification.',
    'truss_design': 'Wood roof trusses are stated. Recommend engineering responsibility for the truss design and its connections.',
}


class CitedProvision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provision_id: str
    division: Literal['A', 'B', 'C']
    citation: str


class PracticeOfEngineering(BaseModel):
    """Boolean when the Division C screen resolves; ``unknown`` plus a question when it does not."""

    model_config = ConfigDict(extra='forbid')
    value: PracticeValue
    rule: str | None = None
    division: Literal['A', 'B', 'C'] | None = None
    citation: str | None = None
    reason: str
    question: str | None = None

    @model_validator(mode='after')
    def _shape(self):
        if self.value == 'unknown':
            if not (self.question and self.question.strip()):
                raise ValueError('unknown practice of engineering requires a question')
        elif not self.citation or not self.rule or not self.division:
            raise ValueError('a boolean practice flag requires the looked-up Division C rule')
        return self


class EmptyProcessField(BaseModel):
    """A required alternative-path process field with no confirmed applicant answer.

    These are process requirements, not evidence-ladder rungs.
    """

    model_config = ConfigDict(extra='forbid')
    id: str
    label: str
    citation: str


class SectionDIssue(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    provision: CitedProvision | None = None
    entered_reference: str | None = None
    question: str | None = None
    objective: str | None = None
    function: str | None = None
    at_stake: str
    recommended_evidence_types: tuple[str, ...]
    practice_of_engineering: PracticeOfEngineering
    empty_process_fields: tuple[EmptyProcessField, ...]
    status: IssueStatus


def _question(result: ProfessionalResult) -> str:
    for question in result.questions:
        folded = question.casefold()
        if question.strip() and 'safe' not in folded and 'compli' not in folded:
            return question
    return 'Which building facts are still unconfirmed before this practice-of-engineering flag can be set?'


def _pick(result: ProfessionalResult, required: str) -> ProfessionalReason | None:
    chosen = [reason for reason in result.reasons if reason.required == required]
    if required == 'yes':
        order = {code: index for index, code in enumerate(_YES_PRIORITY)}
        chosen.sort(key=lambda reason: order.get(reason.code, len(order)))
    return chosen[0] if chosen else None


def _rule(reason: ProfessionalReason) -> tuple[str, str]:
    return _RULE_IDS.get(reason.code, ('', ''))


def practice_of_engineering(case: Case, codes: Codes) -> PracticeOfEngineering:
    """Ledger-only screen. Missing facts stay unknown; nothing is defaulted to a boolean."""
    span = confirmed_value(case, 'professional.span_m', 'span_m')
    span_handoff = isinstance(span, (int, float)) and not isinstance(span, bool) and span > PART9_MAX_SPAN_M
    facts = ProfessionalFacts.from_case(case)
    if span_handoff and facts.part4_design is not True:
        facts = facts.model_copy(update={'part4_design': True})
    result = professional_involvement(facts, codes)
    return render_practice(result, codes, span_handoff=span_handoff)


def render_practice(result: ProfessionalResult, codes: Codes, *, span_handoff: bool = False) -> PracticeOfEngineering:
    if result.required == 'yes':
        reason = _pick(result, 'yes')
        rule, division = _rule(reason) if reason else ('', '')
        text = _YES_TEXT.get(reason.code, 'Recommend a registered professional for the stated scope.') if reason else (
            'Recommend a registered professional for the stated scope.')
        if span_handoff:
            handoff = codes.provision('9.23.1.1.(2)', 'B')
            if handoff and handoff.get('citation'):
                text += f' The stated span is above the prescriptive framing limit at {handoff["citation"]}.'
            else:
                text += (' The stated span is above the prescriptive framing limit. The Part 4 handoff sentence '
                         'was not found in the code database, so it is not cited.')
        return PracticeOfEngineering(value=True, rule=rule or None, division=division or None,
                                     citation=reason.citation if reason else None, reason=text, question=None)
    if result.required == 'no':
        reason = _pick(result, 'no') or _pick(result, 'depends')
        rule, division = _rule(reason) if reason else ('', '')
        return PracticeOfEngineering(
            value=False, rule=rule or None, division=division or None,
            citation=reason.citation if reason else None,
            reason=('The stated facts fit a general exception. Recommend checking component duties and any '
                    'authority direction. This screen does not decide professional-law scope.'),
            question=None)
    reason = _pick(result, 'depends')
    rule, division = _rule(reason) if reason else ('', '')
    return PracticeOfEngineering(
        value='unknown', rule=rule or None, division=division or None,
        citation=reason.citation if reason else None,
        reason='These facts do not establish whether practice of engineering applies. Ask before setting the flag to yes or no.',
        question=_question(result))


def _at_stake(item: EvidencePlanItem) -> str:
    if item.objective and item.function:
        return (f'Recommend evidence that addresses {item.function} and {item.objective} for benchmark {item.citation}. '
                'Identify the proposed configuration, the comparison the responsible designer selects, '
                'the report passages they rely on, the differences and the limits.')
    return ('The attribution table has no objective or function for this provision. Ask the responsible '
            'designer which performance benchmark applies before selecting evidence.')


def _status(flag: PracticeOfEngineering, attachments) -> IssueStatus:
    named = any((doc.responsible_party or '').strip() or doc.professional_seal for doc in attachments)
    if flag.value is True and not named:
        return 'needs_professional'
    if attachments:
        return 'addressed'
    return 'open'


def _empty_fields(fields: list[ProcessField]) -> tuple[EmptyProcessField, ...]:
    return tuple(EmptyProcessField(id=field.id, label=field.label, citation=field.citation)
                 for field in fields if field.answer is None)


def _lookup(codes: Codes, provision_id: str, division: str):
    try:
        return codes.provision(provision_id, division)
    except (ValueError, KeyError):
        return None


def section_d_issues(case: Case, codes: Codes) -> list[SectionDIssue]:
    """Read-only list. Does not write the case and does not invent a citation or a professional opinion."""
    flag = practice_of_engineering(case, codes)
    empty = _empty_fields(process_fields(case, codes))
    recommended_fallback = CONFIDENCE_LADDER + (ALTERNATIVE_EVIDENCE_TYPES if alternative_path(case) else ())

    if not case.provisions:
        return [SectionDIssue(
            id='benchmark-unconfirmed', provision=None, question=(
                'Confirm the Division B benchmark provisions before recommending performance evidence.'),
            at_stake='No confirmed benchmark is on the case. Recommend evidence only after a provision resolves in the code database.',
            recommended_evidence_types=recommended_fallback, practice_of_engineering=flag,
            empty_process_fields=empty, status=_status(flag, ()))]

    known: list[str] = []
    unresolved: list[SectionDIssue] = []
    for provision_id in dict.fromkeys(case.provisions):
        record = _lookup(codes, provision_id, 'B')
        if record is None or not record.get('citation'):
            unresolved.append(SectionDIssue(
                id=f'unresolved-{provision_id}', provision=None, entered_reference=provision_id,
                question='This entered reference was not found in the code database. Ask which Division B provision is the benchmark. No replacement article is suggested.',
                at_stake='Recommend evidence only after the benchmark resolves in the code database.',
                recommended_evidence_types=recommended_fallback, practice_of_engineering=flag,
                empty_process_fields=empty, status=_status(flag, ())))
        else:
            known.append(provision_id)

    issues = list(unresolved)
    if not known:
        return issues
    scoped = case.model_copy(update={'provisions': known})
    plan = section_d_plan(scoped, codes)
    for item in plan.items:
        record = _lookup(codes, item.provision_id, 'B')
        citation = record.get('citation') if record else None
        if not citation:
            issues.append(SectionDIssue(
                id=item.id, provision=None, entered_reference=item.provision_id,
                question='This provision did not resolve in the code database. Ask for the benchmark again. No citation is offered.',
                objective=None, function=None,
                at_stake='Recommend evidence only after the benchmark resolves in the code database.',
                recommended_evidence_types=item.recommended_types, practice_of_engineering=flag,
                empty_process_fields=empty, status=_status(flag, item.attachments)))
            continue
        question = None
        if not (item.objective and item.function):
            question = 'The attribution table has no objective or function for this provision. Ask the responsible designer which benchmark applies.'
        issues.append(SectionDIssue(
            id=item.id,
            provision=CitedProvision(provision_id=item.provision_id, division='B', citation=citation),
            question=question, objective=item.objective, function=item.function,
            at_stake=_at_stake(item),
            recommended_evidence_types=item.recommended_types, practice_of_engineering=flag,
            empty_process_fields=empty, status=_status(flag, item.attachments)))
    return issues
