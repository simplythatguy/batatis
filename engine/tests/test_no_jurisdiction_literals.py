"""AC6.2: engine code never names a city. Jurisdiction facts live in engine/data/jurisdictions.

Allowed outside data and tests: exactly one line, the account `Authority` literal in
`engine/account_models.py`. PR #48 restricts reviewer accounts to two offices for now; each
reviewer code must have a pack (`test_reviewer_codes_line_up_with_account_authorities`).
Fixture data under `engine/**/fixtures/` is data, not code.
"""
from __future__ import annotations

import re
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1]
LITERAL = re.compile(r'calgary|edmonton', re.IGNORECASE)
ALLOWED = {('account_models.py', "Authority = Literal['calgary', 'edmonton']")}


def _code_files(engine: Path):
    for path in sorted(engine.rglob('*.py')):
        rel = path.relative_to(engine)
        if rel.parts[0] in {'tests', 'data'} or 'fixtures' in rel.parts:
            continue
        yield path, rel


def offending_lines(engine: Path = ENGINE) -> list[str]:
    found = []
    for path, rel in _code_files(engine):
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            if LITERAL.search(line) and (str(rel), line.strip()) not in ALLOWED:
                found.append(f'engine/{rel}:{number}: {line.strip()}')
    return found


def test_no_city_literals_in_engine_code():
    assert offending_lines() == [], 'Move jurisdiction facts into engine/data/jurisdictions packs'


def test_the_allowed_exception_is_still_the_reviewer_authority_literal():
    text = (ENGINE / 'account_models.py').read_text()
    assert all(line in text for _, line in ALLOWED)


def test_the_lint_catches_a_planted_literal(tmp_path):
    planted = tmp_path / 'engine'
    (planted / 'tests').mkdir(parents=True)
    (planted / 'notice.py').write_text("if case.jurisdiction.id == 'Calgary':\n    pass\n")
    (planted / 'tests' / 'test_x.py').write_text("'calgary'\n")
    (planted / 'account_models.py').write_text("Authority = Literal['calgary', 'edmonton']\nOther = 'EDMONTON'\n")
    assert offending_lines(planted) == ["engine/notice.py:1: if case.jurisdiction.id == 'Calgary':",
                                        "engine/account_models.py:2: Other = 'EDMONTON'"][::-1]
