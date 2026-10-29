"""A requirement profile must stay small enough to save with the case."""
from types import SimpleNamespace

import pytest

from engine.codes import Codes
from engine.identify.decisions import record_decision

from engine.case_view import current_case
from engine.identify.case_input import is_requirement_run, refresh
from engine.identify.compact import compact_identify
from engine.models import Case, Fact, Source
from engine.models_identify import (
    BenchmarkRecord, IdentifyArticle, IdentifyResult, IdentifyTrace, RequirementDiscovery,
    RequirementEvidence, RequirementLink, RequirementRecord,
)


def _result(screen='requirements'):
    evidence = RequirementEvidence(
        id='e1', division='B', provision_id='9.10.15.4.', kind='provision', quote='passage ' * 40,
        citation='NBC(AE) 2023 p2, 9.10.15.4.', source_sha256='abc')
    return IdentifyResult(
        mode='live', source='codedb requirement discovery', label='Candidates', narrowed=False,
        articles=[IdentifyArticle(rank=1, provision='9.10.15.4.', title='Openings', part=9, link='x',
                                  status='candidate', commit_reason='r', quote='passage ' * 40)],
        benchmark=BenchmarkRecord(identified=False),
        scored_at='2026-10-28T00:00:00Z', description_sha256='0',
        trace=IdentifyTrace(config={'screen': screen}, config_hash='0', exhaustive=False,
                            articles_expected=1, articles_scored=1, ranker='requirements', verifier='none'),
        requirements=[RequirementRecord(
            id='NBC-AE:B:9.10.15.4.', provision_id='9.10.15.4.', division='B', title='Openings',
            discoveries=[RequirementDiscovery(kind='lexical', detail='walk ' * 80, evidence=evidence)],
            evidence=[evidence])],
        requirement_evidence=[evidence],
        requirement_links=[RequirementLink(source_requirement='a', target_requirement='b', evidence_ids=['e1'])],
    )


def test_compact_keeps_candidates_and_drops_the_passage_graph():
    slim = compact_identify(_result())
    assert [item.id for item in slim.requirements] == ['NBC-AE:B:9.10.15.4.']
    assert slim.requirements[0].title == 'Openings'
    assert slim.requirements[0].discoveries == []
    assert slim.requirements[0].evidence == []
    assert slim.requirement_evidence == []
    assert slim.requirement_links == []
    assert slim.articles == []
    assert len(slim.model_dump_json()) < len(_result().model_dump_json())


def test_a_compacted_profile_is_still_a_requirement_run():
    assert is_requirement_run(_result('compacted'))
    assert not is_requirement_run(_result('model'))


def test_case_read_returns_the_compact_profile():
    case = Case(facts=[Fact(field='project.description', value='A house', kind='pointed', status='confirmed',
                            source=Source(type='user_text', ref='Your description', quote='A house'))],
                identify=_result())
    read = current_case(case)
    assert read.identify.requirements[0].id == 'NBC-AE:B:9.10.15.4.'
    assert read.identify.requirement_evidence == []
    assert read.identify.articles == []
    assert case.identify.requirement_evidence, 'reading does not change the stored profile'


def test_refresh_stores_the_compact_profile(monkeypatch):
    fat = _result()

    def run(*_args, **_kwargs):
        return SimpleNamespace(result=fat.model_copy(deep=True))

    monkeypatch.setattr('engine.identify.pipeline.run', run)
    monkeypatch.setattr('engine.identify.config.load_config', lambda: SimpleNamespace(screen='requirements'))
    case = Case(facts=[Fact(field='project.description', value='A house', kind='pointed', status='confirmed',
                            source=Source(type='user_text', ref='Your description', quote='A house'))],
                identify=_result('compacted'))
    refresh(case, None, object())
    assert case.identify.requirements[0].id == 'NBC-AE:B:9.10.15.4.'
    assert case.identify.requirement_evidence == []
    assert case.identify.articles == []
    assert case.identify.trace.config.get('screen') == 'requirements'


@pytest.mark.parametrize('decision', ['yes', 'no', 'not_sure'])
def test_departure_decisions_work_after_compaction(decision):
    case = Case(identify=compact_identify(_result()))
    record_decision(case, '9.10.15.4.', decision, Codes())
    assert case.identify.decisions['9.10.15.4.'].decision == decision
    assert case.provisions == (['9.10.15.4.'] if decision == 'yes' else [])
    assert bool(case.section_c) is (decision == 'yes')
    assert case.identify.articles == []
    assert len(case.identify.requirements) == 1


@pytest.mark.parametrize('division,source_status', [('A', 'verified'), ('C', 'verified'), ('B', 'unavailable')])
def test_compact_decisions_reject_unverified_or_non_division_b_entries(division, source_status):
    case = Case(identify=compact_identify(_result()))
    case.identify.requirements[0].division = division
    case.identify.requirements[0].source_status = source_status
    with pytest.raises(KeyError):
        record_decision(case, '9.10.15.4.', 'yes', Codes())
    assert case.provisions == [] and case.identify.decisions == {}
