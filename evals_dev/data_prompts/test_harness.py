"""Offline checks of the Data Prompts harness: no provider calls and no attachments needed."""
from __future__ import annotations

from evals_dev.data_prompts import checks, corpus, gold, judge
from evals_dev.data_prompts.gold import Item


def test_every_case_loads_with_review_points():
    cases = corpus.load()
    assert len(cases) == 653
    assert all(c.focus and all(len(p) > 3 for p in c.focus) for c in cases)
    assert all(c.prompt for c in cases)


def test_split_keeps_shared_sources_on_one_side_and_is_stable():
    cases = corpus.load()
    sides = corpus.split(cases)
    assert set(sides.values()) == {'dev', 'holdout'}
    by_group: dict[str, set[str]] = {}
    by_file: dict[str, set[str]] = {}
    for c in cases:
        by_group.setdefault(c.source_group, set()).add(sides[c.id])
        for a in c.attachments:
            by_file.setdefault(a.sha256, set()).add(sides[c.id])
    assert all(len(s) == 1 for s in by_group.values())
    assert all(len(s) == 1 for s in by_file.values())
    corpus.split.cache_clear()
    assert corpus.split(cases) == sides
    for tier in corpus.TIERS:
        dev = sum(1 for c in cases if c.tier == tier and sides[c.id] == 'dev')
        held = sum(1 for c in cases if c.tier == tier and sides[c.id] == 'holdout')
        assert held > 0 and dev > 0


def test_prohibitions_are_read_from_wording():
    p = lambda text: judge.is_prohibition(Item('R1', 'R', text))   # noqa: E731
    assert p('do not transfer this British Columbia appeal outcome or code interpretation to Alberta')
    assert p('no compliance certification')
    assert p('Makes no compliance statement.')
    assert p('Whether it does not say the woodburner complies.')
    assert not p('no drawings or calculations attached')
    assert not p('code edition not stated')
    assert not p('Does not say the design complies or is safe; asks for the fire engineering report')
    assert not judge.is_prohibition(Item('F1', 'F', 'do not ...'))


def test_a_covered_verdict_needs_an_excerpt_that_is_in_the_report():
    report = 'FACTS READ\n- [a.pdf p.3] statement: "travel distance of 25 m to a point of choice"'
    assert judge.found('travel distance of 25 m', report)
    assert judge.found('Travel distance of 25 m to a point ... choice', report)
    assert not judge.found('travel distance of 30 m', report)
    assert not judge.found('ok', report)


def test_claim_guardrail_reads_only_outright_verdicts():
    assert checks.claims(['The design complies with the code.'])
    assert checks.claims(['This assembly is code-compliant.'])
    assert not checks.claims(['Batatis does not say whether the design complies with the code.'])
    assert not checks.claims(['Does the wall meet the code requirement?'])
    assert not checks.claims(['Your evidence must show that the design meets the requirements.'])


def test_edition_and_boundary_items_come_from_metadata():
    assert gold.edition_status('National Building Code – 2023 Alberta Edition') == 'current'
    assert gold.edition_status('NBC(AE) 2023 and NFC(AE) 2023; printing not stated') == 'current'
    assert gold.edition_status('Alberta Building Code 2014') == 'historical'
    assert gold.edition_status('NBC 2015') == 'historical'
    assert gold.edition_status('unknown if unstated') == 'unknown'
    cases = {c.tier: c for c in corpus.load()}
    outside = gold.boundary_items(cases['Outside Alberta - attachment comparison only'])
    assert len(outside) == 1 and 'outside Alberta' in outside[0].text
