import pytest

from engine import schema_export
from engine.models import Fact, Source


def test_committed_schema_matches_models():
    """Fails when an engine model changes without `python -m engine.schema_export` (the web types follow it)."""
    assert schema_export.main(['--check']) == 0


def test_schema_names_and_enums():
    defs = schema_export.schema()['$defs']
    assert {'Case', 'Fact', 'FactInput', 'SectionCRow', 'NewCase', 'SectionCRequest'} <= set(defs)
    assert defs['Fact']['properties']['kind']['enum'] == ['exact', 'pointed', 'computed', 'proposed']
    assert set(defs['Fact']['required']) == set(defs['Fact']['properties'])          # responses carry every field
    assert set(defs['FactInput']['required']) == {'field', 'value', 'kind', 'source'}


def test_refusal_schema_covers_decisions_statuses_and_final_close_out():
    defs = schema_export.schema()['$defs']
    for model in ['Decision', 'DecisionRequest', 'DecisionSummary']:
        assert set(defs[model]['properties']['outcome']['enum']) == {'accept', 'return', 'refuse'}
    for model, fields in [('Case', ['status']), ('ApplicationSummary', ['status']),
                          ('QueueApplication', ['status']), ('StatusChange', ['from_status', 'to_status'])]:
        for field in fields:
            assert 'refused' in defs[model]['properties'][field]['enum']
    assert set(defs['CloseOut']['properties']['outcome']['enum']) == {'accept', 'refuse'}


def test_refusal_outcome_and_status_are_in_all_wire_records():
    defs = schema_export.schema()['$defs']
    for name in ('Case', 'ApplicationSummary', 'QueueApplication'):
        assert 'refused' in defs[name]['properties']['status']['enum']
    for name in ('Decision', 'DecisionSummary', 'DecisionRequest'):
        assert defs[name]['properties']['outcome']['enum'] == ['accept', 'return', 'refuse']
    assert 'expected_version' in defs['DecisionRequest']['properties']
    assert defs['CloseOut']['properties']['outcome']['enum'] == ['accept', 'refuse']


def test_journey_contracts_export_their_requests_history_and_handoff_fields():
    defs = schema_export.schema()['$defs']
    assert {'submission_number', 'submissions', 'decision_history', 'return_snapshot', 'expires_at',
            'professional_resolutions', 'selected_articles', 'title_is_manual'} <= set(defs['Case']['properties'])
    assert 'submission_blocking' in defs['Gap']['properties']
    assert {'messages', 'decision'} <= set(defs['MessagesResult']['properties'])
    assert 'expected_version' in defs['SubmitRequest']['properties']
    assert 'message_ids' in defs['MessageReadRequest']['properties']
    assert set(defs['ProfessionalRequirementRequest']['required']) == {
        'expected_version', 'required', 'scope', 'basis', 'reference'}
    for name in ('SubmitRequest', 'DecisionRequest', 'MessageReadRequest', 'ProfessionalRequirementRequest'):
        assert defs[name]['additionalProperties'] is False
    for name in ('ApplicationSummary', 'QueueApplication'):
        assert {'submission_number', 'expires_at'} <= set(defs[name]['required'])


def test_formula_and_inputs_only_on_computed_facts():
    src = Source(type='code', ref='formula')
    f = Fact(field='ratio', value=0.26, kind='computed', source=src, formula='0.88 / 3.34', inputs=['a', 'b'])
    assert f.export()['inputs'] == ['a', 'b']
    with pytest.raises(ValueError):
        Fact(field='ratio', value=0.26, kind='pointed', source=src, formula='0.88 / 3.34')


def test_workspace_wire_types_include_routes_and_truthfully_optional_preview_pdf():
    defs = schema_export.schema()['$defs']
    assert {'WorkspaceView', 'WorkspaceSignature', 'WorkspaceSigner', 'SignatureView', 'RewriteRequest',
            'RewriteResult', 'SignatureInput', 'HistoryInput', 'ConsentInput', 'PackagePreview'} <= set(defs)
    assert set(defs['WorkspaceView']['required']) == {
        'content_hash', 'signers', 'signatures', 'consent', 'history'}
    assert 'pdf' not in defs['PackagePreview']['required']
