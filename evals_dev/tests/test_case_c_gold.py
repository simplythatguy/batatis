"""Case C gold includes 9.10.19.3.(1) with a why taken from the brief."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHORTLIST = ROOT / 'evals/demo-cases/keys/c-homebuilder-infill-house/expected/article-shortlist.md'
CITED = ROOT / 'evals/demo-cases/cited-provisions.txt'
# drawing-notes.md: "Smoke alarms: per code, locations not yet shown."
# project-brief.md: 2 storeys, Bedroom 3, no basement.
WHY = (
    'Drawing notes say smoke-alarm locations are not yet shown ("per code"), '
    'on a 2-storey house with Bedroom 3 and no basement.'
)


def _ids() -> list[str]:
    return [line.strip() for line in CITED.read_text(encoding='utf-8').splitlines()
            if line.strip() and not line.lstrip().startswith('#')]


def test_case_c_gold_includes_smoke_alarm_location():
    text = SHORTLIST.read_text(encoding='utf-8')
    row = next(line for line in text.splitlines() if line.startswith('|') and '9.10.19.3.(1)' in line)
    cells = [cell.strip() for cell in row.strip('|').split('|')]
    assert cells[1].replace('*', '').strip() == '9.10.19.3.(1)'
    assert cells[2] == WHY
    assert len(cells[2].split()) <= 25
    assert 'shall' not in row.casefold()
    assert 'complies' not in cells[2].casefold()
    assert 'article title Location of Smoke Alarms' in text
    assert '9.10.19.3.(1)' in _ids()
    assert f'all {len(_ids())} listed ids present' in text
