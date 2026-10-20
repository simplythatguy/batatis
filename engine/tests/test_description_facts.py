"""The production description extractor is the labelled-set winner."""
import json
from pathlib import Path

from engine.description_facts import WINNER, score_variant

ROOT = Path(__file__).resolve().parents[2] / 'evals_dev' / 'description_facts'
LABELS = ROOT / 'labelled.json'
RESULTS = ROOT / 'RESULTS.md'


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


def test_labelled_set_is_synthetic_and_the_winner_is_recorded():
    readme = (ROOT / 'README.md').read_text()
    assert 'Synthetic' in readme and 'in-sample' in readme
    rows = _load()
    reports = {name: _round_report(score_variant(rows, name)) for name in ('regex', 'normalised')}
    best = max(reports, key=lambda name: (reports[name]['micro']['f1'], name == 'normalised'))
    assert WINNER == best
    assert reports[WINNER]['micro']['f1'] >= reports['regex']['micro']['f1']
    assert reports[WINNER]['micro']['f1'] >= reports['normalised']['micro']['f1']
    text = RESULTS.read_text()
    assert 'Synthetic' in text and 'in-sample' in text
    recorded = json.loads(text.split('```json')[1].split('```')[0])
    assert recorded == reports
