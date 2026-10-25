"""Read a case's facts as rule inputs and evaluate every rule."""
from __future__ import annotations

from ..models import Case, Fact
from .evaluator import evaluate, load_index, load_rules
from .models import CaseRules, RuleResult


def case_inputs(case: Case) -> dict[str, Fact]:
    """Resolve the latest revision before checking usability; nulls and proposals suppress older values."""
    fields = set(load_index()['inputs'])
    latest: dict[str, Fact] = {}
    for fact in case.facts:
        field = 'storeys' if fact.field == 'building.storeys' else fact.field
        if field in fields:
            latest[field] = fact
    return {field: fact for field, fact in latest.items() if fact.kind != 'proposed' and fact.value is not None}


def case_rules(case: Case) -> CaseRules:
    index = load_index()
    facts = case_inputs(case)
    given = {field: fact.value for field, fact in facts.items()}
    results = []
    for rule in load_rules():
        result = RuleResult.model_validate(evaluate(rule, given, index))
        for item in result.inputs:
            fact = facts.get(item.field)
            if fact is not None and item.value is not None:
                item.fact_id, item.fact_status = fact.id, fact.status
        result.unconfirmed_inputs = [i.field for i in result.inputs if i.fact_status == 'unconfirmed']
        results.append(result)
    return CaseRules(case_id=case.id, case_version=case.version, edition=index['edition'], notice=index['notice'],
                     results=results)
