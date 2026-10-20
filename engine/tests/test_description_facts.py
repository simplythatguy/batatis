"""The production description extractor is the labelled-set winner."""
import json
from pathlib import Path

from engine.description_facts import WINNER, extract_description, extract_regex, score_variant

ROOT = Path(__file__).resolve().parents[2] / 'evals_dev' / 'description_facts'
LABELS = ROOT / 'labelled.json'
RESULTS = ROOT / 'RESULTS.md'
HELD_OUT = ROOT / 'held_out.json'
HELD_OUT_REPORT = ROOT / 'HELD_OUT.md'


def _load():
    rows = json.loads(LABELS.read_text())
    assert len(rows) >= 30
    return rows


def _round_report(report):
    out = {}
    for field, stats in report.items():
        out[field] = {
            'precision': round(stats['precision'], 4),
            'recall': round(stats['recall'], 4),
            'tp': stats['tp'], 'fp': stats['fp'], 'fn': stats['fn'],
        }
        if 'f1' in stats:
            out[field]['f1'] = round(stats['f1'], 4)
    return out


def _recorded_blocks(path: Path) -> list[dict]:
    parts = path.read_text().split('```json')[1:]
    return [json.loads(part.split('```')[0]) for part in parts]


# Frozen output of the first blind run, before these five texts were used to change the extractor.
_HELD_OUT_FIRST_RUN = {
    'reports': {
        name: {
            'storeys': {'precision': 1.0, 'recall': 0.75, 'tp': 3, 'fp': 0, 'fn': 1},
            'building_area_m2': {'precision': 1.0, 'recall': 0.6667, 'tp': 2, 'fp': 0, 'fn': 1},
            'span_m': {'precision': 1.0, 'recall': 1.0, 'tp': 0, 'fp': 0, 'fn': 0},
            'occupancy': {'precision': 0.5, 'recall': 0.5, 'tp': 1, 'fp': 1, 'fn': 1},
            'alternative_description': {'precision': 1.0, 'recall': 1.0, 'tp': 5, 'fp': 0, 'fn': 0},
            'micro': {'precision': 0.9167, 'recall': 0.7857, 'tp': 11, 'fp': 1, 'fn': 3, 'f1': 0.8462},
        }
        for name in ('regex', 'normalised')
    },
    'misses': {
        name: [
            {'id': 'brief-a-manufacturer', 'field': 'storeys', 'gold': 2, 'predicted': None},
            {'id': 'brief-a-manufacturer', 'field': 'building_area_m2', 'gold': 190, 'predicted': None},
            {'id': 'brief-a-manufacturer', 'field': 'occupancy', 'gold': 'single_family', 'predicted': 'industrial'},
        ]
        for name in ('regex', 'normalised')
    },
}


def _misses(rows, name):
    from engine.description_facts import EXTRACTORS

    found = []
    for row in rows:
        extracted = EXTRACTORS[name](row['text'])
        predicted = {fact.field: fact.value for fact in extracted.facts}
        predicted['alternative_description'] = extracted.alternative_description
        for field in ('storeys', 'building_area_m2', 'span_m', 'occupancy', 'alternative_description'):
            gold, pred = row.get(field), predicted.get(field)
            if gold is None and pred is None:
                continue
            same = gold == pred
            if field in ('building_area_m2', 'span_m') and gold is not None and pred is not None:
                same = abs(float(gold) - float(pred)) <= 0.02
            if field == 'alternative_description' and isinstance(gold, str) and isinstance(pred, str):
                same = ' '.join(gold.split()) == ' '.join(pred.split())
            if not same:
                found.append({'id': row['id'], 'field': field, 'gold': gold, 'predicted': pred})
    return found


def test_labelled_set_is_synthetic_and_the_winner_is_recorded():
    readme = (ROOT / 'README.md').read_text()
    assert 'synthetic, in-sample' in readme
    rows = _load()
    reports = {name: _round_report(score_variant(rows, name)) for name in ('regex', 'normalised')}
    best = max(reports, key=lambda name: (reports[name]['micro']['f1'], name == 'normalised'))
    assert WINNER == best
    assert reports[WINNER]['micro']['f1'] >= reports['regex']['micro']['f1']
    assert reports[WINNER]['micro']['f1'] >= reports['normalised']['micro']['f1']
    text = RESULTS.read_text()
    assert 'Synthetic, in-sample' in text
    assert _recorded_blocks(RESULTS)[0] == reports


def test_held_out_first_run_stays_frozen_and_post_fix_is_not_blind():
    report = HELD_OUT_REPORT.read_text()
    assert 'held-out, first run, agent-labelled' in report
    assert 'post-fix, no longer blind' in report
    rows = json.loads(HELD_OUT.read_text())
    assert {row['id'] for row in rows} == {
        'script-c-homebuilder', 'script-a-manufacturer', 'brief-a-manufacturer',
        'brief-b-contractor', 'brief-c-homebuilder'}
    assert all(row['labelling'] == 'agent-labelled, not human-verified' for row in rows)
    first, post = _recorded_blocks(HELD_OUT_REPORT)
    assert first == _HELD_OUT_FIRST_RUN
    fresh = {
        'reports': {name: _round_report(score_variant(rows, name)) for name in ('regex', 'normalised')},
        'misses': {name: _misses(rows, name) for name in ('regex', 'normalised')},
    }
    assert post == fresh
    assert post != first
    for name, found in fresh['misses'].items():
        for miss in found:
            assert miss['id'] in report and miss['field'] in report


def _facts(text: str) -> dict:
    return {fact.field: fact.value for fact in extract_description(text).facts}


def test_question_mark_drops_only_the_interrogative_clause():
    text = '2-storey single-family, about 190 m², housewrap?'
    facts = _facts(text)
    assert facts['storeys'] == 2
    assert facts['building_area_m2'] == 190
    assert facts['occupancy'] == 'single_family'
    alternative = extract_description(text).alternative_description
    assert alternative is not None and 'housewrap' not in alternative and '?' not in alternative
    for separated in (
        '2-storey single-family; about 190 m²; housewrap?',
        '2-storey single-family — about 190 m² — housewrap?',
        '| Building | 2-storey single-family, about 190 m² |\n| Wall | housewrap?',
    ):
        assert _facts(separated) == facts
    for question in ('Is 2-storey enough?', 'What do I need for a 2-storey garden suite?'):
        extracted = extract_description(question)
        assert extracted.facts == () and extracted.alternative_description is None
        assert extract_regex(question).facts == ()


def test_factory_bonded_is_not_industrial_and_residential_wins_a_conflict():
    assert 'occupancy' not in _facts('The facer is factory-bonded.')
    assert _facts('A factory of 2 storeys.')['occupancy'] == 'industrial'
    assert _facts('A warehouse of 2 storeys.')['occupancy'] == 'industrial'
    assert _facts(
        'A 2-storey single-family house with factory-bonded panels.')['occupancy'] == 'single_family'
    assert _facts('A single-family house beside a warehouse.')['occupancy'] == 'single_family'
    assert 'occupancy' not in _facts('A hotel beside a warehouse.')
    assert 'occupancy' not in _facts('A single-family house and a duplex.')
    assert extract_regex('The facer is factory-bonded.').facts == ()
