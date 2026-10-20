"""The production description extractor is the labelled-set winner."""
import json
from pathlib import Path

from engine.description_facts import WINNER, score_variant

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


def _recorded(path: Path) -> dict:
    return json.loads(path.read_text().split('```json')[1].split('```')[0])


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
    assert _recorded(RESULTS) == reports


def test_held_out_demo_text_is_scored_and_misses_are_listed():
    report = HELD_OUT_REPORT.read_text()
    assert 'Agent-labelled, not human-verified' in report
    rows = json.loads(HELD_OUT.read_text())
    assert {row['id'] for row in rows} == {
        'script-c-homebuilder', 'script-a-manufacturer', 'brief-a-manufacturer',
        'brief-b-contractor', 'brief-c-homebuilder'}
    assert all(row['labelling'] == 'agent-labelled, not human-verified' for row in rows)
    fresh = {
        'reports': {name: _round_report(score_variant(rows, name)) for name in ('regex', 'normalised')},
        'misses': {name: _misses(rows, name) for name in ('regex', 'normalised')},
    }
    assert _recorded(HELD_OUT_REPORT) == fresh
    for name, found in fresh['misses'].items():
        for miss in found:
            assert miss['id'] in report and miss['field'] in report
