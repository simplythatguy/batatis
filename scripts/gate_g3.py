"""Gate G3: the official SCC form export is complete and clean for the three demo cases and the BTRboard sample.

Run: python scripts/gate_g3.py            (uses the tracked supplied form and a built public CodeDB)

Checks, one line each, then PASS or FAIL:
  1. N/A only from applicant facts: N/A cells trace to a confirmed applicant fact; removing the fact leaves a blank
  2. runtime applicant fields filled or N/A for each case
  3. `python -m codedb validate` over the exported text: 0 errors
  4. render: every filled field drawn inside its box; long values carried by the appendix
  5. appendix: Section C rows (lookup objectives and functions, quoted sentence, how identified) and the six
     process rows with their provenance
  6. precedent-example panel data for the six process fields: structure only, sources by title and page
  7. CCMC snapshot bundled and used by the offline fallback; export runtime files are in the engine bundle
  8. wording: request for variance and alternative solution named; no complies/safe/approved/adequate
Exit status 0 only when every check passes.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from fnmatch import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.codes import Codes  # noqa: E402
from engine.export import export_case, form_path  # noqa: E402
from engine.export.demo_cases import CASES, demo_case  # noqa: E402
from engine.export.g3 import (appendix_problems, appendix_text, coverage, coverage_problems,  # noqa: E402
                              render_problems, wording_problems)
from engine.export.sample import sample_case  # noqa: E402


def _cli_validate(result) -> list[str]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'export.md'
        path.write_text('\n\n'.join(result.text) + '\n')
        run = subprocess.run([sys.executable, '-m', 'codedb', 'validate', str(path)], cwd=ROOT,
                             capture_output=True, text=True)
    if run.returncode == 0:
        return []
    errors = [line for line in run.stdout.splitlines() if ': error ' in line]
    return errors or [f'exit {run.returncode}: {(run.stdout + run.stderr).strip()[-300:]}']


def _na_problems(name, case, result, codes) -> list[str]:
    out = [f'{name}: {f} N/A without a fact' for f in coverage_problems(case, result) if 'N/A' in f]
    facts = [f for f in case.facts if f.field.startswith('not_applicable.')]
    out += [f'{name}: {f.field} is not applicant-confirmed' for f in facts
            if f.status != 'confirmed' or f.source.type not in ('user_text', 'user_click')]
    if facts:
        stripped = case.model_copy(deep=True)
        stripped.facts = [f for f in stripped.facts if not f.field.startswith('not_applicable.')]
        again = export_case(stripped, codes=codes, draft=True)
        if again.not_applicable or any(p.lines == ['N/A'] for p in again.placements):
            out.append(f'{name}: N/A still shown after the applicant facts were removed')
        if not again.blank_fields:
            out.append(f'{name}: removing the N/A facts left no blank field (N/A was not from the facts)')
    return out


def _examples_problems() -> list[str]:
    from engine.process_examples import problems
    return problems()


def _bundle_problems() -> list[str]:
    from engine import ccmc
    from engine.export import scc
    function = json.loads((ROOT / 'vercel.json').read_text())['services']['engine']['functions']['engine/api.py']
    inc, exc = (function[k].strip('{}').split(',') for k in ('includeFiles', 'excludeFiles'))
    match = lambda rel, globs: any(fnmatch(rel, g) or fnmatch(rel, g.replace('/**/', '/')) for g in globs)  # noqa: E731
    out = []
    for path in (scc.BUNDLE_FORM, scc.form_path(), scc.MAP_DIR / f'{scc.CURRENT_MAP}.json', ccmc.BUNDLED_SNAPSHOT, ccmc.BUNDLED_META,
                 ROOT / 'engine' / 'data' / 'process_examples.json'):
        rel = path.relative_to(ROOT).as_posix()
        if not match(rel, inc) or match(rel, exc):
            out.append(f'{rel} is not in the engine bundle')
        elif path != scc.BUNDLE_FORM and not path.is_file():      # the form is fetched by the build, not committed
            out.append(f'{rel} is missing')
    found = ccmc.CCMCRegistry(offline=True).search('insulation')
    if found.source != 'snapshot' or found.registry_date == 'unknown' or not found.total_matches:
        out.append('the CCMC offline fallback did not answer from the dated bundled snapshot')
    return out


def main() -> int:
    if not form_path().is_file():
        print('G3 cannot run: the tracked supplied challenge template is missing.')
        return 2
    codes = Codes()
    cases = {name: demo_case(name, codes) for name in CASES}
    cases['sample-btrboard'] = sample_case(codes)
    checks = {k: [] for k in ('1 N/A only from applicant facts', '2 runtime applicant fields filled or N/A',
                              '3 codedb validate: 0 errors', '4 render test', '5 Section C and process rows',
                              '6 precedent-example panel data', '7 CCMC snapshot and bundle', '8 wording')}
    keys = list(checks)
    print('Gate G3: official SCC form export')
    for name, case in cases.items():
        result = export_case(case, codes=codes)
        cov = coverage(case, result)
        print(f'  {name}: {len(cov["filled"])} filled + {len(cov["na"])} N/A of {sum(map(len, cov.values()))}; '
              f'{result.form_pages} form pages + {result.appendix_pages} appendix pages; {len(case.section_c)} Section C rows')
        checks[keys[0]] += _na_problems(name, case, result, codes)
        checks[keys[1]] += [f'{name}: {p}' for p in coverage_problems(case, result) if 'N/A' not in p]
        checks[keys[2]] += [f'{name}: {p}' for p in _cli_validate(result)]
        checks[keys[3]] += [f'{name}: {p}' for p in render_problems(result)]
        checks[keys[4]] += [f'{name}: {p}' for p in appendix_problems(case, result, codes)]
        text = appendix_text(result)
        checks[keys[7]] += [f'{name}: {p}' for p in wording_problems(case, result)]
        checks[keys[7]] += [f'{name}: missing "{w}"' for w in ('request for variance', 'Alternative solution (Div C 2.3.1)',
                            'at least the level of performance of the acceptable solution') if w not in text]
    checks[keys[5]] += _examples_problems()
    checks[keys[6]] += _bundle_problems()
    for key, problems in checks.items():
        print(f'  [{"PASS" if not problems else "FAIL"}] {key}' + (f' ({len(problems)} problems)' if problems else ''))
        for p in problems[:10]:
            print(f'      - {p}')
    ok = not any(checks.values())
    print('G3 PASS' if ok else 'G3 FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
