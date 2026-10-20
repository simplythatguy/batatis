"""The plain-checkout benchmark bootstrap installs the requirement files CI uses."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_bootstrap_installs_engine_and_codedb_requirements_and_pins_openai():
    engine = (ROOT / 'engine' / 'requirements.txt').read_text()
    codedb = (ROOT / 'codedb' / 'requirements.txt').read_text()
    script = (ROOT / 'scripts' / 'bench_identify.sh').read_text()
    assert 'openai' in engine
    assert 'pypdf' in codedb
    assert not (ROOT / 'requirements.txt').exists()
    assert '-r engine/requirements.txt -r codedb/requirements.txt' in script
    assert 'requirements.txt' in script
    assert '-r requirements.txt' not in script.replace('-r engine/requirements.txt', '').replace(
        '-r codedb/requirements.txt', '')
    assert 'engine.identify.benchmark' in script
    assert 'export BATATIS_LLM_PROVIDER=openai' in script
    assert 'OPENAI_API_KEY' not in script
