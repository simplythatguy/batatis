# PyInstaller spec: the desktop engine as one directory. Only engine and codedb code and their tracked
# runtime data; no code database, NRC text, evaluation data, research corpus or environment file.
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(SPECPATH).parent


def modules(package):
    """Every module of a package from its files: routes are imported by name, which analysis cannot see."""
    found = []
    for path in sorted((ROOT / package).rglob('*.py')):
        parts = path.relative_to(ROOT).with_suffix('').parts
        if 'tests' in parts:
            continue
        found.append('.'.join(parts[:-1] if parts[-1] == '__init__' else parts))
    return found


hidden = modules('engine') + modules('codedb')
datas = [(str(ROOT / folder), folder) for folder in (
    'engine/data', 'engine/export/templates', 'engine/export/field_maps', 'engine/export/fixtures')]
for pattern in ('engine/identify/*.json', 'engine/intake/*.json', 'engine/identify/jevkit/LICENSE'):
    datas += [(str(path), str(path.parent.relative_to(ROOT))) for path in ROOT.glob(pattern)]
datas += collect_data_files('reportlab') + collect_data_files('certifi') + collect_data_files('pypdfium2_raw')

a = Analysis(
    [str(ROOT / 'desktop' / 'engine_entry.py')],
    pathex=[str(ROOT)],
    hiddenimports=hidden,
    datas=datas,
    excludes=['pytest', 'uvicorn', 'tkinter', 'evals', 'evals_dev', 'research', 'IPython'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='batatis-engine', console=True,
          debug=False, strip=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='batatis-engine')
