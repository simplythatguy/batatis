"""The intake plan: scope first, then the fork, then at most five questions, plus the pre-application
note and the product-route notice. Deterministic: it reads the case and calls no provider."""
from __future__ import annotations

from ..models import Case, Fact
from ..models_intake import IntakePlan, ScopeCheck
from .fork import assess
from .notices import route_notice
from .preapplication import pre_application
from .questions import PROBES, plan_questions
from .scope import classify

OVERRIDDEN = 'overridden'
SCOPE_FIELD = 'scope.redirect'


def _latest(case: Case) -> dict[str, Fact]:
    out: dict[str, Fact] = {}
    for fact in case.facts:
        # Saved code-check counts use this alias. A newer withdrawal must also
        # replace the older value before the next applicant question is chosen.
        out['storeys' if fact.field == 'building.storeys' else fact.field] = fact
    return out


def description(case: Case) -> str:
    fact = _latest(case).get('project.description')
    return fact.value if fact is not None and isinstance(fact.value, str) else ''


def overridden(case: Case) -> bool:
    fact = _latest(case).get(SCOPE_FIELD)
    return fact is not None and fact.status == 'confirmed' and fact.value == OVERRIDDEN


def scope_check(case: Case) -> ScopeCheck:
    if overridden(case):
        return ScopeCheck(status='overridden')
    return classify(description(case))


def build_plan(case: Case) -> IntakePlan:
    latest = _latest(case)
    text = description(case)
    scope = scope_check(case)
    identify = getattr(case, 'identify', None)
    decisions = {k: v.decision for k, v in (identify.decisions if identify else {}).items()}
    fork = assess(text, decisions=decisions)
    if scope.status == 'redirect':
        fork = fork.model_copy(update={'variance_needed': 'unknown', 'explanation': (
            'This request reads as one for another safety-codes regime, so the building-code fork is not '
            'assessed. If it is a building-code question, say so and Batatis will continue.')})
    value = lambda name: latest[name].value if name in latest else None   # noqa: E731
    previous = case.intake.plan if case.intake and case.intake.plan else None
    not_sure = list(previous.not_sure) if previous else []
    candidates = []
    if identify is not None:
        for article in sorted(identify.articles, key=lambda a: a.rank):
            if decisions.get(article.provision) != 'no':
                candidates.append({'provision': article.provision, 'title': article.title})
    probe_fields = {p.field for p in PROBES} | {'floor_area_m2', 'building_area_ft2', 'lot', 'plan', 'ats_sec'}
    known = {name for name in probe_fields if value(name) not in (None, '')}
    questions = []
    if scope.status != 'redirect':
        questions = plan_questions(
            known=known, prose=text, candidates=candidates, conflicts=case.intake.conflicts if case.intake else [],
            not_sure=set(not_sure), role=value('applicant_role'),
            departure_known=fork.variance_needed == 'likely' or value('alternative_description') not in (None, ''))
    if scope.status == 'redirect':
        step = 'redirect'
    elif any(q.priority == 'critical' for q in questions):
        step = 'questions'
    else:
        step = 'identify'
    return IntakePlan(next=step, scope=scope, fork=fork, questions=questions, not_sure=not_sure,
                      pre_application=pre_application(case, value('municipality')),
                      route_notice=route_notice(value('applicant_role'), value('scope')),
                      candidates_seen=len(candidates))
