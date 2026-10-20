"""The v1.1 scorer reads an external file and does not open the precedent index.

Those labels are internal and not judge-facing."""
import json
from pathlib import Path

from engine.section_d_flag_eval import load_codes
from engine.section_d_heldout_v11 import INTERPRETATION, LABEL, SECTION, labelled_cases, report


def test_heldout_v11_scorer_skips_null_labels_and_splits_source(tmp_path):
    rows = [
        {'id': 'heldout-v1-appeal', 'description': 'A house.', 'known_facts': [],
         'gold_engineering_flag': {'engineering_required': 'yes'}},
        {'id': 'heldout-v1-unlabelled', 'description': 'A house.', 'known_facts': [],
         'gold_engineering_flag': None},
        {'id': 'heldout-v1.1-23-bcv-001', 'description': 'A window device.', 'known_facts': [],
         'source_type': 'STANDATA province-wide variance (not an individual application)',
         'gold_engineering_flag': {'engineering_required': 'no'}},
    ]
    path = tmp_path / 'cases.jsonl'
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    loaded = [json.loads(line) for line in path.read_text().splitlines()]
    cases, skipped = labelled_cases(loaded)
    assert skipped == 1
    assert [case['source'] for case in cases] == ['appeal', 'bcv']
    codes, _codedb = load_codes()
    text = report(loaded, codes)
    assert text.startswith(SECTION)
    assert INTERPRETATION in text
    assert 'internal' in text and 'not judge-facing' in text
    assert 'confident_wrong' in text
    assert 'unknown_rate' in text
    assert 'first run with frozen rules' in text
    assert 'precedent retrieval: off' in text
    assert LABEL in text
    assert 'skipped null: 1' in text
    assert 'labelled n: 2' in text
    assert 'source appeal n=1' in text
    assert 'source bcv n=1' in text
    assert 'pooled n=2' in text
    source = Path('engine/section_d_heldout_v11.py').read_text()
    assert 'research.precedents' not in source
    assert 'from .identify' not in source
    assert 'import identify' not in source
