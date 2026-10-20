"""Bulletin gates. No code database and no SCC form required."""
from engine.bulletin_gates import applicant_reminder, bulletin_gaps
from engine.completeness_variants import run_variant
from engine.ingest import ingest_bytes
from engine.models import Case, Fact, Jurisdiction, Source

DOC = ('The Division C Section 2.3.1 documentation for this alternative solution is included '
       'with this application.')


def _fact(field, value):
    return Fact(field=field, value=value, kind='pointed', status='confirmed',
                source=Source(type='user_text', ref='synthetic-bulletin', quote=str(value)))


def _case(**facts):
    # IB-2026-10-16: the organisation holds jurisdiction.
    case = Case(title='Synthetic bulletin fixture',
                jurisdiction=Jurisdiction(id='edmonton', name='City of Edmonton', authority='City of Edmonton'),
                facts=[_fact(key, value) for key, value in facts.items()])
    return case


def _form(lines: list[str]) -> str:
    return '# synthetic variance application\n\n[section B]\n' + '\n'.join(lines) + '\n'


def test_documentation_and_one_location_pass():
    gaps = bulletin_gaps(_case(**{
        'division_c_2_3_1': DOC,
        'civic_address': '100 Example Avenue, Edmonton, Alberta',
    }))
    assert gaps == []


def test_missing_division_c_documentation_cites_ib_2025_11_18():
    gaps = bulletin_gaps(_case(civic_address='100 Example Avenue, Edmonton, Alberta'))
    assert len(gaps) == 1
    gap = gaps[0]
    assert gap.id == 'IB-DOC:division_c_2_3_1'
    assert gap.citation == 'IB-2025-11-18'
    assert gap.field == 'division_c_2_3_1'
    assert gap.message.startswith('Your application appears to be missing ')
    assert 'safety codes officer needs to issue and register' in gap.message
    assert 'applicant duty' not in gap.message.casefold()
    assert 'within 10 days' not in gap.message
    assert 'within 10 days' not in gap.fix_hint


def test_second_location_and_semicolon_cite_ib_2026_10_01_but_a_comma_does_not():
    second = bulletin_gaps(_case(**{
        'division_c_2_3_1': DOC,
        'civic_address': '100 Example Avenue, Edmonton, Alberta',
        'additional_location': '200 Example Road, Edmonton, Alberta',
    }))
    assert [gap.id for gap in second] == ['IB-LOC:single_location']
    assert second[0].citation == 'IB-2026-10-01'
    assert 'Do not choose a location' in second[0].fix_hint
    assert 'safety codes officer registers' in second[0].fix_hint
    split = bulletin_gaps(_case(**{
        'division_c_2_3_1': DOC,
        'civic_address': '100 Example Avenue, Edmonton, Alberta; 200 Example Road, Edmonton, Alberta',
    }))
    assert [gap.id for gap in split] == ['IB-LOC:single_location']
    comma = bulletin_gaps(_case(**{
        'division_c_2_3_1': DOC,
        'civic_address': '100 Example Avenue, Edmonton, Alberta',
    }))
    assert comma == []


def test_acceptable_path_does_not_take_variance_gates():
    gaps = bulletin_gaps(_case(pathway='acceptable', civic_address='1 A Street; 2 B Street'))
    assert gaps == []


def test_copy_deadline_is_a_reminder_not_a_gap():
    reminder = applicant_reminder()
    assert reminder['verdict'] == 'reminder'
    assert reminder['bulletin_ids'] == ['IB-2025-11-18', 'IB-2026-10-01']
    folded = reminder['text'].casefold()
    assert 'applicant reminder' not in folded
    assert 'copy of each variance' in folded
    assert 'issued variance, not the supporting documentation' in folded
    assert 'within 10 days' in reminder['text']
    assert '2026-12-01' in reminder['text']
    assert 'only a safety codes officer registers' in folded
    assert 'not council approval' in folded
    assert 'https://ovp.safetycodes.ab.ca/' in reminder['links']
    assert all('within 10 days' not in gap.message for gap in bulletin_gaps(_case()))


def test_variant_gates_on_a_planted_style_form():
    clean = ingest_bytes(_form([
        f'FIELD | division_c_2_3_1 |  | {DOC}',
        'FIELD | civic_address | Municipal Address | 100 Example Avenue, Edmonton, Alberta',
    ]).encode(), 'clean.txt')[0]
    result = run_variant('A', clean, None)
    by_field = {element.field: element for element in result.elements}
    assert by_field['division_c_2_3_1'].verdict == 'present'
    assert by_field['single_location'].verdict == 'present'
    assert by_field['division_c_2_3_1'].reason.endswith('(IB-2025-11-18).')
    assert 'IB-2026-10-01' in by_field['single_location'].reason
    assert result.invented_values == 0
    assert all('within 10 days' not in (element.export_reason or '') for element in result.elements)

    omitted = ingest_bytes(_form([
        'FIELD | civic_address | Municipal Address | 100 Example Avenue, Edmonton, Alberta',
    ]).encode(), 'ib-doc.txt')[0]
    doc = next(element for element in run_variant('B', omitted, None).elements if element.field == 'division_c_2_3_1')
    assert doc.verdict == 'missing' and doc.problem == 'not_found' and doc.defect_class == 'IB-DOC'
    assert doc.prompt['source'] == 'applicant'
    assert 'will not draft' in doc.prompt['question']
    assert doc.in_export_preflight
    assert 'IB-2025-11-18' in doc.export_reason
    assert 'within 10 days' not in doc.export_reason

    two = ingest_bytes(_form([
        f'FIELD | division_c_2_3_1 |  | {DOC}',
        'FIELD | civic_address | Municipal Address | 100 Example Avenue, Edmonton, Alberta',
        'FIELD | additional_location |  | 200 Example Road, Edmonton, Alberta',
    ]).encode(), 'ib-loc.txt')[0]
    loc = next(element for element in run_variant('A', two, None).elements if element.field == 'single_location')
    assert loc.verdict == 'missing' and loc.problem == 'multiple_locations' and loc.defect_class == 'IB-LOC'
    assert 'will not pick' in loc.prompt['question']
    assert 'IB-2026-10-01' in loc.export_reason
