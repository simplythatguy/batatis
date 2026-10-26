"""WP-22: scope redirects (AC2.1-AC2.3), the early fork (AC1.5) and the question planner (AC1.3).

Sets: the 60 dev cases; `evals_dev/boundary/scope.json` (agent-written before the classifier);
`blind_scope.json` and `blind_fork.json` (written by a subagent that never saw the code). All rules
were tuned after the first blind run, so every number printed here is in-sample; the first blind
run is recorded in the PR.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.intake import service
from engine.intake.fork import HALVES, assess
from engine.intake.notices import NBC_CITED, route_notice
from engine.intake.plan import SCOPE_FIELD, build_plan
from engine.intake.questions import CAP
from engine.intake.scope import REGIMES, classify, redirect_message
from engine.jurisdictions import registry
from engine.models import Case, Jurisdiction
from engine.models_intake import IntakeRecord
from engine.models_identify import ArticleDecision, BenchmarkRecord, IdentifyArticle, IdentifyResult, IdentifyTrace
from engine.store import CaseStore
from engine.tests._network_guard import block_network

ROOT = Path(__file__).resolve().parents[2]
BOUNDARY = ROOT / 'evals_dev' / 'boundary'
CASES = [json.loads(p.read_text()) for p in sorted((ROOT / 'evals_dev' / 'cases').glob('dev-*.json'))]
BANNED = re.compile(r'(?i)\bcompl(?:y|ies)\b|\bapproval\b|\badequate\b|\bwell enough\b|\bis safe\b|\bjev\b')


def _prompts(name: str) -> list[dict]:
    return json.loads((BOUNDARY / name).read_text())['prompts']


def _scope_counts(prompts: list[dict]) -> dict:
    out = {'redirect_ok': 0, 'redirect_total': 0, 'false': 0, 'in_total': 0}
    for p in prompts:
        got = classify(p['text'])
        regime = got.regime.id if got.regime else None
        if p['expect'] == 'redirect':
            out['redirect_total'] += 1
            out['redirect_ok'] += regime == p['regime']
        else:
            out['in_total'] += 1
            out['false'] += regime is not None
    return out


# ---------------------------------------------------------------- scope

def test_scope_on_dev_cases_and_boundary_sets(capsys):
    dev_redirects = [c for c in CASES if c['gold']['intake_action'] == 'redirect']
    in_scope = [c for c in CASES if c['gold']['intake_action'] != 'redirect']
    expected = {'dev-024': 'plumbing', 'dev-025': 'electrical', 'dev-059': 'gas', 'dev-060': 'private_sewage'}
    hits = sum(classify(c['description']).regime is not None and classify(c['description']).regime.id == expected[c['id']]
               for c in dev_redirects)
    false = [c['id'] for c in in_scope if classify(c['description']).status == 'redirect']
    boundary, blind = _scope_counts(_prompts('scope.json')), _scope_counts(_prompts('blind_scope.json'))
    with capsys.disabled():
        print(f'\nscope: dev redirects {hits}/{len(dev_redirects)}, false redirects {len(false)}/{len(in_scope)}; '
              f'boundary {boundary}; blind {blind}')
    assert hits == 4 and len(dev_redirects) == 4
    assert false == [] and len(in_scope) == 56
    assert boundary['redirect_total'] == 24 and boundary['redirect_ok'] >= 20 and boundary['false'] == 0
    assert blind['redirect_ok'] >= 28 and blind['false'] <= 1


def test_redirect_copy_follows_the_scc_deck():
    for regime in REGIMES.values():
        text = redirect_message(regime)
        assert not BANNED.search(text) and 'out of scope' not in text.lower()
        if regime.id in ('electrical', 'gas', 'private_sewage'):
            assert 'no equivalent mandatory Division C alternative-solution framework' in text
            assert 'follow the National Model Codes approach in principle' in text
        else:
            assert 'National Model Code' in text and 'roadmap, not built' in text
        assert regime.route in text


def test_a_house_with_a_bathroom_or_a_gas_fireplace_stays_in_scope():
    for text in ('We are adding a bathroom to our house and the new window is small.',
                 'The gas fireplace wall is 1 m from the property line and has two windows.',
                 'My new house will meet Section 9.36 energy efficiency with thicker batts.'):
        assert classify(text).status == 'in_scope', text


# ---------------------------------------------------------------- fork

def test_fork_on_labelled_cases(capsys):
    rows = [(p['text'], p['label']) for p in _prompts('blind_fork.json')]
    rows += [(c['description'], 'likely') for c in CASES if c['gold']['intake_action'] == 'proceed_conditionally']
    assert len(rows) >= 20
    counts: dict[tuple[str, str], int] = {}
    for text, label in rows:
        got = assess(text).variance_needed
        counts[(label, got)] = counts.get((label, got), 0) + 1
    report = {}
    for label in ('likely', 'not_indicated'):
        tp = counts.get((label, label), 0)
        predicted = sum(v for (_, g), v in counts.items() if g == label)
        gold = sum(v for (l, _), v in counts.items() if l == label)
        report[label] = (tp, predicted, gold)
    with capsys.disabled():
        print(f'\nfork (precision tp/predicted, recall tp/gold): {report}')
    assert report['not_indicated'][0] == report['not_indicated'][1]          # never "not indicated" by mistake
    assert report['likely'][0] / report['likely'][2] >= 0.9
    assert report['not_indicated'][0] / report['not_indicated'][2] >= 0.9


def test_fork_wording_keeps_the_two_halves_distinct():
    ids = [h.id for h in HALVES]
    assert ids == ['variance_request', 'alternative_solution']
    assert 'Safety Codes Act, s.38' in HALVES[0].basis and 'Division C, 2.3.1' in HALVES[1].basis
    for text in ('We want to omit the fire dampers.', 'A standard house built to the Part 9 tables.', 'Hello.'):
        fork = assess(text)
        assert not BANNED.search(fork.explanation)
    likely = assess('We want to omit the fire dampers.')
    assert 'at least the level of performance required by Division B' in likely.explanation
    assert 's.38' in likely.explanation and '2.3.1' in likely.explanation
    assert assess('A standard house built to the Part 9 tables.').variance_needed == 'not_indicated'


def test_process_citations_resolve_in_codedb():
    from engine.codes import Codes
    codes = Codes()
    assert codes.provision('2.3.1.1.', 'C') and codes.provision('1.2.1.1.', 'A')
    for division, provision in NBC_CITED:
        assert codes.provision(provision, division), provision


# ---------------------------------------------------------------- planner

def _case(text: str, **facts) -> Case:
    case = Case()
    service.apply(case, text, service.run(text, []))
    return case


def test_at_most_five_questions_each_with_why_and_unblocks():
    for c in CASES:
        plan = _case(c['description']).intake.plan
        assert len(plan.questions) <= CAP
        for q in plan.questions:
            assert q.why and q.unblocks and q.id == 'intake.' + q.field
            assert not BANNED.search(q.text + q.why)
        if c['gold']['intake_action'] == 'redirect':
            assert plan.next == 'redirect' and plan.questions == []


def test_asks_or_abstains_on_stripped_and_ask_cases(capsys):
    """AC1.3: a description missing its deciding facts gets a critical question or an unknown fork."""
    asked = total = 0
    for c in CASES:
        if c['gold']['intake_action'] == 'redirect':
            continue
        sentences = re.split(r'(?<=[.?!])\s+', c['description'])
        variants = [' '.join(s for s in sentences if not re.search(r'\d|storey|area', s, re.I)) or 'We need a variance.']
        if c['gold']['intake_action'] == 'ask':
            variants.append(c['description'])
        for text in variants:
            plan = _case(text).intake.plan
            total += 1
            asked += any(q.priority == 'critical' for q in plan.questions) or plan.fork.variance_needed == 'unknown'
    with capsys.disabled():
        print(f'\nasks or abstains: {asked}/{total}')
    assert asked / total >= 0.9


def test_conflicts_are_asked_first():
    plan = _case('The house is two storeys. Actually it is three storeys. We want to omit the housewrap.').intake.plan
    assert plan.questions[0].kind == 'conflict' and plan.questions[0].field == 'storeys'
    assert '"two storeys"' in plan.questions[0].text


def test_an_answered_conflict_is_not_asked_again():
    case = _case('The house is two storeys. Actually it is three storeys. We want to omit the housewrap.')
    qid = case.intake.plan.questions[0].id
    service.answer(case, [{'question_id': qid, 'answer': '3'}])
    assert 'storeys' not in {q.field for q in case.intake.plan.questions}
    assert [(f.value, f.status) for f in case.facts if f.field == 'storeys'] == [(3, 'confirmed')]


def _identify(case: Case, provisions: list[str], decisions: dict[str, str] | None = None) -> None:
    articles = [IdentifyArticle(rank=i + 1, provision=p, title='t', part=int(p.split('.')[0]), link='x', status='candidate',
                                commit_reason='r') for i, p in enumerate(provisions)]
    case.identify = IdentifyResult(
        mode='fake', source='fake', label='fake', narrowed=True, articles=articles, benchmark=BenchmarkRecord(identified=False),
        scored_at='2026-10-21', description_sha256='0', trace=IdentifyTrace(
            config={}, config_hash='0', exhaustive=True, articles_expected=1, articles_scored=1, ranker='fake', verifier='none'),
        decisions={k: ArticleDecision(decision=v, decided_at='2026-10-21') for k, v in (decisions or {}).items()})


def test_ranking_follows_what_splits_the_candidates():
    case = _case('We want to leave out the protection on the wall near the property line.')
    _identify(case, ['9.10.15.4.', '9.10.15.5.', '3.2.3.1.', '9.27.2.1.'])
    service.refresh(case)
    top = case.intake.plan.questions[0]
    assert top.field == 'limiting_distance_m' and set(top.splits) == {'9.10.15.4.', '9.10.15.5.', '3.2.3.1.'}
    _identify(case, ['9.10.15.4.'], {'9.10.15.4.': 'no'})
    service.refresh(case)
    assert case.intake.plan.candidates_seen == 0
    assert assess(case.facts[0].value, decisions={'9.10.15.4.': 'no'}).variance_needed in ('likely', 'not_indicated')


def test_answers_fill_only_their_own_question_and_not_sure_never_blocks():
    case = _case('Our client wants a single staircase in their new building instead of two.')
    asked = {q.field: q.id for q in case.intake.plan.questions}
    assert 'storeys' in asked and 'occupancy' in asked
    with pytest.raises(service.AnswerRejected):
        service.answer(case, [{'question_id': 'intake.owner_name_not_asked', 'answer': 'x'}])
    with pytest.raises(service.AnswerRejected):
        service.answer(case, [{'question_id': asked['storeys'], 'field': 'project.description', 'answer': '3'}])
    with pytest.raises(service.AnswerRejected):
        service.answer(case, [{'question_id': asked['storeys'], 'answer': 'tall'}])
    before = len(case.facts)
    created = service.answer(case, [{'question_id': asked['storeys'], 'answer': 'three'},
                                    {'question_id': asked['occupancy'], 'answer': 'not sure'}])
    assert [(f.field, f.value, f.status) for f in created] == [('storeys', 3, 'confirmed')]
    assert len(case.facts) == before + 1
    fields = [q.field for q in case.intake.plan.questions]
    assert 'storeys' not in fields and 'occupancy' not in fields
    assert asked['occupancy'] in case.intake.plan.not_sure
    assert not [f for f in case.facts if f.field == 'occupancy']           # nothing that could block export


def test_an_answered_choice_can_be_changed_after_the_plan_moves_on(http):
    case_id = http.post('/cases', json={}).json()['id']
    intake = http.post(f'/cases/{case_id}/intake', json={
        'text': 'We manufacture an insulated panel for house walls.', 'role': 'manufacturer', 'model': False,
    }).json()
    scope = next(q for q in intake['record']['plan']['questions'] if q['field'] == 'product_scope')
    first = http.post(f'/cases/{case_id}/intake/answers', json={
        'answers': [{'question_id': scope['id'], 'answer': 'site'}], 'expected_version': intake['case_version'],
    })
    assert first.status_code == 200
    saved = first.json()
    assert scope['id'] not in [q['id'] for q in saved['record']['plan']['questions']]

    # Read the persisted record before going Back and changing the saved choice.
    reloaded = http.get(f'/cases/{case_id}/intake').json()
    edited = http.post(f'/cases/{case_id}/intake/answers', json={
        'answers': [{'question_id': scope['id'], 'answer': 'product_acceptance'}],
        'expected_version': reloaded['case_version'],
    })
    assert edited.status_code == 200, edited.text
    latest = http.get(f'/cases/{case_id}').json()
    assert [f for f in latest['facts'] if f['field'] == 'product_scope'][-1]['value'] == 'product_acceptance'
    assert edited.json()['case_version'] == saved['case_version'] + 1

    # An issued question remains bound to its field and to the acknowledged case version.
    stale = http.post(f'/cases/{case_id}/intake/answers', json={
        'answers': [{'question_id': scope['id'], 'answer': 'site'}], 'expected_version': saved['case_version'],
    })
    assert stale.status_code == 409
    wrong_field = http.post(f'/cases/{case_id}/intake/answers', json={
        'answers': [{'question_id': scope['id'], 'field': 'project.description', 'answer': 'site'}],
        'expected_version': edited.json()['case_version'],
    })
    assert wrong_field.status_code == 422
    unasked = http.post(f'/cases/{case_id}/intake/answers', json={
        'answers': [{'question_id': 'intake.owner_name_not_asked', 'answer': 'x'}],
        'expected_version': edited.json()['case_version'],
    })
    assert unasked.status_code == 422
    assert http.get(f'/cases/{case_id}').json() == latest


def test_product_prose_asks_the_route_without_a_role_and_keeps_municipal_scope_separate():
    from engine.models import Fact, Source
    case = _case('We want to market this insulated wall panel product for buildings across Alberta.')
    case.facts.append(Fact(field='scope', value='jurisdiction', kind='pointed', status='confirmed',
                           source=Source(type='user_text', ref='Your answer', quote='municipality-wide variance')))
    service.refresh(case)
    question = next(q for q in case.intake.plan.questions if q.field == 'product_scope')
    assert question.text == 'One building, or across Alberta?'
    assert not [f for f in case.facts if f.field == 'applicant_role']
    service.answer(case, [{'question_id': question.id, 'answer': 'product_acceptance'}])
    assert [f for f in case.facts if f.field == 'scope'][-1].value == 'jurisdiction'
    assert [f for f in case.facts if f.field == 'product_scope'][-1].value == 'product_acceptance'
    assert case.intake.plan.route_notice is not None
    assert 'CCMC' in case.intake.plan.route_notice.summary
    reloaded = Case.model_validate(case.model_dump())
    service.refresh(reloaded)
    assert question.id not in [q.id for q in reloaded.intake.plan.questions]
    service.answer(reloaded, [{'question_id': question.id, 'answer': 'not sure'}])
    assert question.id in reloaded.intake.plan.not_sure
    assert [f for f in reloaded.facts if f.field == 'product_scope'][-1].value is None
    assert [f for f in reloaded.facts if f.field == 'scope'][-1].value == 'jurisdiction'


def test_journey_deferral_and_route_use_the_existing_case_fact_route(http):
    case_id = http.post('/cases', json={}).json()['id']
    answer = dict(key='field-owner', field='owner', question='Owner', stage='paperwork', answerer='you',
                  value='later', required=True)
    for field, value in [('journey.answer.field-owner', json.dumps(answer)), ('journey.route', 'standard')]:
        result = http.post(f'/cases/{case_id}/facts', json={
            'field': field, 'value': value, 'kind': 'pointed', 'status': 'confirmed',
            'source': {'type': 'user_text', 'ref': 'Typed in Section A', 'quote': value},
        })
        assert result.status_code == 200, result.text
    saved = http.get(f'/cases/{case_id}').json()
    values = {f['field']: f['value'] for f in saved['facts']}
    assert json.loads(values['journey.answer.field-owner']) == answer
    assert values['journey.route'] == 'standard'
    assert 'owner' not in values, 'Later must never satisfy the underlying required field'


def test_applicant_roles_keep_the_existing_none_value():
    from engine.account_models import User
    for role in (None, 'owner', 'designer', 'engineer', 'contractor', 'manufacturer', 'other', 'homebuilder', 'builder'):
        assert User(email='journey@example.test', name='Synthetic applicant', applicant_type=role).applicant_type == role


def test_a_saved_not_sure_can_be_replaced_with_a_real_answer():
    case = _case('Our client wants a single staircase in their new building instead of two.')
    qid = next(q.id for q in case.intake.plan.questions if q.field == 'occupancy')
    service.answer(case, [{'question_id': qid, 'answer': 'not sure'}])
    service.answer(case, [{'question_id': qid, 'answer': 'single_family'}])
    assert qid not in case.intake.plan.not_sure
    assert [f for f in case.facts if f.field == 'occupancy'][-1].value == 'single_family'


def test_an_issued_question_survives_replanning_and_batch_validation_is_atomic():
    case = _case('Our client wants a single staircase in their new building instead of two.')
    question = next(q for q in case.intake.plan.questions if q.field == 'storeys')
    from engine.models import Fact, Source
    case.facts.append(Fact(field='storeys', value=2, kind='pointed', status='unconfirmed',
                           source=Source(type='user_text', ref='intake:description', quote='two storeys')))
    service.refresh(case)
    assert question.id not in [q.id for q in case.intake.plan.questions]
    assert question.id in [q.id for q in case.intake.plan.asked]
    before = case.model_dump()
    with pytest.raises(service.AnswerRejected):
        service.answer(case, [{'question_id': question.id, 'answer': '3'},
                              {'question_id': 'intake.never_asked', 'answer': 'x'}])
    assert case.model_dump() == before
    service.answer(case, [{'question_id': question.id, 'answer': '3'}])
    assert [f for f in case.facts if f.field == 'storeys'][-1].value == 3
    service.refresh(case)
    assert len([q for q in case.intake.plan.asked if q.id == question.id]) == 1


def test_legacy_answers_stay_editable_and_uncertainty_withdraws_the_old_value():
    case = _case('Our client wants a single staircase in their new building instead of two.')
    qid = next(q.id for q in case.intake.plan.questions if q.field == 'occupancy')
    service.answer(case, [{'question_id': qid, 'answer': 'single_family'}])
    case.intake.plan.asked = []  # persisted before issued-question history was added
    service.answer(case, [{'question_id': qid, 'answer': 'not sure'}])
    assert [f for f in case.facts if f.field == 'occupancy'][-1].value is None
    assert qid in case.intake.plan.not_sure
    case.intake.plan.asked = []
    service.answer(case, [{'question_id': qid, 'answer': 'single_family'}])
    assert qid not in case.intake.plan.not_sure
    assert [f for f in case.facts if f.field == 'occupancy'][-1].value == 'single_family'


@pytest.mark.parametrize('answer', ['no', 'not sure'])
def test_legacy_choice_history_is_hydrated_on_read_and_replan(tmp_path, answer):
    case = _case('We want to omit the fire separation in our new house.')
    issued = next(q for q in case.intake.plan.questions if q.field == 'sprinklered')
    service.answer(case, [{'question_id': issued.id, 'answer': answer}])
    record = case.intake.model_dump()
    record['plan'].pop('asked')
    case.intake = IntakeRecord.model_validate(record)
    assert case.intake.plan.asked == [] and issued.id not in [q.id for q in case.intake.plan.questions]
    store = CaseStore(tmp_path / 'cases.sqlite')
    saved = store.put(case)
    with TestClient(create_app(store=store)) as client:
        loaded = client.get(f'/cases/{saved.id}/intake')
        assert loaded.status_code == 200
        asked = [q for q in loaded.json()['record']['plan']['asked'] if q['id'] == issued.id]
        assert len(asked) == 1
        assert (asked[0]['field'], asked[0]['text'], asked[0]['why']) == (issued.field, issued.text, issued.why)
        assert store.get(saved.id).model_dump() == saved.model_dump(), 'reading history cannot write or advance the case'
        replanned = client.post(f'/cases/{saved.id}/intake/plan', json={'expected_version': saved.version})
        assert replanned.status_code == 200
        assert [q['id'] for q in replanned.json()['record']['plan']['asked']].count(issued.id) == 1
        edited = client.post(f'/cases/{saved.id}/intake/answers', json={
            'answers': [{'question_id': issued.id, 'answer': 'yes'}],
            'expected_version': replanned.json()['case_version'],
        })
        assert edited.status_code == 200
        assert issued.id not in edited.json()['record']['plan']['not_sure']
        assert [f for f in store.get(saved.id).facts if f.field == issued.field][-1].value == 'yes'


def test_reopened_legacy_choice_has_one_editable_deck_card(tmp_path):
    node = shutil.which('node')
    if node is None:
        pytest.skip('node is required to exercise the real openedCase -> buildDeck projection')
    case = _case('We want to omit the fire separation in our new house.')
    issued = next(q for q in case.intake.plan.questions if q.field == 'sprinklered')
    service.answer(case, [{'question_id': issued.id, 'answer': 'no'}])
    serialized = case.model_dump()
    serialized['intake']['plan'].pop('asked')
    store = CaseStore(tmp_path / 'cases.sqlite')
    saved = store.put(Case.model_validate(serialized))
    with TestClient(create_app(store=store)) as client:
        intake = client.get(f'/cases/{saved.id}/intake').json()
    payload = tmp_path / 'reopened.json'
    payload.write_text(json.dumps({'saved': saved.model_dump(mode='json'), 'intake': intake}))
    script = '''
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { openedCase } from './src/calm/openCase.ts';
import { buildDeck, choicesFor } from './src/calm/deck.ts';
const payload = JSON.parse(readFileSync(process.argv[1], 'utf8'));
const c = openedCase(payload.saved, 'homebuilder', { intake: payload.intake, identify: null });
const cards = buildDeck(c, [], { includeDone: true }).filter(c => c.ref === 'intake.sprinklered');
assert.equal(cards.length, 1, 'the older saved choice must have one editable card');
assert.equal(cards[0].done, true);
assert.deepEqual(choicesFor(cards[0]).map(c => c.value), ['yes', 'no', 'partial', 'not_sure']);
console.log('legacy reopened choice: one editable card, all three real choices');
'''
    result = subprocess.run([node, '--experimental-strip-types', '--no-warnings', '--import',
                             './scripts/register-ts.mjs', '--input-type=module', '-e', script, str(payload)],
                            cwd=ROOT / 'web', capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_legacy_history_requires_own_case_answer_or_remembered_uncertainty():
    from engine.models import Fact, Source
    case = _case('We want to omit the fire separation in our new house.')
    case.facts.extend([
        Fact(field='part4_design', value=False, kind='pointed', status='confirmed',
             source=Source(type='user_text', ref='intake:description', quote='not a Part 4 design')),
        Fact(field='scope', value='site', kind='pointed', status='unconfirmed',
             source=Source(type='user_text', ref='intake answer', quote='site')),
        Fact(field='unissued_probe', value='yes', kind='pointed', status='confirmed',
             source=Source(type='user_text', ref='intake answer', quote='yes')),
    ])
    case.intake.plan.not_sure.extend(['intake.assembly.description', 'intake.unissued_probe'])
    service.refresh(case)
    asked = {q.id for q in case.intake.plan.asked}
    assert 'intake.assembly.description' in asked
    assert not {'intake.part4_design', 'intake.scope', 'intake.unissued_probe'} & asked
    for qid in ('intake.part4_design', 'intake.scope', 'intake.unissued_probe'):
        before = case.model_dump()
        with pytest.raises(service.AnswerRejected):
            service.answer(case, [{'question_id': qid, 'answer': 'yes'}])
        assert case.model_dump() == before


def test_issued_history_does_not_bypass_a_scope_redirect():
    case = _case('Our client wants a single staircase in their new building instead of two.')
    qid = next(q.id for q in case.intake.plan.questions if q.field == 'storeys')
    text = 'Can we skip AFCI breakers on the bedroom circuits?'
    service.apply(case, text, service.run(text, []))
    assert case.intake.plan.scope.status == 'redirect'
    before = case.model_dump()
    with pytest.raises(service.AnswerRejected):
        service.answer(case, [{'question_id': qid, 'answer': '3'}])
    assert case.model_dump() == before


# ---------------------------------------------------------------- redirect on the case (AC2.2, AC2.3)

def test_redirect_is_a_computed_fact_with_the_cue_and_blocks_export_until_overridden():
    text = 'Plumbing contractor. We want an air admittance valve instead of a vent through the roof.'
    case = _case(text)
    fact = next(f for f in case.facts if f.field == SCOPE_FIELD)
    assert fact.kind == 'computed' and fact.value == 'plumbing' and fact.source.quote in text and fact.inputs
    assert fact.id in case.export_blockers()
    plan = case.intake.plan
    assert plan.next == 'redirect' and plan.scope.regime.id == 'plumbing' and plan.scope.cue == fact.source.quote
    assert not case.section_c and not case.provisions
    service.override_scope(case, True)
    assert fact.id not in case.export_blockers() and fact.id not in {p.fact_id for p in case.intake.pointers}
    assert not [f for f in case.facts if f.field == SCOPE_FIELD and f.status != 'confirmed']
    plan = case.intake.plan
    assert plan.scope.status == 'overridden' and plan.next != 'redirect' and plan.questions
    latest = [f for f in case.facts if f.field == SCOPE_FIELD][-1]       # export reads the latest revision
    assert latest.status == 'confirmed' and latest.source.type == 'user_click'
    service.apply(case, text, service.run(text, []))                       # a re-run keeps the override
    assert case.intake.plan.scope.status == 'overridden'
    service.override_scope(case, False)
    assert case.intake.plan.scope.status == 'redirect'


# ---------------------------------------------------------------- notices

def test_pre_application_comes_from_the_pack_or_stays_generic():
    generic = build_plan(Case()).pre_application
    assert [s.id for s in generic.steps] == ['meet_authority', 'emergency_services']
    assert all(s.origin == 'generic' for s in generic.steps) and generic.jurisdiction_id is None
    reg = registry()
    pack = next(p for p in reg.packs.values() if not p.fallback)
    case = Case(jurisdiction=Jurisdiction(id=pack.id, name=pack.name))
    note = build_plan(case).pre_application
    assert note.jurisdiction_id == pack.id and note.resolved_by == 'case'
    assert note.steps[0].origin == 'pack' and pack.authority.name in note.steps[0].text
    assert any(s.url for s in note.steps[0].sources)
    from_words = _case(f'We are building a two-storey house in {pack.name}.')
    assert from_words.intake.plan.pre_application.resolved_by in ('description', None)


def test_manufacturer_route_notice():
    assert route_notice('contractor', None) is None
    notice = route_notice('manufacturer', None)
    assert notice and 'Safety Codes Act, s.38' in notice.summary and 'Division C, 2.3.1' in notice.summary
    assert 'at least the level of performance required by Division B' in notice.summary
    assert not BANNED.search(notice.summary)
    assert route_notice(None, 'jurisdiction') is not None
    assert _case('We manufacture an insulated panel for houses across Alberta.').intake.plan.route_notice is not None


# ---------------------------------------------------------------- routes

@pytest.fixture
def http(tmp_path):
    return TestClient(create_app(CaseStore(tmp_path / 'cases.sqlite')))


def test_plan_routes_round_trip_offline(http, monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError('network call attempted')
    block_network(monkeypatch, message='network call attempted')
    monkeypatch.setattr('httpx.Client.send', blocked)
    case_id = http.post('/cases', json={}).json()['id']
    body = http.post(f'/cases/{case_id}/intake', json={'text': 'Our client wants a single staircase instead of two.'}).json()
    plan = body['record']['plan']
    assert plan['next'] == 'questions' and len(plan['questions']) <= 5
    storeys = next(q for q in plan['questions'] if q['field'] == 'storeys')
    stale = http.post(f'/cases/{case_id}/intake/answers',
                      json={'answers': [{'question_id': storeys['id'], 'answer': '2'}], 'expected_version': 1})
    assert stale.status_code == 409
    wrong = http.post(f'/cases/{case_id}/intake/answers', json={'answers': [{'question_id': 'intake.nope', 'answer': '2'}]})
    assert wrong.status_code == 422
    done = http.post(f'/cases/{case_id}/intake/answers', json={
        'answers': [{'question_id': storeys['id'], 'answer': '2'}], 'expected_version': body['case_version']})
    assert done.status_code == 200
    assert 'storeys' not in [q['field'] for q in done.json()['record']['plan']['questions']]
    assert http.post(f'/cases/{case_id}/intake/plan', json={}).status_code == 200
    redirect_id = http.post('/cases', json={}).json()['id']
    red = http.post(f'/cases/{redirect_id}/intake', json={'text': 'Can we skip AFCI breakers on the bedroom circuits?'}).json()
    assert red['record']['plan']['next'] == 'redirect'
    over = http.post(f'/cases/{redirect_id}/intake/scope', json={'building_code': True}).json()
    assert over['record']['plan']['scope']['status'] == 'overridden'
    for payload in (body, done.json(), red, over):
        visible = {k: v for k, v in payload.items() if k != 'meta'}     # meta.notice is the shared privacy notice
        assert not re.search(r'(?i)\bjev\b', json.dumps(visible))


def test_ordinary_requests_are_not_read_as_departures():
    for text in ('We want a deck on the back of the house.', 'We propose a two-storey house on our lot.'):
        assert assess(text).variance_needed == 'unknown', text


def test_a_stale_version_is_refused_before_any_model_call(tmp_path):
    calls = []

    def factory(ip):
        def transport(system, user, schema):
            calls.append(1)
            return {'facts': []}, {}
        return transport, 'fake'
    from engine.routes_intake import create_router
    from fastapi import FastAPI
    store = CaseStore(tmp_path / 'cases.sqlite')
    app = FastAPI()
    app.include_router(create_router(lambda: store, lambda: None, transport_factory=factory))
    case = store.put(Case())
    client = TestClient(app)
    assert client.post(f'/cases/{case.id}/intake', json={'text': 'We want to omit the dampers.',
                                                          'expected_version': case.version + 5}).status_code == 409
    assert calls == []


def test_checking_the_scope_again_never_blocks_export_by_itself():
    case = _case('We want a single exit stair in our new four-storey office.')
    blockers = set(case.export_blockers())
    service.override_scope(case, True)
    service.override_scope(case, False)
    assert set(case.export_blockers()) == blockers and case.intake.plan.scope.status == 'in_scope'
    red = _case('Can we skip AFCI breakers on the bedroom circuits?')
    service.override_scope(red, True)
    service.override_scope(red, False)
    again = [f for f in red.facts if f.field == SCOPE_FIELD][-1]
    assert again.kind == 'computed' and again.id in {p.fact_id for p in red.intake.pointers}
