"""The memo and the G1 report are pure functions of the rows."""
import pytest

from evals_dev.identify_bench import analysis, fakes, memo
from evals_dev.identify_bench.rows import RowStore
from evals_dev.identify_bench.runner import run_arms

CHAIN = ['R0-bm25', 'R1-searchrank-v3', 'R2-precedent-lofo', 'R6-bm25-jev-rerank60', 'F1-rrf-R5-R1-R2', 'V15f-R5', 'V5c-R5']


@pytest.fixture
def world(tmp_path):
    ctx, _ = fakes.make_ctx(tmp_path)
    cases = fakes.make_cases(8, 'public53', 'selection') + fakes.make_cases(4, 'dev', 'validation')
    arms = fakes.fake_arms()
    run_arms(arms, CHAIN, cases, ctx, repeats=2, git_sha='abc123', codedb_sha256='d' * 64)
    run_arms(arms, ['V15f-R5', 'R6-bm25-jev-rerank60'], cases[:4], ctx, repeats=1, profile='interactive', git_sha='abc123')
    return ctx, arms, cases


def analyse(world):
    ctx, arms, cases = world
    return analysis.analyse(ctx.store, arms=arms, cases=cases, arts=ctx.arts, pipelines=tuple(arms))


def test_the_decision_memo_has_every_section_and_names_a_winner(world):
    an = analyse(world)
    text = memo.render_decision(an, ledger_openai=world[0].openai.ledger.summary(), folds_sha='f' * 64)
    for heading in ['# Code identification: decision memo', '## Claim', '## Verdict', '## Decision rule applied',
                    '## Pareto table', '## Success rate by Part group', '## Gate G1', '## Development folds',
                    '## Commit policy, explored', '## Integrity and reliability', '## Cost and latency', '## Validity checklist',
                    '## What WP-13', '## Provenance']:
        assert heading in text, heading
    assert an.decision.winner and f'**Chosen pipeline: `{an.decision.winner}`.**' in text
    assert 'abc123' in text and 'ffffffffffffffff' in text and 'gpt-6-luna' in text


def test_the_same_rows_give_the_same_bytes(world):
    a = memo.render_decision(analyse(world), folds_sha='f' * 64)
    b = memo.render_decision(analyse(world), folds_sha='f' * 64)
    assert a == b


def test_pipelines_without_rows_are_left_out_not_invented(world):
    an = analyse(world)
    assert 'A9-bm25-luna-rerank60' not in an.selection and 'V5f-F1-ool' not in an.selection
    assert set(an.selection) >= {'R0-bm25', 'V15f-R5', 'F1-rrf-R5-R1-R2'}


def test_latency_comes_only_from_interactive_rows(world):
    an = analyse(world)
    assert set(an.latency) >= {'V15f-R5', 'R6-bm25-jev-rerank60'} and 'F1-rrf-R5-R1-R2' not in an.latency
    assert an.latency['V15f-R5']['n'] == 4 and an.latency['V15f-R5']['p95_ms'] > 0


def test_g1_section_reports_rerank_mrr_verifier_top1_by_part_and_not_run_for_the_rest(world):
    an = analyse(world)
    lines = '\n'.join(memo.render_g1_section(an))
    assert 'Rerank MRR on public53' in lines and 'Verifier top-1 by Part' in lines and 'V15f-R5' in lines
    empty = analysis.analyse(RowStore(world[0].store.dir.parent / 'empty'), arms=world[1], cases=world[2],
                             pipelines=tuple(world[1]))
    assert empty.decision is None
    assert 'No pipeline met the rule' in memo.render_decision(empty)


def test_describe_walks_the_chain():
    arms = fakes.fake_arms()
    text = memo.describe(arms, 'V15f-R5')
    assert text.startswith('Jev `jev-1.13.0` judges all 2,080') and 'must quote word for word' in text
    assert 'reciprocal-rank fusion' in memo.describe(arms, 'F1-rrf-R5-R1-R2')


def test_g4_planning_uses_measured_coverage_or_says_it_is_unmeasured(world):
    an = analyse(world)
    text = '\n'.join(memo.render_g4_needs(an, 'V15f-R5'))
    assert 'Part 9 development cases now' in text
    assert memo.render_g4_needs(an, None)[-1] == memo.NOT_RUN


def test_formatting_helpers():
    assert memo.pct(0.6416) == '64.2%' and memo.pct(None) == '-' and memo.usd(0.01758) == '$0.0176' and memo.secs(9400) == '9.4 s'
    assert memo.cell({'x': 34, 'n': 53, 'rate': 34 / 53, 'wilson_95': [0.5, 0.75]}) == '34 of 53 (64.2%, 50.0%-75.0%)'
    assert memo.cell({'n': 0}) == '0 of 0'


# ---- gates ------------------------------------------------------------------------------------------------------

def test_g4_is_not_run_without_a_calibrated_threshold_and_never_fits_one(world):
    from evals_dev.accuracy.gates import evaluate_g4, passed
    an = analyse(world)
    checks = evaluate_g4(an, 'V15f-R5', None)
    assert [c.status for c in checks] == ['NOT RUN'] and not passed(checks)
    assert 'calibration sweep committed picks' in checks[0].text
    assert [c.status for c in evaluate_g4(an, 'V15f-R5', {'status': 'placeholder_uncalibrated'})] == ['NOT RUN']
    assert [c.status for c in evaluate_g4(an, None, None)] == ['NOT RUN']


def test_g4_fails_when_the_validation_fold_has_too_few_committed_picks(world):
    from evals_dev.accuracy.gates import evaluate_g4
    an = analyse(world)
    checks = evaluate_g4(an, 'V15f-R5', {'status': 'calibrated', 'parts': {'9': {'threshold': 0.5}}})
    assert checks[0].status == 'FAIL' and 'need at least 50' in checks[0].text


def test_g1_checks_fail_closed_on_missing_data(world):
    from evals_dev.accuracy.gates import evaluate_g1, passed
    an = analyse(world)
    checks = {c.id: c for c in evaluate_g1(an, 'V15f-R5')}
    assert checks['G1.1'].status in ('PASS', 'FAIL', 'NOT RUN') and checks['G1.2'].status == 'FAIL'    # 2 repeats, 5 are needed
    assert not passed(list(checks.values()))
