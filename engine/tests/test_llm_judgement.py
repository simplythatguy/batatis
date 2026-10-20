"""Variant C finding shape. A fake client stands in for the provider."""
from engine.completeness_variants import run_variant
from engine.ingest import ingest_bytes
from engine.llm_judgement import JudgementFinding, ScriptedClient, judge_document

RISK = 'If the soffit remains vented, flame could reach the neighbouring property.'


def _document():
    text = (
        '# synthetic variance application\n\n[section B]\n'
        f'FIELD | risk_assessment |  | {RISK}\n'
        'FIELD | mitigating_measures |  | Non-vented soffit material addresses the departure.\n'
        'FIELD | assumptions_and_limits |  | Assumes the distance stays 1.2 m. These are assumptions.\n'
    )
    return ingest_bytes(text.encode(), 'judgement.txt')[0]


def _risk(result):
    return next(element for element in result.elements if element.field == 'risk_assessment')


def test_zero_findings_do_not_change_the_rules():
    result = run_variant('C', _document(), None, ScriptedClient({'findings': []}))
    assert result.skipped is None
    assert result.usage is not None and result.usage.dropped == 0
    assert _risk(result).verdict == 'present'
    assert result.invented_values == 0


def test_one_finding_is_a_typed_object_and_is_applied():
    payload = {'findings': [{
        'field': 'risk_assessment', 'defect_class': 'D09', 'problem': 'generic',
        'verdict': 'unclear', 'reason': 'The quoted span is not about this departure.',
        'quotes': [RISK],
    }]}
    client = ScriptedClient(payload)
    document = _document()
    findings, usage = judge_document(document, client)
    assert usage.dropped == 0 and len(findings) == 1 and isinstance(findings[0], JudgementFinding)
    assert findings[0].field == 'risk_assessment'
    result = run_variant('C', document, None, ScriptedClient(payload))
    element = _risk(result)
    assert element.verdict == 'unclear' and element.problem == 'generic' and element.defect_class == 'D09'
    assert element.quotes and element.quotes[0].text == RISK
    assert result.invented_values == 0


def test_a_malformed_item_is_dropped_and_counted():
    valid = {
        'field': 'risk_assessment', 'defect_class': 'D09', 'problem': 'generic',
        'verdict': 'unclear', 'reason': 'The quoted span is not about this departure.',
        'quotes': [RISK],
    }
    payload = {'findings': ['not-a-finding', {'verdict': 'unclear'}, valid]}
    result = run_variant('C', _document(), None, ScriptedClient(payload))
    assert result.usage.dropped == 2
    assert _risk(result).verdict == 'unclear'
    only_bad = run_variant('C', _document(), None, ScriptedClient({'findings': [{'field': 3}]}))
    assert only_bad.usage.dropped == 1
    assert _risk(only_bad).verdict == 'present'
    assert only_bad.invented_values == 0
