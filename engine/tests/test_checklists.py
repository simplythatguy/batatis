"""AC5.5: standing-package checklists are complete, sourced, verified against the reference text and never
a determination.

The quote check reads the git-excluded `reference/text/<stem>.jsonl` (or `BATATIS_REFERENCE_DIR`) and skips
cleanly when it is absent; everything else runs anywhere.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from engine.jurisdictions import DATA_DIR, PackError, Registry
from engine.jurisdictions.checklists import NONE_IN_PACK, NONE_NO_JURISDICTION, NOTICE, normalise
from engine.models_checklists import QUOTE_MAX, StandingChecklist

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = Path(os.environ.get('BATATIS_REFERENCE_DIR') or ROOT / 'reference')   # git-excluded
FOLDER = DATA_DIR / 'checklists'
BANNED = re.compile(r'\b(compl(y|ies|iant|iance)|safe|safely|approved?|approval|adequate(ly)?)\b', re.I)
SUMMARY_ONLY = re.compile(r'\b(see (the )?source|etc\.?|and so on|all (of the )?conditions|as listed|as required by the package)\b', re.I)

# Every operative item each source prints, by the label the checklist cites. Read from the PDFs by hand;
# a checklist that drops one fails here, so a summary row cannot stand in for the items.
EXPECTED_LABELS = {
    'calgary-spv-001': {
        'Background', 'Reason for the Variance', 'Note', 'Accepted method of Variance',
        'a)', 'b) i.', 'b) ii.', 'b) iii.', 'c) i.', 'c) ii.', 'c) iii.', 'd)', 'e)', 'f)', 'g)', 'h)', 'i)',
        'j) i.', 'j) ii.', 'j) iii.', 'k) i.', 'k) ii.', 'k) iii.', 'l)', 'l) i.', 'l) ii.', 'l) iii.', 'l) iv.',
        'm)', 'Authority and conditions', 'This Variance is based on'},
    'calgary-spv-006': {
        'Reason for Variance', 'Note', 'Acceptable method of Variance',
        '1. a)', '1. b)', '1. c)', '2. a)', '2. b)', '2. c)', '3. a)', '3. b) i)', '3. b) ii)', '3. b) iii)',
        '3. b) iv)', 'footnote (1)', 'footnote (2)', '3. c)', '4. a)', '4. a) i)', '4. a) ii)', '5. a)', '5. b)',
        '6. a)', '6. b)', '7. a)', 'Authority and conditions', 'This variance is based on'},
    'edmonton-b23-01': {
        'Policy', 'Purpose', 'Procedure 1.', 'Procedure 2.', 'Letter of Construction Intention',
        'Letter, first statement', 'Letter, second statement', 'Letter, third statement', 'Letter, fourth statement'},
}


@pytest.fixture(scope='module')
def reg() -> Registry:
    return Registry.load(DATA_DIR)


def _checklists() -> list[StandingChecklist]:
    return [StandingChecklist.model_validate(json.loads(p.read_text())) for p in sorted(FOLDER.glob('*.json'))]


# ---------------------------------------------------------------- schema

def test_the_three_checklists_load_and_link_both_ways(reg):
    assert set(reg.checklists) == set(EXPECTED_LABELS) == {p.stem for p in FOLDER.glob('*.json')}
    for checklist in reg.checklists.values():
        pkg = next(p for p in reg.get(checklist.jurisdiction).standing_packages if p.id == checklist.package)
        assert pkg.checklist == checklist.id and pkg.status == 'current'
        assert pkg.code == checklist.code and pkg.source.sha256 == checklist.source.sha256


def test_unknown_keys_and_bad_options_are_rejected():
    raw = json.loads((FOLDER / 'calgary-spv-001.json').read_text())
    with pytest.raises(ValidationError):
        StandingChecklist.model_validate({**raw, 'complies': True})
    bad = json.loads(json.dumps(raw))
    bad['conditions'][0]['one_of'] = 'x'                 # an option without its label
    with pytest.raises(ValidationError):
        StandingChecklist.model_validate(bad)
    with pytest.raises(ValidationError):                 # reviewed needs a named reviewer and date
        StandingChecklist.model_validate({**raw, 'reviewed': True})
    long = json.loads(json.dumps(raw))
    long['conditions'][0]['source']['quote'] = 'x' * (QUOTE_MAX + 1)
    with pytest.raises(ValidationError):
        StandingChecklist.model_validate(long)


def _copy(tmp_path) -> Path:
    root = tmp_path / 'jurisdictions'
    shutil.copytree(DATA_DIR, root)
    return root


def _edit(path: Path, change):
    data = json.loads(path.read_text())
    change(data)
    path.write_text(json.dumps(data))


def test_a_historical_package_can_never_name_a_checklist(tmp_path):
    root = _copy(tmp_path)
    def to_b14(data):
        b14 = next(p for p in data['standing_packages'] if p['code'] == 'B14-01')
        b14['checklist'] = 'edmonton-b23-01'
    _edit(root / 'packs' / 'edmonton.json', to_b14)
    with pytest.raises(PackError, match='B14-01'):
        Registry.load(root)


def test_a_package_naming_a_missing_checklist_fails(tmp_path):
    root = _copy(tmp_path)
    (root / 'checklists' / 'calgary-spv-006.json').unlink()
    with pytest.raises(PackError, match='missing checklist calgary-spv-006'):
        Registry.load(root)


def test_a_checklist_must_match_its_package(tmp_path):
    root = _copy(tmp_path)
    _edit(root / 'checklists' / 'calgary-spv-001.json', lambda d: d.update(issued='2017-10-01'))
    with pytest.raises(PackError, match='must match package SPV-001'):
        Registry.load(root)


def test_a_package_cannot_borrow_another_packages_checklist(tmp_path):
    root = _copy(tmp_path)
    def borrow(data):    # a second, synthetic current package points at another office's checklist
        extra = json.loads(json.dumps(data['standing_packages'][0]))
        extra.update(id='edmonton-planted', code='PLANTED-1', checklist='calgary-spv-001')
        data['standing_packages'].append(extra)
    _edit(root / 'packs' / 'edmonton.json', borrow)
    with pytest.raises(PackError, match='belongs to calgary/calgary-spv-001'):
        Registry.load(root)


def test_removing_a_pack_removes_its_checklists(tmp_path):
    root = _copy(tmp_path)
    (root / 'packs' / 'calgary.json').unlink()
    assert set(Registry.load(root).checklists) == {'edmonton-b23-01'}


# ---------------------------------------------------------------- completeness

@pytest.mark.parametrize('checklist', _checklists(), ids=lambda c: c.id)
def test_every_operative_item_of_the_source_has_a_row(checklist):
    labels = {c.source.label for c in checklist.conditions}
    assert EXPECTED_LABELS[checklist.id] <= labels, EXPECTED_LABELS[checklist.id] - labels


@pytest.mark.parametrize('checklist', _checklists(), ids=lambda c: c.id)
def test_no_summary_only_rows(checklist):
    seen = set()
    for c in checklist.conditions:
        assert c.source.quote.strip() and c.source.page >= 1, c.id
        assert not SUMMARY_ONLY.search(c.plain), c.id
        key = (c.source.page, c.source.label, normalise(c.source.quote))   # same words under another item are fine
        assert key not in seen, f'{c.id} repeats another row\'s quote'
        seen.add(key)
        if not c.may_not_apply:
            assert c.when is None, f'{c.id}: a conditional row must allow does_not_apply'
    for group in checklist.groups:
        assert any(c.group == group.id for c in checklist.conditions), group.id


# Article, then any sentence and clause parts: 9.10.15.5.(8)(a) stays distinct from 9.10.15.5.(8)(b).
CODE_REF = re.compile(r'\b(?:[A-D]-\d+(?:\.\d+)+|\d+\.\d+\.\d+(?:\.\d+)*)\.?(?:\(\d+\))?(?:\([a-z]{1,4}\))*')


@pytest.mark.parametrize('checklist', _checklists(), ids=lambda c: c.id)
def test_every_code_reference_in_plain_text_is_in_the_verified_extract(checklist):
    """Plain text may not add a citation the source extract does not carry."""
    untraced = []
    for c in checklist.conditions:
        extract = normalise(f'{c.source.lead_in or ""} {c.source.quote}').replace('[', '(').replace(']', ')')
        for ref in CODE_REF.findall(f'{c.plain} {c.when or ""}'):
            if not _cites(extract, ref):
                untraced.append(f'{c.id}: {ref}')
    assert untraced == []


def _refs(text: str) -> set[str]:
    return {m.group(0).rstrip('.') for m in CODE_REF.finditer(text)}


def _cites(extract: str, ref: str) -> bool:
    """Whole references only: 9.10.15.5 is not found inside 9.10.15.50, and a sentence cites its article."""
    wanted = ref.rstrip('.')
    found = _refs(extract)
    return wanted in found or any(r.startswith(wanted + '.(') or r.startswith(wanted + '(') for r in found)


def test_reference_matching_is_whole_reference_not_substring():
    assert not _cites('see 9.10.15.50. for soffits', '9.10.15.5.')
    assert _cites('see 9.10.15.5. for soffits', '9.10.15.5.')
    assert _cites('Sentence 9.10.15.5.(8) applies', '9.10.15.5.')
    assert not _cites('Clause 9.10.15.5.(8)(a) applies', '9.10.15.5.(8)(b)')
    assert _cites('Clause 9.10.15.5.(8)(b) applies', '9.10.15.5.(8)(b)')


@pytest.mark.parametrize('checklist', _checklists(), ids=lambda c: c.id)
def test_copy_never_says_complies_safe_approved_or_adequate(checklist):
    texts = [checklist.summary, *(g.title for g in checklist.groups), *(g.plain for g in checklist.groups),
             *(n.plain for n in checklist.source_notes)]
    for c in checklist.conditions:
        texts += [c.plain, c.when or '']
    found = [t for t in texts if BANNED.search(t)]
    assert found == []


def test_notice_says_a_checklist_is_never_a_determination():
    assert 'never a determination' in NOTICE and 'officer decides' in NOTICE
    for text in (NOTICE, NONE_IN_PACK, NONE_NO_JURISDICTION):
        assert not BANNED.search(text)


def test_spv_001_covers_both_houses_and_the_registered_agreement(reg):
    spv = reg.checklists['calgary-spv-001']
    subjects = {c.subject for c in spv.conditions}
    assert {'both_houses', 'both_parcels', 'zero_side', 'easement_side'} <= subjects
    quotes = ' '.join(normalise(c.source.quote) for c in spv.conditions)
    assert 'on both side walls of both houses' in quotes
    assert 'registered on the title of th parcel and the adjacent parcel' in quotes
    assert 'closer together than 0.9 m' in quotes
    agreement = [c for c in spv.conditions if c.group == 'agreement']
    assert len(agreement) >= 6 and not any(c.may_not_apply for c in agreement)
    assert any(n.kind == 'conflict' and 'footing' in n.plain for n in spv.source_notes)


def test_b14_01_is_historical_only(reg):
    edmonton = reg.get('edmonton')
    b14 = next(p for p in edmonton.standing_packages if p.code == 'B14-01')
    assert b14.status == 'historical' and b14.checklist is None
    assert all(c.code != 'B14-01' for c in reg.checklists.values())


def test_every_checklist_waits_for_a_human_reviewer(reg):
    review = (ROOT / 'evals_dev' / 'checklists' / 'REVIEW.md').read_text()
    for checklist in reg.checklists.values():
        assert checklist.reviewed is False, f'{checklist.id}: only a person who read it in full may flip this'
        assert checklist.id in review


# ---------------------------------------------------------------- quotes against the reference text

def _pages(stem: str) -> dict[int, str]:
    path = REFERENCE / 'text' / f'{stem}.jsonl'
    if not path.is_file():
        pytest.skip(f'reference source not present (reference/text/{stem}.jsonl is git-excluded)')
    pages = {}
    for line in path.read_text().splitlines():
        row = json.loads(line)
        pages[int(row['page'])] = normalise(row['text'])
    return pages


@pytest.mark.parametrize('checklist', _checklists(), ids=lambda c: c.id)
def test_every_quote_is_on_its_page_in_the_reference_text(checklist):
    pages = _pages(checklist.reference_text)
    missing = []
    for c in checklist.conditions:
        for quote in (c.source.quote, c.source.lead_in):
            if quote and normalise(quote) not in pages.get(c.source.page, ''):
                missing.append(f'{c.id} p.{c.source.page}: {quote}')
        for page in re.findall(r'\bp\.(\d+)', c.source.diagram or ''):
            assert int(page) in pages, f'{c.id}: diagram page {page} is not in the source'
    for note in checklist.source_notes:
        if note.quote and normalise(note.quote) not in pages.get(note.page, ''):
            missing.append(f'note {note.id} p.{note.page}: {note.quote}')
    assert missing == []


@pytest.mark.parametrize('checklist', _checklists(), ids=lambda c: c.id)
def test_the_local_pdf_is_the_one_the_checklist_was_built_from(checklist):
    found = list((REFERENCE / 'precedents').rglob(f'{checklist.reference_text}.pdf'))
    if not found:
        pytest.skip('reference/precedents is git-excluded and not present here')
    assert hashlib.sha256(found[0].read_bytes()).hexdigest() == checklist.source.sha256


def test_the_quote_check_catches_a_planted_misquote():
    pages = _pages('calgary-spv-001-zero-lot-line-2026-03')
    assert normalise('Maximum allowable soffit projection into the easement: 0.3 m.') in pages[4]
    assert normalise('Maximum allowable soffit projection into the easement: 0.6 m.') not in pages[4]
