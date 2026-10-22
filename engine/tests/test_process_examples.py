"""Precedent-example panel data for the six process fields (WP-33, AC8.2): structure only, never text to paste."""
import json
import re

import pytest

from engine.codes import Codes
from engine.models import Case
from engine.process_examples import (DATA, FIELD_IDS, MAX_STRUCTURE_WORDS, REFERENCE, ProcessExample, examples,
                                     local_file, problems)
from engine.process_fields import process_fields


def test_every_process_field_has_structure_only_example_data():
    assert problems(check_sources=False) == []
    found = examples()
    assert set(found) == set(FIELD_IDS)
    for fid, example in found.items():
        assert example.kind == 'structure_only' and 'structure only' in example.label
        assert len(example.must_address) >= 3 and example.precedents
        for ref in example.precedents:
            assert ref.title and ref.issuer and ref.pdf_page >= 1 and ref.url.startswith('https://')
            assert len(ref.structure.split()) <= MAX_STRUCTURE_WORDS


def test_cited_pages_exist_and_descriptions_copy_no_source_text():
    """Runs against the git-excluded local copies when they are present; the data never carries their text."""
    data = json.loads(DATA.read_text())['fields']
    present = [ref for entry in data.values() for ref in entry['precedents'] if (p := local_file(ref)) and p.is_file()]
    if not present:
        pytest.skip('reference/precedents is not present (git-excluded)')
    assert problems() == []


def test_the_data_holds_no_paste_able_answer_text():
    raw = DATA.read_text()
    assert len(raw.encode()) < 40_000                       # a panel index, not a text corpus
    for entry in json.loads(raw)['fields'].values():
        for item in entry['must_address']:
            assert len(item.split()) <= 40
            assert not re.search(r'"[^"]{40,}"', item)        # no long quotation
        assert set(entry) == {'must_address', 'precedents'}
    assert 'reference/precedents' not in json.dumps([examples()[f].model_dump() for f in FIELD_IDS])


def test_process_fields_carry_the_example_and_never_an_answer():
    fields = process_fields(Case(), Codes())
    assert [f.id for f in fields] == list(FIELD_IDS)
    for field in fields:
        assert isinstance(field.example, ProcessExample) and field.answer is None
    risk = next(f for f in fields if f.id == 'risk_assessment')
    assert any('lapsed maintenance' in s for s in risk.reviewer_looks_for)
    rationale = next(f for f in fields if f.id == 'rationale')
    assert any('at least the level of performance of the acceptable solution' in s for s in rationale.reviewer_looks_for)


def test_local_copies_are_never_served():
    for example in examples().values():
        for ref in example.precedents:
            assert str(REFERENCE) not in ref.model_dump_json() and 'file' not in ref.model_dump()
