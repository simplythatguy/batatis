"""Section D issues: what the applicant's evidence must address.

Each issue recommends evidence and, where Division C says so, professional involvement.
It does not conclude that a design complies, is safe, or that a supplied opinion is adequate.
Citations are copied from codedb lookups. A reference that does not resolve becomes no citation
and a question. This module does not write the case and does not fill a professional's name,
discipline, seal, or registration number.
"""
from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from .codes import Codes
from .human_review import HumanReview, human_reviews
from .models import Case
from .process_fields import ProcessField, alternative_path, confirmed_value, latest_fact, process_fields
from .professional import (
    PART9_MAX_SPAN_M, PracticePrompt, ProfessionalReason, ProfessionalResult, commercial_party,
    professional_confirmed, professional_involvement, unresolved_item,
)
from .section_d import (
    ALTERNATIVE_EVIDENCE_TYPES, CONFIDENCE_LADDER, EvidencePlanItem, EvidenceType, section_d_plan,
)

# A confirmed span above this value is screened as Part 4 design by the shared case decision.
# This handoff came from development case dev-050. The only provision cited for that
# result is Div C 2.4.1.2.(1), which engine/professional.py already passes to add().
# This module does not add a provision id.

# Every practice-screen id below is a string literal already passed to add() in
# engine/professional.py. Process-field ids are the literals in engine/process_fields.py
# _FIELDS. Nothing else is looked up as a rule.
PROFESSIONAL_RULES = (
    ('C', '2.4.1.1.(1)', 'engine/professional.py: general_exception, general_unresolved'),
    ('C', '2.4.1.1.(2)', 'engine/professional.py: secondary_suites'),
    ('C', '2.4.1.1.(3)', 'engine/professional.py: general_building, design_scope'),
    ('C', '2.4.1.1.(4)', 'engine/professional.py: ahj_direction, special_safety'),
    ('C', '2.4.1.1.(5)', 'engine/professional.py: professional_law'),
    ('C', '2.4.1.2.(1)', 'engine/professional.py: part4, part4_unknown, truss_part4, trusses_unknown'),
    ('C', '2.4.1.2.(2)', 'engine/professional.py: preserved_wood_foundation, foundation_unknown'),
    ('C', '2.4.1.3.(1)', 'engine/professional.py: suppression, suppression_unknown'),
    ('C', '2.4.1.4.(1)', 'engine/professional.py: fire_alarm, fire_alarm_unknown'),
    ('B', '9.23.14.11.(2)', 'engine/professional.py: truss_design'),
)
PROCESS_RULES = (
    ('C', '2.3.1.1.(2)(a)', 'engine/process_fields.py: rationale'),
    ('C', '2.3.1.1.(2)(b)', 'engine/process_fields.py: maintenance_operation'),
    ('C', '2.3.1.1.(3)', 'engine/process_fields.py: risk_assessment, mitigating_measures, assumptions_and_limits'),
    ('C', '2.3.1.1.(4)', 'engine/process_fields.py: qualifications'),
)

PracticeValue = bool | Literal['unknown']
IssueStatus = Literal['open', 'evidence_listed', 'needs_professional']

log = logging.getLogger(__name__)

# Used only when the Division C screen is unresolved and every specific question was unusable.
GENERIC_FALLBACK_QUESTION = (
    'Which building facts are still unconfirmed before this practice-of-engineering flag can be set?')

# The applicant has to confirm these. A name or seal copied off a document does not count.
PROFESSIONAL_REQUEST = (
    'Name the registered professional for this scope: name, discipline (engineer or architect), '
    'and APEGA or AAA registration number. A seal the applicant confirms can stand in for the number. '
    'This screen does not fill the name, the discipline, or the number.')
_APPLICANT_SOURCES = frozenset({'user_text', 'user_click'})
_PROCESS_RULE_IDS = {
    'rationale': ('C', '2.3.1.1.(2)(a)'),
    'maintenance_operation': ('C', '2.3.1.1.(2)(b)'),
    'risk_assessment': ('C', '2.3.1.1.(3)'),
    'mitigating_measures': ('C', '2.3.1.1.(3)'),
    'assumptions_and_limits': ('C', '2.3.1.1.(3)'),
    'qualifications': ('C', '2.3.1.1.(4)'),
}

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
    'systems_unknown': ('2.4.1.3.(1)', 'C'),
    'firestop_scope': ('2.4.1.3.(1)', 'C'),
    'part_scope': ('1.3.3.3.(1)', 'A'),
    'fire_alarm': ('2.4.1.4.(1)', 'C'),
    'fire_alarm_unknown': ('2.4.1.4.(1)', 'C'),
    'design_scope': ('2.4.1.1.(3)', 'C'),
    'professional_law': ('2.4.1.1.(5)', 'C'),
    'gross_area_acts': ('2.4.1.1.(5)', 'C'),
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
    prompts: tuple[PracticePrompt, ...] = ()
    routed_to: Literal['officer', 'professional', 'applicant'] | None = None

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
    recommended_types: tuple[EvidenceType, ...]
    practice_of_engineering: PracticeOfEngineering
    empty_process_fields: tuple[EmptyProcessField, ...]
    human_review: tuple[HumanReview, ...] = ()
    status: IssueStatus
    routed_to: Literal['officer', 'professional', 'applicant'] | None = None


def _question(result: ProfessionalResult) -> str:
    for question in result.questions:
        folded = question.casefold()
        if question.strip() and 'safe' not in folded and 'compli' not in folded:
            return question
    log.info('generic fallback practice question')
    return GENERIC_FALLBACK_QUESTION


def _applicant_confirmed(case: Case, *fields: str) -> str | None:
    """Confirmed applicant text or an explicit confirmation. Document sources do not qualify."""
    fact = latest_fact(case, *fields)
    if fact is None or fact.status != 'confirmed' or fact.kind == 'proposed':
        return None
    if fact.source.type not in _APPLICANT_SOURCES:
        return None
    if not isinstance(fact.value, str) or not fact.value.strip():
        return None
    return fact.value.strip()


def _pick(result: ProfessionalResult, required: str) -> ProfessionalReason | None:
    chosen = [reason for reason in result.reasons if reason.required == required]
    if required == 'yes':
        order = {code: index for index, code in enumerate(_YES_PRIORITY)}
        chosen.sort(key=lambda reason: order.get(reason.code, len(order)))
    return chosen[0] if chosen else None


def _rule(reason: ProfessionalReason) -> tuple[str, str]:
    if reason.code.startswith('mandatory:'):
        _, division, provision = reason.code.split(':', 2)
        return provision, division
    return _RULE_IDS.get(reason.code, ('', ''))


def practice_of_engineering(case: Case, codes: Codes) -> PracticeOfEngineering:
    """Ledger-only screen. Missing facts stay unknown; nothing is defaulted to a boolean."""
    span = confirmed_value(case, 'professional.span_m', 'span_m')
    span_handoff = isinstance(span, (int, float)) and not isinstance(span, bool) and span > PART9_MAX_SPAN_M
    return render_practice(professional_involvement(case, codes), codes, span_handoff=span_handoff)


_UNRESOLVED_CITATION_REASON = (
    'The rule for this practice screen did not resolve in the code database. '
    'Ask before setting the flag to yes or no.')
_UNRESOLVED_CITATION_QUESTION = (
    'Which professional-involvement rule applies? No citation was returned.')


def _flag(value: PracticeValue, reason_row: ProfessionalReason | None, text: str, question: str | None) -> PracticeOfEngineering:
    """A yes or no flag needs the looked-up rule. A missing citation becomes unknown, not an error."""
    rule, division = _rule(reason_row) if reason_row else ('', '')
    citation = reason_row.citation if reason_row else None
    if value == 'unknown' or (rule and division and citation and str(citation).strip()):
        return PracticeOfEngineering(value=value, rule=rule or None, division=division or None,
                                     citation=citation or None, reason=text, question=question)
    return PracticeOfEngineering(value='unknown', rule=rule or None, division=division or None,
                                 reason=_UNRESOLVED_CITATION_REASON,
                                 question=(f'The citation lookup for Division {division} {rule} failed. '
                                           'Ask the code reviewer to verify this reference before setting the flag.'
                                           if rule and division else _UNRESOLVED_CITATION_QUESTION))


def _with_prompts(flag: PracticeOfEngineering, result: ProfessionalResult) -> PracticeOfEngineering:
    return flag.model_copy(update={'prompts': tuple(result.prompts), 'routed_to': result.routed_to})


def render_practice(result: ProfessionalResult, codes: Codes, *, span_handoff: bool = False) -> PracticeOfEngineering:
    if result.required == 'yes':
        reason = _pick(result, 'yes')
        text = _YES_TEXT.get(reason.code, 'Recommend a registered professional for the stated scope.') if reason else (
            'Recommend a registered professional for the stated scope.')
        if span_handoff:
            text += ' The stated span is recorded as Part 4 design, so the same Division C rule applies.'
        return _with_prompts(_flag(True, reason, text, PROFESSIONAL_REQUEST), result)
    if result.required == 'no':
        reason = _pick(result, 'no') or _pick(result, 'depends')
        return _with_prompts(_flag(False, reason,
                     ('The stated facts fit a general exception. Recommend checking component duties and any '
                      'authority direction. This screen does not decide professional-law scope.'),
                     None), result)
    reason = _pick(result, 'depends')
    rule, division = _rule(reason) if reason else ('', '')
    question = _question(result)
    return _with_prompts(PracticeOfEngineering(
        value='unknown', rule=rule or None, division=division or None,
        citation=(reason.citation or None) if reason else None,
        reason=unresolved_item(question, result.routed_to),
        question=question), result)


def _at_stake(item: EvidencePlanItem) -> str:
    if item.objective and item.function:
        return (f'Recommend evidence that addresses {item.function} and {item.objective} for benchmark {item.citation}. '
                'Identify the proposed configuration, the comparison the responsible designer selects, '
                'the report passages they rely on, the differences and the limits.')
    return ('The attribution table has no objective or function for this provision. Ask the responsible '
            'designer which performance benchmark applies before selecting evidence.')


def _commercial_attachment(case: Case, doc) -> bool:
    """An unsigned vendor or sales email is not professional evidence."""
    fact = latest_fact(case, f'evidence.{doc.id}.file_ref')
    quote = fact.source.quote if fact is not None and isinstance(fact.source.quote, str) else ''
    seal = doc.professional_seal if isinstance(doc.professional_seal, str) else ''
    return commercial_party(doc.responsible_party, doc.issuer, doc.title, quote, seal)


def _status(case: Case, flag: PracticeOfEngineering, attachments) -> IssueStatus:
    """None of these values is a sign-off or a compliance determination."""
    if flag.value == 'unknown':
        return 'open'
    if flag.value is True and not professional_confirmed(case):
        return 'needs_professional'
    if any(not _commercial_attachment(case, doc) for doc in attachments):
        return 'evidence_listed'
    return 'open'


def _empty_fields(fields: list[ProcessField]) -> tuple[EmptyProcessField, ...]:
    return tuple(EmptyProcessField(id=field.id, label=field.label, citation=field.citation)
                 for field in fields if field.answer is None)


def _lookup(codes: Codes, provision_id: str, division: str):
    try:
        return codes.provision(provision_id, division)
    except (ValueError, KeyError):
        return None


def _routed(flag: PracticeOfEngineering, status: IssueStatus):
    if status == 'needs_professional':
        return 'professional'
    return flag.routed_to


def _with_review(case: Case, codes: Codes, issues: list[SectionDIssue]) -> list[SectionDIssue]:
    reviews = human_reviews(case, codes)
    return [issue.model_copy(update={
        'human_review': reviews,
        'routed_to': _routed(issue.practice_of_engineering, issue.status),
    }) for issue in issues]


def section_d_issues(case: Case, codes: Codes) -> list[SectionDIssue]:
    """Read-only list. Does not write the case and does not invent a citation or a professional opinion."""
    flag = practice_of_engineering(case, codes)
    empty = _empty_fields(process_fields(case, codes))
    recommended_fallback = CONFIDENCE_LADDER + (ALTERNATIVE_EVIDENCE_TYPES if alternative_path(case) else ())

    if not case.provisions:
        return _with_review(case, codes, [SectionDIssue(
            id='benchmark-unconfirmed', provision=None, question=(
                'Confirm the Division B benchmark provisions before recommending performance evidence.'),
            at_stake='No confirmed benchmark is on the case. Recommend evidence only after a provision resolves in the code database.',
            recommended_types=recommended_fallback, practice_of_engineering=flag,
            empty_process_fields=empty, status=_status(case, flag, ()))])

    known: list[str] = []
    unresolved: list[SectionDIssue] = []
    for provision_id in dict.fromkeys(case.provisions):
        record = _lookup(codes, provision_id, 'B')
        if record is None or not record.get('citation'):
            unresolved.append(SectionDIssue(
                id=f'unresolved-{provision_id}', provision=None, entered_reference=provision_id,
                question='This entered reference was not found in the code database. Ask which Division B provision is the benchmark. No replacement article is suggested.',
                at_stake='Recommend evidence only after the benchmark resolves in the code database.',
                recommended_types=recommended_fallback, practice_of_engineering=flag,
                empty_process_fields=empty, status=_status(case, flag, ())))
        else:
            known.append(provision_id)

    issues = list(unresolved)
    if not known:
        return _with_review(case, codes, issues)
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
                recommended_types=item.recommended_types, practice_of_engineering=flag,
                empty_process_fields=empty, status=_status(case, flag, item.attachments)))
            continue
        question = None
        if not (item.objective and item.function):
            question = 'The attribution table has no objective or function for this provision. Ask the responsible designer which benchmark applies.'
        issues.append(SectionDIssue(
            id=item.id,
            provision=CitedProvision(provision_id=item.provision_id, division='B', citation=citation),
            question=question, objective=item.objective, function=item.function,
            at_stake=_at_stake(item),
            recommended_types=item.recommended_types, practice_of_engineering=flag,
            empty_process_fields=empty, status=_status(case, flag, item.attachments)))
    return _with_review(case, codes, issues)


def generic_fallback_on_dev(cases: list[dict], codes: Codes) -> int:
    """Count fallback questions for dev cases as the issues route sees them.

    Each case contributes its seed provision only. The route does not read the prose
    and does not infer facts from it.
    """
    fired = 0
    for case in cases:
        seed = case.get('seed_provision')
        provisions = [seed] if isinstance(seed, str) and seed else []
        issues = section_d_issues(Case(provisions=provisions), codes)
        if any(issue.practice_of_engineering.question == GENERIC_FALLBACK_QUESTION for issue in issues):
            fired += 1
    log.info('generic fallback practice question fired %s times on %s dev cases', fired, len(cases))
    return fired


def _cited(issue: SectionDIssue) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    if issue.provision and issue.provision.citation:
        rows.append((issue.provision.division, issue.provision.provision_id, issue.provision.citation))
    flag = issue.practice_of_engineering
    if flag.rule and flag.division and flag.citation:
        rows.append((flag.division, flag.rule, flag.citation))
    for field in issue.empty_process_fields:
        rule = _PROCESS_RULE_IDS.get(field.id)
        if rule and field.citation:
            rows.append((rule[0], rule[1], field.citation))
    from .human_review import REVIEW_PROVISIONS
    for review in issue.human_review:
        for division, provision_id in REVIEW_PROVISIONS:
            if provision_id in review.cite:
                rows.append((division, provision_id, review.cite))
    return rows


def citation_resolution(cases: list[dict], codes: Codes) -> tuple[int, int]:
    """Unique cited provisions from one issues-endpoint pass, and how many still resolve."""
    seen: dict[tuple[str, str], str] = {}
    for case in cases:
        seed = case.get('seed_provision')
        provisions = [seed] if isinstance(seed, str) and seed else []
        for issue in section_d_issues(Case(provisions=provisions), codes):
            for division, provision_id, citation in _cited(issue):
                seen.setdefault((division, provision_id), citation)
    resolved = 0
    for (division, provision_id), citation in seen.items():
        record = _lookup(codes, provision_id, division)
        if record and record.get('citation') == citation:
            resolved += 1
    return resolved, len(seen)
