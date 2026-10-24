"""The supplied default is tracked; the legacy form is still fetched at build time."""
import importlib.util
import json
from fnmatch import fnmatch
from pathlib import Path


def test_codes_only_source_build_does_not_fetch_a_substitute_variance_form(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location('supplied_form_sources', root / 'scripts' / 'fetch_sources.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    code = {'key': 'synthetic-code-source'}
    monkeypatch.setattr(module, 'load_sources', lambda: [code])
    fetched = []
    monkeypatch.setattr(module, 'acquire', lambda item, **_: fetched.append(item) or Path('synthetic.pdf'))
    assert module.main(['--codes-only']) == 0
    assert fetched == [code]
    fetched.clear()
    assert module.main(['--scc-form']) == 0
    assert fetched == [module.SCC_FORM]


def test_each_versioned_runtime_template_is_bundled_without_an_ignored_reference_file():
    from engine.export import form_path
    root = Path(__file__).resolve().parents[2]
    config = json.loads((root / 'vercel.json').read_text())
    files = config['services']['engine']['functions']['engine/api.py']
    include = files['includeFiles'].strip('{}').split(',')
    exclude = files['excludeFiles'].strip('{}').split(',')
    for version in ['challenge_2026-09-15']:
        path = form_path(version)
        assert path.is_file()
        relative = str(path.relative_to(root))
        assert any(fnmatch(relative, pattern) for pattern in include)
        assert not any(fnmatch(relative, pattern) for pattern in exclude)

    assert 'engine/export/templates/*.pdf' in include
    assert 'codedb/build/SCC-Variance-Form.pdf' in include
    legacy = root / 'engine/export/templates/scc_2026-10.pdf'
    assert not legacy.exists(), 'Option B never commits or packages a tracked legacy form'
    build = (root / 'scripts/vercel_build_engine.sh').read_text()
    assert '--scc-form' in build or 'SCC-Variance-Form.pdf' in build
    assert '--codes-only' not in build
    assert 'f2749e1273e1b1d5826ac98cc0d8cfcb1204386914751d496f0d162d9014b42a' in build
