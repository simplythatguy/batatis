"""Section C pairs come only from codedb attribution_status. None stays empty."""
from contextlib import closing

import pytest

from codedb import store
from codedb.tests.mini_db import build
from engine.codes import Codes
from engine.completeness import check_completeness
from engine.evidence_gaps import group_evidence_gaps
from engine.models import Case, Jurisdiction
from engine.professional import ProfessionalResult
from engine.section_c import NOT_ATTRIBUTED, section_c_rows
from engine.section_d import section_d_plan
from engine.tests.case_builder_fixtures import fact


@pytest.fixture
def codes(tmp_path):
    path = tmp_path / 'mini.sqlite'
    build(path)
    return Codes(path)


@pytest.mark.parametrize('pid,root', [
    ('9.8.8.1.(5)', '9.8.8.1.(4)'),
    ('3.1.9.4.(1)', None),
    ('3.1.9.4.(2)', None),
    ('3.1.9.4.(4)', None),
    ('3.1.9.1.(4)', None),
    ('9.25.5.1.(1)', '9.25.5.1.(2)'),
])
def test_sentence_without_an_article_row_stays_a_gap(codes, pid, root):
    [row] = section_c_rows([pid], codes)
    assert row.pairs == []
    assert row.attribution_status == 'no row in the attribution table'
    assert row.attribution == NOT_ATTRIBUTED
    assert row.attribution_label == 'lookup not available'
    assert row.attributed_via is None
    assert row.related_root == root
    assert 'compli' not in row.citation.casefold()


def test_3_1_8_1_1_has_no_sentence_level_pairs(codes):
    """Status clause_level keeps pairs off the sentence and shows the clause that has them."""
    rows = section_c_rows(['3.1.8.1.(1)'], codes)
    sentence = next(row for row in rows if row.provision_id == '3.1.8.1.(1)')
    assert sentence.pairs == []
    assert sentence.attributed_via is None
    assert sentence.attribution is None
    assert sentence.attribution_label == 'attributed at clause level: (a)'
    clause = next(row for row in rows if row.provision_id == '3.1.8.1.(1)(a)')
    assert clause.attribution_status == 'direct'
    assert clause.attributed_via is None
    assert sorted((pair.function, pair.objective) for pair in clause.pairs) == [('F03', 'OP1.2'), ('F03', 'OS1.2')]


def test_clause_without_rows_does_not_take_a_sibling_clause(codes):
    [row] = section_c_rows(['3.1.8.1.(1)(b)'], codes)
    assert row.pairs == []
    assert row.attributed_via is None
    assert row.attribution_status == 'no row in the attribution table'
    assert row.attribution == NOT_ATTRIBUTED


def test_clause_inherits_its_sentence_not_a_made_up_pair(codes):
    [row] = section_c_rows(['3.1.4.2.(1)(a)'], codes)
    assert row.attribution_status == 'inherited from parent'
    assert row.attributed_via == '3.1.4.2.(1)'
    assert [(pair.function, pair.objective) for pair in row.pairs] == [('F02', 'OS1.2')]


def test_sentence_falls_back_to_an_article_row(codes):
    """8.1.1.1.(1) is attribution_status none. The article row is not copied onto it."""
    rec = codes.provision('8.1.1.1.(1)', 'B')
    assert rec['attribution_status']['status'] == 'none'
    [row] = section_c_rows(['8.1.1.1.(1)'], codes)
    assert row.pairs == []
    assert row.attributed_via is None
    assert row.attribution == NOT_ATTRIBUTED
    assert row.attribution_label == 'lookup not available'
    assert row.attribution_status == 'no row in the attribution table'


def test_not_determined_sentence_states_that_and_does_not_copy_the_article(codes):
    """9.23.17.3.(1) in the fixture: status none / not_determined, intent only, article pair present."""
    [row] = section_c_rows(['9.23.17.3.(1)'], codes)
    assert row.attribution == NOT_ATTRIBUTED
    assert row.attribution_label == 'lookup not available'
    assert row.attribution_status == 'no row in the attribution table'
    assert row.pairs == [] and row.attributed_via is None
    assert row.intents and row.intents[0].intents == ['SYNTHETIC intent for an unattributed sentence']
    assert row.intents[0].objective is None
    plan = section_d_plan(Case(provisions=['9.23.17.3.(1)']), codes)
    assert plan.items and all(item.objective is None and item.function is None for item in plan.items)
    [gap] = group_evidence_gaps(plan.items)
    assert gap.pairs == []
    assert gap.evidence_types == list(plan.items[0].recommended_types)
    text = gap.fix_hint
    assert 'lookup not available' in text
    assert 'F99' not in text and 'OS9.9' not in text
    assert "manufacturer's literature" in text


CONTROL_PAIRS = (
    ('F03', 'OS1.2', 323, 'Table 3.10.1.1.'),
    ('F04', 'OS1.3', 323, 'Table 3.10.1.1.'),
    ('F03', 'OP1.2', 323, 'Table 3.10.1.1.'),
    ('F04', 'OP1.3', 323, 'Table 3.10.1.1.'),
)


@pytest.mark.parametrize('pid', ['3.1.9.1.(4)', '3.1.9.4.(4)', '9.23.17.3.(1)'])
def test_codedb_status_none_is_not_attributed(codes, pid):
    """These three sentences are attribution_status none in the codedb fixture."""
    rec = codes.provision(pid, 'B')
    assert rec['attribution_status']['status'] == 'none'
    assert rec['attributions'] == []
    [row] = section_c_rows([pid], codes)
    assert row.provision_id == pid
    assert row.pairs == []
    assert row.attribution == NOT_ATTRIBUTED
    assert row.attribution_label == 'lookup not available'
    assert row.attribution_status == 'no row in the attribution table'
    assert row.attributed_via is None


def test_3_1_9_1_1_is_the_attributed_control(codes):
    """Sentence (1) keeps Table 3.10.1.1. p.323. Those pairs are not copied onto (4)."""
    rec = codes.provision('3.1.9.1.(1)', 'B')
    assert rec['attribution_status']['status'] == 'direct'
    assert [(a['bracket'], a['pdf_page'], a['table_id']) for a in rec['attributions']] == [
        (f'[{function}-{objective}]', page, table) for function, objective, page, table in CONTROL_PAIRS]
    [row] = section_c_rows(['3.1.9.1.(1)'], codes)
    assert row.attribution is None
    assert row.attribution_status == 'direct'
    assert [(pair.function, pair.objective, pair.pdf_page, pair.table) for pair in row.pairs] == list(CONTROL_PAIRS)
    [blank] = section_c_rows(['3.1.9.1.(4)'], codes)
    assert blank.pairs == []
    assert blank.attribution == NOT_ATTRIBUTED
    assert blank.attribution_label == 'lookup not available'


def test_cited_3_1_9_4_4_is_an_explicit_section_c_row(codes):
    """Sentence (4) has no table row and does not inherit sibling (3). It is still in Section C."""
    [row] = section_c_rows(['3.1.9.4.(4)'], codes)
    assert row.provision_id == '3.1.9.4.(4)'
    assert row.pairs == []
    assert row.attribution == NOT_ATTRIBUTED
    assert row.attribution_label == 'lookup not available'
    assert row.attribution_status == 'no row in the attribution table'
    assert row.attributed_via is None
    rows = {item.provision_id: item for item in section_c_rows(['3.1.9.4.'], codes)}
    assert '3.1.9.4.(4)' in rows
    assert rows['3.1.9.4.(4)'].attribution == NOT_ATTRIBUTED
    assert rows['3.1.9.4.(4)'].pairs == []
    assert [(pair.function, pair.objective) for pair in rows['3.1.9.4.(3)'].pairs] == [('F03', 'OS1.2')]
    assert rows['3.1.9.4.(3)'].attribution is None


def test_adding_3_1_9_4_7_names_each_new_blocking_gap(codes, monkeypatch):
    """A new provision may add a blocking gap. The new gap names that provision and the evidence."""
    monkeypatch.setattr('engine.completeness.validate_text', lambda *args, **kwargs: {'errors': []})
    monkeypatch.setattr('engine.completeness.process_fields', lambda case, codes: [])
    monkeypatch.setattr(
        'engine.completeness.professional_involvement',
        lambda case, codes: ProfessionalResult(required='no', general_required='no', reasons=[], questions=[]))

    def blocking(provisions):
        case = Case(
            provisions=provisions,
            section_c=section_c_rows(provisions, codes),
            jurisdiction=Jurisdiction(id='alberta-other', name='Synthetic AHJ'),
            facts=[fact(name, 'synthetic') for name in (
                'owner_name', 'application_date', 'civic_address', 'legal_description',
                'representative', 'mailing_address', 'alternative_description', 'scope')])
        return [gap for gap in check_completeness(case, codes) if gap.severity == 'blocking']

    before = blocking(['3.1.9.4.(4)'])
    after = blocking(['3.1.9.4.(4)', '3.1.9.4.(7)'])
    known = {gap.id for gap in before}
    new = [gap for gap in after if gap.id not in known]
    assert len(after) - len(before) == len(new) > 0
    for gap in new:
        assert gap.provision_id == '3.1.9.4.(7)'
        assert '3.1.9.4.(7)' in gap.message
        assert 'F03/OS1.2' in gap.message
        assert gap.evidence_types
        for kind in gap.evidence_types:
            assert kind in gap.message


def test_every_none_status_returns_empty_pairs(codes):
    """Every attribution_status none id in the mini database has no pairs and no attributed_via."""
    with closing(store.connect(codes.db_path)) as con:
        none_ids = [row['provision_id'] for row in con.execute(
            "SELECT provision_id FROM attribution_status WHERE status='none' ORDER BY provision_id")]
    assert none_ids
    for pid in none_ids:
        match = [row for row in section_c_rows([pid], codes) if row.provision_id == pid]
        assert len(match) == 1
        row = match[0]
        assert row.pairs == []
        assert row.attributed_via is None
        assert row.attribution == NOT_ATTRIBUTED
        assert row.attribution_label == 'lookup not available'


def test_division_c_sentence_is_not_a_section_c_row(codes):
    with pytest.raises(KeyError):
        section_c_rows(['2.3.1.1.(3)'], codes)
