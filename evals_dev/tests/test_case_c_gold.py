"""Case C gold includes the verified smoke-alarm sentence, id and title only."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHORTLIST = ROOT / 'evals/demo-cases/keys/c-homebuilder-infill-house/expected/article-shortlist.md'
CITED = ROOT / 'evals/demo-cases/cited-provisions.txt'


def _ids() -> list[str]:
    return [line.strip() for line in CITED.read_text(encoding='utf-8').splitlines()
            if line.strip() and not line.lstrip().startswith('#')]


def test_case_c_gold_includes_smoke_alarm_location():
    text = SHORTLIST.read_text(encoding='utf-8')
    row = next(line for line in text.splitlines() if line.startswith('|') and '9.10.19.3.(1)' in line)
    cells = [cell.strip() for cell in row.strip('|').split('|')]
    assert cells[1].replace('*', '').strip() == '9.10.19.3.(1)'
    assert cells[2] == 'Location of Smoke Alarms'
    assert len(cells[2].split()) <= 25
    assert 'shall' not in row.casefold()
    assert '9.10.19.3.(1)' in _ids()
    assert f'all {len(_ids())} listed ids present' in text
