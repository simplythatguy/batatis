"""Turn the researcher's appeal JSON into the trimmed internal eval cases.

Reads one JSON object per decision plus index.json. Writes structured fields, one-
or two-sentence excerpts, and the source URL. Does not read PDFs or extracted text
files, and does not copy pdf_path, text_path, notes, or the full paraphrase.

    python evals_dev/appeals/convert.py /path/to/appeals-structured
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from evals_dev.appeals.mapping import classify_article, edition_bucket  # noqa: E402

OUT = Path(__file__).resolve().parent / 'cases'

# Fixed-width lookbehinds. The period may sit on either side of a closing quote.
_SENT = re.compile(
    r"(?<=[a-z0-9][.])\s+(?=[A-Z])"
    r"|(?<=['\u2019\"][.])\s+(?=[A-Z])"
    r"|(?<=[.?!]['\u2019])\s+(?=[A-Z])"
    r'|(?<=[.?!]["])\s+(?=[A-Z])'
)
_PROVISION = re.compile(r'\b\d{1,2}(?:\.\d{1,3}){2,}')
# Holdings that are not the first two sentences of the researcher's note.
QUOTE_OVERRIDE = {
    ('scc-co-2024-06', 'professional_involvement'): (
        "Permit issuers are not permitted to declare an expert's conclusions incorrect. "
        "If the City requires expert assessments it must recognize their legitimacy, "
        "or substantiate concerns with competing evidence."
    ),
}

# Stated in the opening paraphrase, not inferred from who spoke at the hearing.
APPLICANT = {
    'scc-co-0015414-2012': 'manufacturer',
    'scc-co-0015416-2012': 'owner',
    'scc-co-0015432-2013': 'owner',
    'scc-co-0015443-2014': 'architect-engineer',
    'scc-co-0015470-2016': 'homebuilder',
    'scc-co-0015471-2016': 'homebuilder',
    'scc-co-0015482-2018': 'owner',
    'scc-co-0015496-2019': 'owner',
}
TOPIC = {
    'scc-co-0015412-2012': 'part9-spatial-separation',
    'scc-co-0015439-2014': 'part4-structural',
    'scc-co-0015467-2016': 'cladding',
    'scc-co-0015470-2016': 'part9-spatial-separation',
    'scc-co-0015471-2016': 'part9-spatial-separation',
    'scc-co-2023-03': 'part4-structural',
}
JURISDICTION = {
    'scc-co-2023-02': 'Calgary',
    'scc-co-2023-03': 'Calgary',
}

# Weak flags for the 12 decisions whose index marks professional involvement as addressed.
# "yes" is the panel's conclusion. It is not an engine ProfessionalFacts trigger.
WEAK_FLAG = {
    'scc-co-0015416-2012': 'yes',
    'scc-co-0015421-2012': 'depends',
    'scc-co-0015427-2012': 'depends',
    'scc-co-0015428-2012': 'yes',
    'scc-co-0015432-2013': 'depends',
    'scc-co-0015439-2014': 'yes',
    'scc-co-0015447-2015': 'yes',
    'scc-co-0015467-2016': 'depends',
    'scc-co-2022-06': 'depends',
    'scc-co-2023-03': 'depends',
    'scc-co-2023-08': 'yes',
    'scc-co-2024-06': 'depends',
}
# Only fields the decision states in the engine's own vocabulary.
# A panel conclusion is not stored as a fact. It is the weak label.
# An order to file schedules is not rewritten as ahj_requires_professional.
PROFESSIONAL_FACTS: dict[str, dict] = {}
FACTS_PROVENANCE = {
    'scc-co-0015416-2012': (
        'The panel sentence about special safety concerns is the weak yes label. '
        'It is not stored as a screen fact.'
    ),
}
PROFESSIONAL_FACT_NOTES = {
    'scc-co-0015416-2012': (
        'special_safety_concerns was omitted: it comes from the panel conclusion '
        'that also supplies the weak yes label, not an independent authority statement.'
    ),
}
DEFERENCE = {
    'scc-co-0015432-2013': 'officer_not_bound',
    'scc-co-2024-06': 'issuer_must_not_dismiss_expert_without_competing_evidence',
}
CONDITION_0015427 = (
    'Standpipe requirement removed on acceptance of the alternative. '
    'Firefighting water supply and the other plans-examination requirements remain.'
)


def split_sentences(text: str) -> list[str]:
    """Normalize whitespace and split retained research text at supported sentence boundaries."""
    text = ' '.join((text or '').split())
    if not text:
        return []
    return [part.strip() for part in _SENT.split(text) if part.strip()]


def _sentences(text: str, n: int = 2) -> str:
    """Keep at most n sentences and restore terminal punctuation where splitting removed it."""
    parts = split_sentences(text)
    if not parts:
        return ''
    kept = []
    for index, part in enumerate(parts[:n]):
        if index < len(parts) - 1 and not part.endswith(('.', '?', '!', "'", '"', '\u2019')):
            part += '.'
        elif index < len(parts) - 1 and part[-1] in "'\"\u2019" and '.' not in part[-3:]:
            part += '.'
        kept.append(part)
    return ' '.join(kept)


def _description(facts: str) -> str:
    """Opening paraphrase with provision numbers removed so they are not read as citations."""
    parts = _SENT.split(' '.join((facts or '').split()))
    kept = []
    for part in parts:
        part = part.strip().rstrip('.')
        if not part or _PROVISION.search(part):
            continue
        kept.append(part + '.')
        if len(kept) == 2:
            break
    return ' '.join(kept)


def _other_codes(code_edition: str) -> list[str]:
    """Identify supported fire-code and standard labels mentioned in the source edition."""
    found = []
    for label, pattern in (
        ('NFC(AE) 2019', r'NFC'),
        ('AFC 2006', r'\bAFC\b|Alberta Fire Code'),
        ('NFPA 80', r'NFPA'),
    ):
        if re.search(pattern, code_edition or '') and label not in found:
            found.append(label)
    return found


def _quote(text: str | None, confidence: str, *, kind: str) -> dict | None:
    """Trim source text to two sentences and attach its provenance classification."""
    short = _sentences(text or '', 2)
    if not short:
        return None
    return {
        'text': short,
        'sentences': len(split_sentences(short)),
        'quote_confidence': confidence,
        'kind': kind,
    }


def convert_record(rec: dict, index_row: dict) -> dict:
    """Convert one research record to a trimmed weak-label case without promoting citations."""
    edition = edition_bucket(rec.get('code_edition') or '')
    confidence = 'low' if str(rec.get('text_source') or '').startswith('OCR') else 'standard'
    case_id = rec['id']
    quotes = []
    for field in ('refusal_reason_evidence', 'professional_involvement'):
        override = QUOTE_OVERRIDE.get((case_id, field))
        source = override if override is not None else (rec.get(field) if isinstance(rec.get(field), str) else None)
        # A possessive or an embedded fragment does not make a paraphrase an excerpt.
        # An opening quotation, or a holding kept in QUOTE_OVERRIDE, does.
        quoted = (source or '').lstrip().startswith(("'", '"', '\u2018', '\u201c'))
        kind = 'excerpt' if field == 'refusal_reason_evidence' or override is not None or quoted else 'summary'
        item = _quote(source, confidence, kind=kind)
        if item:
            item['field'] = field
            item['source_url'] = rec.get('url')
            quotes.append(item)
    addressed = bool(index_row.get('professional_involvement_addressed'))
    flag = WEAK_FLAG.get(case_id)
    if addressed != (flag is not None):
        raise SystemExit(f'{case_id}: professional-involvement flag does not match the index')
    anchors = []
    if case_id == 'scc-co-0015414-2012':
        anchors.append('section_c_objectives_and_functional_statements')
    if case_id == 'scc-co-2022-06':
        anchors.append('insufficient_information')
    if case_id == 'scc-co-0015427-2012':
        anchors.append('alternative_accepted_with_condition')
    if case_id in DEFERENCE:
        anchors.append('officer_deference')
    case = {
        'id': case_id,
        'title': rec.get('title'),
        'decision_date': rec.get('decision_date'),
        'source_url': rec.get('url'),
        'applicant_type': APPLICANT.get(case_id),
        'topic': TOPIC.get(case_id),
        'code_part': None,
        'jurisdiction': JURISDICTION.get(case_id, 'unspecified'),
        'seed_provision': None,
        'description': _description(rec.get('facts') or ''),
        'description_kind': 'paraphrase',
        'known_facts': list(rec.get('topics') or [])[:6],
        'missing_info': [],
        'edition_original': edition,
        'other_codes': _other_codes(rec.get('code_edition') or ''),
        'text_source_kind': 'ocr' if confidence == 'low' else 'pdftotext',
        'label_strength': 'weak',
        'refusal': {
            'code': index_row.get('refusal_reason_code'),
            'basis_type': index_row.get('refusal_reason_basis_type'),
            'basis': _sentences(rec.get('refusal_reason_basis') or '', 2),
        },
        'outcome': rec.get('outcome'),
        'outcome_summary': _sentences(rec.get('outcome_explanation') or '', 2),
        'outcome_summary_kind': 'paraphrase',
        'article_mapping': [classify_article(article, edition) for article in rec.get('articles_at_issue') or []],
        'quotes': quotes,
        'professional_involvement': {
            'addressed': addressed,
            'weak_flag': flag,
            'label_strength': 'weak' if addressed else None,
            'facts': dict(PROFESSIONAL_FACTS.get(case_id) or {}),
            **({'facts_provenance': FACTS_PROVENANCE[case_id]} if case_id in FACTS_PROVENANCE else {}),
        },
        'anchors': anchors,
        'gold': {
            'departure': '',
            'must_cite': [],
            'should_cite': [],
            'must_not_cite': [],
            'section_c': [],
            'engineering_required': flag,
            'engineering_reason': (
                'Weak appeal label only. Not an NBC(AE) 2023 professional-involvement determination.'
                if flag else ''
            ),
            'engineering_citations': [],
            'intake_action': None,
            'out_of_scope': False,
            'redirect_to': None,
        },
        'authoring': {
            'source': 'scc-appeal-decision',
            'author': 'Batatis appeals converter',
            'date': '2026-10-20',
            'notes': (
                'Weak labels from a Council order or permit appeal, not a refusal on the current variance form. '
                'Source articles are not NBC(AE) 2023 gold.'
            ),
        },
    }
    if case_id in PROFESSIONAL_FACT_NOTES:
        case['authoring']['notes'] += ' ' + PROFESSIONAL_FACT_NOTES[case_id]
    if case_id == 'scc-co-2022-06':
        case['insufficient_information'] = {
            'source_provision': '2.2.10.8.(2)(b)',
            'source_division': 'C',
            'source_edition': 'NBC(AE) 2019',
            'nbc_ae_2023': None,
            'presented_as_2023': False,
            'refusal_code': 'R2_insufficient',
            'basis_type': 'close analog',
        }
    if case_id == 'scc-co-0015427-2012':
        case['accepted_with_condition'] = {
            'outcome': 'varied',
            'condition': CONDITION_0015427,
            'condition_kind': 'paraphrase',
        }
    if case_id in DEFERENCE:
        case['deference'] = DEFERENCE[case_id]
    return case


def convert_dir(source: Path, dest: Path) -> list[dict]:
    """Validate the indexed 25-record research set and replace the generated case files."""
    index = json.loads((source / 'index.json').read_text())
    by_id = {row['id']: row for row in index['decisions']}
    cases = []
    for path in sorted(source.glob('scc-*.json')):
        rec = json.loads(path.read_text())
        if rec['id'] not in by_id:
            raise SystemExit(f'{path.name} is missing from index.json')
        cases.append(convert_record(rec, by_id[rec['id']]))
    if len(cases) != 25:
        raise SystemExit(f'expected 25 decisions, got {len(cases)}')
    dest.mkdir(parents=True, exist_ok=True)
    for stale in dest.glob('*.json'):
        stale.unlink()
    for case in cases:
        (dest / f"{case['id']}.json").write_text(json.dumps(case, indent=2) + '\n')
    return cases


def main(argv: list[str] | None = None) -> int:
    """Convert a supplied research directory and report the number of written cases."""
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('source', type=Path)
    ap.add_argument('--out', type=Path, default=OUT)
    args = ap.parse_args(argv)
    cases = convert_dir(args.source, args.out)
    print(f'wrote {len(cases)} cases to {args.out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
