"""Deterministic checks on the appeal cases.

Labels are weak. Counts here are not model grades and not human verification.
A pre-2023 article stays out of the citation denominator until ``nbc_ae_2023`` is set.
"""
from __future__ import annotations

import json
from pathlib import Path

from evals_dev.appeals.mapping import attempt_mapping
from evals_dev.stats import proportion

LABEL_SOURCE = 'appeals_weak'
CODEDB_MISSING = 'skipped: codedb missing'
NO_MAPPED = 'no mapped NBC(AE) 2023 citations'

SECTION_C_ID = 'scc-co-0015414-2012'
INSUFFICIENT_ID = 'scc-co-2022-06'
ACCEPTED_ID = 'scc-co-0015427-2012'
DEFERENCE_IDS = ('scc-co-0015432-2013', 'scc-co-2024-06')
DEFERENCE_LABELS = {
    'scc-co-0015432-2013': 'officer_not_bound',
    'scc-co-2024-06': 'issuer_must_not_dismiss_expert_without_competing_evidence',
}


def load_appeals(path: Path) -> list[dict]:
    if not path.is_dir():
        return []
    return [json.loads(p.read_text()) for p in sorted(path.glob('scc-*.json'))]


def mapped_citations(cases: list[dict], db_path: Path | None) -> tuple[list[dict], dict]:
    """Citations that survived mapping. Same-identifier hits are counted as unmapped."""
    cites = []
    unmapped = 0
    not_promoted = 0
    for case in cases:
        for entry in case.get('article_mapping') or []:
            attempted = attempt_mapping(entry, db_path)
            target = attempted.get('nbc_ae_2023')
            if target:
                cites.append({
                    'provision': target,
                    'division': attempted.get('source_division'),
                    'source': 'appeals_mapped',
                })
            else:
                unmapped += 1
                if attempted.get('method') == 'same_identifier_in_codedb':
                    not_promoted += 1
    return cites, {'unmapped': unmapped, 'same_identifier_not_promoted': not_promoted}


def citation_resolution(cases: list[dict], db_path: Path | None, score) -> dict:
    cites, meta = mapped_citations(cases, db_path)
    meta['codedb_used'] = db_path is not None
    if not cites and db_path is None:
        row = proportion(0, 0, skipped=CODEDB_MISSING)
    elif not cites:
        row = proportion(0, 0, skipped=NO_MAPPED)
    else:
        row = score(cites, db_path, empty_reason=NO_MAPPED)
    row = dict(row)
    row['label_source'] = LABEL_SOURCE
    row['mapping'] = meta
    return row


def _by_id(cases: list[dict]) -> dict[str, dict]:
    return {case['id']: case for case in cases}


def _quote_text(case: dict, field: str) -> str:
    for quote in case.get('quotes') or []:
        if quote.get('field') == field:
            return quote.get('text') or ''
    return ''


def section_c_anchor(cases: list[dict], db_path: Path | None) -> dict:
    """0015414 faulted a variance for skipping objectives and functional statements."""
    case = _by_id(cases).get(SECTION_C_ID)
    recorded = False
    if case is not None:
        quote = _quote_text(case, 'refusal_reason_evidence')
        gold = case.get('gold') or {}
        recorded = (
            'objectives and functional statements' in quote
            and case.get('label_strength') == 'weak'
            and gold.get('must_cite') == []
            and gold.get('section_c') == []
            and 'section_c_objectives_and_functional_statements' in (case.get('anchors') or [])
        )
    structural = proportion(1 if recorded else 0, 1 if case else 0,
                            skipped=None if case else 'anchor case missing')
    return {
        'decision_id': SECTION_C_ID,
        'label_source': LABEL_SOURCE,
        'quote_recorded': structural,
        'engine_flags_missing_section_c': _section_c_engine(db_path),
    }


def _section_c_engine(db_path: Path | None) -> dict:
    """Fixture probe: a benchmark with an empty Section C must be flagged. Not the 2006 articles."""
    if db_path is None:
        return proportion(0, 0, skipped=CODEDB_MISSING)
    try:
        from engine.codes import Codes
        from engine.completeness import check_completeness
        from engine.tests.case_builder_fixtures import complete_case
    except ImportError as exc:
        return proportion(0, 0, skipped=f'skipped: engine unavailable ({type(exc).__name__})')
    case = complete_case()
    case.section_c = []
    gaps = check_completeness(case, Codes(db_path))
    hit = any(gap.id.startswith('D16:') for gap in gaps)
    return proportion(1 if hit else 0, 1)


def professional_agreement(cases: list[dict], flagger, *, skipped: str | None = None) -> dict:
    """Exact match of the engine screen to the weak flag. ``flagger`` is None when the screen cannot run."""
    rows = [case for case in cases if (case.get('professional_involvement') or {}).get('addressed')]
    counts = {'yes': 0, 'depends': 0, 'no': 0}
    for case in rows:
        flag = (case.get('professional_involvement') or {}).get('weak_flag')
        if flag in counts:
            counts[flag] += 1
    if flagger is None:
        agreement = proportion(0, 0, skipped=skipped or CODEDB_MISSING)
    else:
        hit = 0
        for case in rows:
            want = case['professional_involvement']['weak_flag']
            if flagger(case) == want:
                hit += 1
        agreement = proportion(hit, len(rows))
    return {
        'label_source': LABEL_SOURCE,
        'decisions': len(rows),
        'weak_labels': counts,
        'agreement': agreement,
    }


def engine_professional_flagger(db_path: Path):
    from engine.codes import Codes
    from engine.professional import ProfessionalFacts, professional_involvement

    codes = Codes(db_path)

    def flagger(case: dict) -> str:
        facts = ProfessionalFacts.model_validate((case.get('professional_involvement') or {}).get('facts') or {})
        return professional_involvement(facts, codes).required

    return flagger


def other_anchors(cases: list[dict]) -> dict:
    found = _by_id(cases)
    info = found.get(INSUFFICIENT_ID)
    info_ok = False
    if info is not None:
        detail = info.get('insufficient_information') or {}
        cited = json_articles(info)
        info_ok = (
            info.get('refusal', {}).get('code') == 'R2_insufficient'
            and info.get('refusal', {}).get('basis_type') == 'close analog'
            and detail.get('source_provision') == '2.2.10.8.(2)(b)'
            and detail.get('source_edition') == 'NBC(AE) 2019'
            and detail.get('nbc_ae_2023') is None
            and detail.get('presented_as_2023') is False
            and (info.get('gold') or {}).get('must_cite') == []
            and any('2.2.10.8' in (row.get('source_article') or '') for row in cited)
            and all(row.get('nbc_ae_2023') is None for row in cited)
        )
    accepted = found.get(ACCEPTED_ID)
    accepted_ok = False
    if accepted is not None:
        detail = accepted.get('accepted_with_condition') or {}
        accepted_ok = (
            accepted.get('outcome') == 'varied'
            and detail.get('outcome') == 'varied'
            and bool(detail.get('condition'))
            and (accepted.get('gold') or {}).get('must_cite') == []
            and 'alternative_accepted_with_condition' in (accepted.get('anchors') or [])
        )
    left = found.get(DEFERENCE_IDS[0])
    right = found.get(DEFERENCE_IDS[1])
    opposed = False
    if left is not None and right is not None:
        opposed = (
            left.get('deference') == DEFERENCE_LABELS[DEFERENCE_IDS[0]]
            and right.get('deference') == DEFERENCE_LABELS[DEFERENCE_IDS[1]]
            and left.get('deference') != right.get('deference')
            and left.get('label_strength') == 'weak'
            and right.get('label_strength') == 'weak'
        )
    return {
        'label_source': LABEL_SOURCE,
        'insufficient_information_2022_06': {
            'decision_id': INSUFFICIENT_ID,
            'source_provision': '2.2.10.8.(2)(b)',
            'source_edition': 'NBC(AE) 2019',
            'recorded': proportion(1 if info_ok else 0, 1 if info else 0,
                                   skipped=None if info else 'anchor case missing'),
        },
        'accepted_with_condition_0015427': {
            'decision_id': ACCEPTED_ID,
            'recorded': proportion(1 if accepted_ok else 0, 1 if accepted else 0,
                                   skipped=None if accepted else 'anchor case missing'),
        },
        'officer_deference_opposed': {
            'decisions': list(DEFERENCE_IDS),
            'labels': dict(DEFERENCE_LABELS),
            'recorded': proportion(1 if opposed else 0, 1 if left and right else 0,
                                   skipped=None if left and right else 'anchor case missing'),
        },
    }


def json_articles(case: dict) -> list[dict]:
    return list(case.get('article_mapping') or [])


def build_appeals_block(cases: list[dict], db_path: Path | None, score, *, professional_flagger=None) -> dict:
    if not cases:
        empty = proportion(0, 0, skipped='no appeal cases')
        return {
            'label_source': LABEL_SOURCE,
            'citation_resolution': empty,
            'section_c_anchor': empty,
            'professional_involvement': {'label_source': LABEL_SOURCE, 'agreement': empty},
            'anchors': empty,
        }
    flagger = professional_flagger
    flagger_skip = None
    if flagger is None and db_path is not None:
        try:
            flagger = engine_professional_flagger(db_path)
        except ImportError as exc:
            flagger_skip = f'skipped: engine unavailable ({type(exc).__name__})'
    return {
        'label_source': LABEL_SOURCE,
        'note': (
            'Appeal labels are weak mappings from permit refusals and order appeals. '
            'They are not human verification and not NBC(AE) 2023 gold.'
        ),
        'citation_resolution': citation_resolution(cases, db_path, score),
        'section_c_anchor': section_c_anchor(cases, db_path),
        'professional_involvement': professional_agreement(cases, flagger, skipped=flagger_skip),
        'anchors': other_anchors(cases),
    }
