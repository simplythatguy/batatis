"""Success rate, chains, commit exploration and the decision rule, on hand-built rows."""
import pytest

from evals_dev.identify_bench import report
from evals_dev.identify_bench.datasets import BenchCase
from evals_dev.identify_bench.decision import decide, pareto_front
from evals_dev.identify_bench.rows import RowDraft, RowStore, make_row


def case(cid, gold, family=None, dataset='public53', fold='selection'):
    return BenchCase(id=cid, dataset=dataset, query='q', gold=tuple(gold), family=family or cid, fold=fold)


def add(store, arm, c, repeat, order, *, usd=0.0, ms=None, profile='throughput', upstream=None, probs=None, picks=None,
        errors=None, cached=False, notes=None, chash=None, tokens=None):
    draft = RowDraft(order=order, probabilities=probs or {}, usd=usd, latency_ms=ms or {}, upstream=upstream or {},
                     picks=picks or [], errors=errors or [], cached=cached, notes=notes or {}, tokens=tokens or {})
    row = make_row(draft, arm=arm, chash=chash or f'h-{arm}', case=c, repeat=repeat, attempt=1, profile=profile,
                   git_sha='t', codedb_sha256='x')
    store.append(row)
    return row


def loaded(store, cases, arms, kinds=None, profile='throughput'):
    return report.load(store, cases, {a: f'h-{a}' for a in arms}, kinds or {}, profile)


P9, OTHER, MIXED = ['9.1.1.1.'], ['3.2.2.51.'], ['9.1.1.1.', '3.2.2.51.']


def test_success_follows_the_product_definition():
    p9, other, mixed = case('a', P9), case('b', OTHER), case('c', MIXED)
    assert p9.part_group == 'part9' and other.part_group == 'other' and mixed.part_group == 'mixed'
    assert report.success(p9, ['9.1.1.1.', 'x']) and not report.success(p9, ['x', '9.1.1.1.'])       # first only
    assert report.success(other, ['x', 'y', '3.2.2.51.']) and not report.success(other, ['x', 'y', 'z', '3.2.2.51.'])
    assert report.success(mixed, ['x', 'y', '3.2.2.51.'])                                            # top-3 rule
    assert not report.success(case('d', []), ['x'])


def test_majority_is_strict():
    assert report.majority([True, True, False]) and not report.majority([True, False]) and not report.majority([])


def test_evaluate_arm_counts_misses_and_reports_groups_and_stability(tmp_path):
    store = RowStore(tmp_path)
    cs = [case('a', P9), case('b', P9), case('c', OTHER), case('d', OTHER)]
    orders = {  # repeat -> case -> order
        0: {'a': ['9.1.1.1.'], 'b': ['x', '9.1.1.1.'], 'c': ['3.2.2.51.'], 'd': ['x', 'y', 'z', '3.2.2.51.']},
        1: {'a': ['9.1.1.1.'], 'b': ['9.1.1.1.'], 'c': ['y'], 'd': ['x', 'y', 'z', '3.2.2.51.']},
        2: {'a': ['9.1.1.1.'], 'b': ['x'], 'c': ['3.2.2.51.'], 'd': ['3.2.2.51.']},
    }
    for r, by_case in orders.items():
        for c in cs:
            add(store, 'A', c, r, by_case[c.id])
    e = report.evaluate_arm(loaded(store, cs, ['A']), 'A', cs)
    assert e.repeats == 3 and e.missing_rows == 0
    assert e.outcome == {'a': True, 'b': False, 'c': True, 'd': False}      # d succeeds in 1 of 3 repeats only
    assert e.sr['label'] == '2 of 4'
    assert e.sr_by_group['part9']['label'] == '1 of 2' and e.sr_by_group['other']['label'] == '1 of 2'
    assert e.by_repeat_sr == [0.5, 0.5, 0.75]
    assert e.ranking['hit@1']['min'] <= e.ranking['hit@1']['mean'] <= e.ranking['hit@1']['max']
    assert e.top1_agreement == pytest.approx((1 + 1 / 3 + 1 / 3 + 1 / 3) / 4)
    assert e.majority_top1_hit['label'] == '2 of 4'


def test_a_missing_row_is_a_miss_and_is_counted(tmp_path):
    store = RowStore(tmp_path)
    cs = [case('a', P9), case('b', P9)]
    add(store, 'A', cs[0], 0, ['9.1.1.1.'])
    e = report.evaluate_arm(loaded(store, cs, ['A']), 'A', cs)
    assert e.missing_rows == 1 and e.sr['label'] == '1 of 2'


def test_chain_cost_adds_stages_and_latency_adds_sequential_stages(tmp_path):
    store = RowStore(tmp_path)
    c = case('a', P9)
    r4 = add(store, 'R4', c, 0, ['x'], usd=0.016, ms={'screen': 1600, 'request_p50': 420}, profile='interactive')
    r5 = add(store, 'R5', c, 0, ['x'], usd=0.001, ms={'rerank': 400}, profile='interactive', upstream={'R4': r4['key']})
    v = add(store, 'V', c, 0, ['x'], usd=0.003, ms={'verify': 7000}, profile='interactive', upstream={'R5': r5['key']},
            tokens={'openai': {'input': 6000, 'output': 2000}})
    L = loaded(store, [c], ['R4', 'R5', 'V'], profile='interactive')
    row = L.rows['V'][('a', 0)]
    assert report.chain_usd(L, row) == pytest.approx(0.020)
    assert report.chain_latency_ms(L, row) == 9000                    # request_p50 is not a stage
    assert report.chain_tokens(L, row)['openai'] == {'input': 6000, 'output': 2000}


def test_fusion_branches_run_in_parallel_so_the_slowest_counts(tmp_path):
    store = RowStore(tmp_path)
    c = case('a', P9)
    a = add(store, 'A', c, 0, ['x'], ms={'rank': 100}, profile='interactive')
    b = add(store, 'B', c, 0, ['x'], ms={'rank': 900}, profile='interactive')
    f = add(store, 'F', c, 0, ['x'], profile='interactive', upstream={'A': a['key'], 'B': b['key']},
            notes={'parallel_upstream': True})
    L = loaded(store, [c], ['A', 'B', 'F'], profile='interactive')
    assert report.chain_latency_ms(L, L.rows['F'][('a', 0)]) == 900


def test_cached_recorded_and_errored_rows_never_count_towards_latency(tmp_path):
    store = RowStore(tmp_path)
    c = case('a', P9)
    add(store, 'A', c, 0, ['x'], ms={'screen': 100}, profile='interactive', cached=True)
    add(store, 'B', c, 0, ['x'], ms={'screen': 100}, profile='interactive', errors=[{'category': 'x'}])
    add(store, 'C', c, 0, ['x'], ms={'screen': 100}, profile='interactive')
    L = loaded(store, [c], ['A', 'B', 'C'], profile='interactive')
    assert report.chain_latency_ms(L, L.rows['A'][('a', 0)]) is None
    assert report.chain_latency_ms(L, L.rows['B'][('a', 0)]) is None
    assert report.chain_latency_ms(L, L.rows['C'][('a', 0)]) == 100


def test_latency_uses_the_first_repeat_when_there_are_several(tmp_path):
    store = RowStore(tmp_path)
    c = case('a', P9)
    for rep, ms in enumerate((9000, 3000, 3000)):          # later repeats of one prompt can hit the provider's prompt cache
        add(store, 'V', c, rep, ['x'], ms={'verify': ms}, profile='interactive')
    L = loaded(store, [c], ['V'], profile='interactive')
    s = report.latency_summary(L, 'V', [c])
    assert s['p50_ms'] == 9000 and s['n'] == 1 and s['all_repeats_p50_ms'] == 3000


def test_commit_exploration_is_part_9_probability_and_verifier_agreement(tmp_path):
    store = RowStore(tmp_path)
    cs = [case('a', P9), case('b', P9), case('c', OTHER)]
    probs = {'9.1.1.1.': 0.9, '9.2.2.2.': 0.8, '3.2.2.51.': 0.95}
    pick = [{'article': '9.1.1.1.', 'quote': 'q', 'reason': 'r', 'confidence': 0.9}]
    add(store, 'V', cs[0], 0, ['9.1.1.1.', '9.2.2.2.'], probs=probs, picks=pick)                 # right commit
    add(store, 'V', cs[1], 0, ['9.2.2.2.', '9.1.1.1.'], probs=probs, picks=[{**pick[0], 'article': '9.2.2.2.'}])   # wrong commit
    add(store, 'V', cs[2], 0, ['3.2.2.51.'], probs=probs, picks=[{**pick[0], 'article': '3.2.2.51.'}])           # not Part 9
    L = loaded(store, cs, ['V'], kinds={'V': 'verify'})
    c = report.commit_stats(L, 'V', cs, threshold=0.75)
    assert c['precision']['label'] == '1 of 2' and c['coverage']['label'] == '2 of 2'
    assert c['wrong_commits'] == ['b#r0:9.2.2.2.'] and c['status'].startswith('placeholder_uncalibrated')
    strict = report.commit_stats(L, 'V', cs, threshold=0.85)                                       # 0.8 falls below
    assert strict['precision']['label'] == '1 of 1'
    rel = report.reliability(L, 'V', cs)
    assert sum(b['n'] for b in rel) == 2


def test_the_verifier_recheck_finds_a_fabricated_pick(tmp_path):
    store = RowStore(tmp_path)
    c = case('a', P9)
    arts = {'9.1.1.1.': {'id': '9.1.1.1.', 'part': 9, 'title': 'T', 'section': 'S', 'subsection': 'U',
                         'text': 'the wall shall be protected'}}
    good = {'article': '9.1.1.1.', 'quote': 'wall shall be protected', 'reason': 'r', 'confidence': 1}
    add(store, 'V', c, 0, ['9.1.1.1.'], picks=[good], notes={'raw_picks': 1, 'kept': 1, 'dropped': 0})
    add(store, 'V', c, 1, ['9.1.1.1.'], picks=[{**good, 'quote': 'not in the text'}],
        notes={'raw_picks': 1, 'kept': 1, 'dropped': 0})
    L = loaded(store, [c], ['V'])
    L.arts = arts
    assert report.verifier_integrity(L, list(L.rows['V'].values()))['fabricated_citations_shown'] == 1


# ---- the decision rule ---------------------------------------------------------------------------------------

def world(tmp_path, spec, n=40):
    """spec: arm -> (cases succeeded as a set of indexes, usd per case, optional extras)."""
    store = RowStore(tmp_path)
    cs = [case(f'c{i:02}', OTHER, dataset='public53') for i in range(n)]
    for arm, (wins, usd, *extra) in spec.items():
        for i, c in enumerate(cs):
            order = ['3.2.2.51.'] if i in wins else ['x']
            add(store, arm, c, 0, order, usd=usd, notes=(extra[0] if extra else {}))
    L = loaded(store, cs, list(spec))
    return cs, {a: report.evaluate_arm(L, a, cs) for a in spec}


def test_the_cheapest_tied_pipeline_wins(tmp_path):
    cs, ev = world(tmp_path, {'best': (set(range(30)), 0.050), 'cheap': (set(range(29)), 0.002),
                              'weak': (set(range(15)), 0.0)})
    d = decide(ev, {}, cs)
    assert d.best == 'best' and d.winner == 'cheap'
    rows = {r.arm: r for r in d.rows}
    assert rows['cheap'].tied and not rows['weak'].tied and rows['weak'].p_worse < 0.10
    assert rows['best'].pareto and rows['cheap'].pareto


def test_a_tie_needs_both_no_significant_loss_and_three_points(tmp_path):
    cs, ev = world(tmp_path, {'best': (set(range(30)), 0.05), 'near': (set(range(28)), 0.001)})   # 5 points behind
    d = decide(ev, {}, cs)
    rows = {r.arm: r for r in d.rows}
    assert not rows['near'].tied and d.winner == 'best'


def test_the_override_takes_a_much_cheaper_pipeline_within_five_points(tmp_path):
    cs, ev = world(tmp_path, {'best': (set(range(60)), 0.30), 'cheap': (set(range(57)), 0.01)}, n=80)   # 3.75 points behind
    d = decide(ev, {}, cs)
    rows = {r.arm: r for r in d.rows}
    assert not rows['cheap'].tied and d.winner == 'cheap' and any('override' in t for t in d.trace)
    cs, ev = world(tmp_path / 'b', {'best': (set(range(60)), 0.30), 'cheap': (set(range(57)), 0.20)}, n=80)   # not 3x cheaper
    assert decide(ev, {}, cs).winner == 'best'


def test_hard_filters_disqualify_but_the_pipeline_is_still_reported(tmp_path):
    cs, ev = world(tmp_path, {'slow': (set(range(35)), 0.01), 'ok': (set(range(30)), 0.02)})
    d = decide(ev, {'slow': {'p95_ms': 25_000}, 'ok': {'p95_ms': 9_000}}, cs)
    rows = {r.arm: r for r in d.rows}
    assert d.winner == 'ok' and rows['slow'].filters['H2_p95_under_20s'] is False and 'hard filter' in ' '.join(rows['slow'].notes)


def test_an_unmeasured_latency_does_not_disqualify_it_is_flagged(tmp_path):
    cs, ev = world(tmp_path, {'only': (set(range(30)), 0.01)})
    d = decide(ev, {}, cs)
    assert d.winner == 'only' and {r.arm: r for r in d.rows}['only'].filters['H2_p95_under_20s'] is None


def test_incomplete_data_is_excluded_from_the_choice(tmp_path):
    store = RowStore(tmp_path)
    cs = [case(f'c{i}', OTHER) for i in range(10)]
    for c in cs:
        add(store, 'full', c, 0, ['3.2.2.51.'], usd=0.01)
    for c in cs[:5]:
        add(store, 'partial', c, 0, ['3.2.2.51.'], usd=0.0)
    L = loaded(store, cs, ['full', 'partial'])
    d = decide({a: report.evaluate_arm(L, a, cs) for a in ('full', 'partial')}, {}, cs)
    assert d.winner == 'full' and any('incomplete' in n for r in d.rows if r.arm == 'partial' for n in r.notes)


def test_robustness_rejects_a_pipeline_that_trails_the_bm25_floor_on_a_part_group(tmp_path):
    store = RowStore(tmp_path)
    cs = [case(f'p{i:02}', P9) for i in range(30)] + [case(f'o{i:02}', OTHER) for i in range(30)]
    for c in cs:
        is_p9 = c.id.startswith('p')
        add(store, 'R0-bm25', c, 0, [c.gold[0]] if is_p9 else ['x'], usd=0.0)           # the floor only knows Part 9
        add(store, 'fancy', c, 0, ['x'] if c.id == 'p00' else [c.gold[0]], usd=0.01)     # 59 of 60, one Part 9 miss
        add(store, 'steady', c, 0, [c.gold[0]], usd=0.02)                               # 60 of 60
    L = loaded(store, cs, ['R0-bm25', 'fancy', 'steady'])
    ev = {a: report.evaluate_arm(L, a, cs) for a in ('R0-bm25', 'fancy', 'steady')}
    d = decide(ev, {}, cs)
    rows = {r.arm: r for r in d.rows}
    assert rows['fancy'].tied and rows['fancy'].usd < rows['steady'].usd             # it would win on cost alone
    assert rows['fancy'].robust['not_behind_floor_by_group'] is False and rows['fancy'].robust['behind_floor_on'] == ['part9']
    assert d.winner == 'steady' and any('robustness failed for fancy' in t for t in d.trace)


def test_pareto_front():
    assert pareto_front({'a': (0.9, 0.05), 'b': (0.8, 0.01), 'c': (0.7, 0.02), 'd': (0.9, 0.06)}) == {'a', 'b'}
