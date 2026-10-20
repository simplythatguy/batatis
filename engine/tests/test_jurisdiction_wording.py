"""IB-2026-10-16: the authority having jurisdiction is the organisation, not the officer."""
import json

from engine.models import Jurisdiction


def test_schema_stays_portable_and_names_the_organisation():
    schema = Jurisdiction.model_json_schema()
    assert set(schema['properties']) == {'id', 'name', 'authority'}
    assert set(schema['required']) == {'id', 'name'}
    blob = json.dumps(schema)
    assert 'IB-2026-10-16' in blob
    assert 'accredited organisation' in blob
    assert 'not the individual' in blob
    assert 'Calgary' not in blob
    assert 'officer identifier' in schema['properties']['id']['description']
    record = Jurisdiction(id='alberta-other', name='Synthetic accredited organisation')
    assert record.authority is None
    assert set(record.model_dump()) == {'id', 'name', 'authority'}
