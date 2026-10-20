"""Freeze the search-recall query set and the seeded holdout.

Run once, before looking at variant scores. The committed queries.json is the
set that was scored. Re-running this script with the same seed reproduces the
same split; it does not retune anything.

Holdout draw, in order, from random.Random(20261020):
  1. repo-key ids (evals_dev must_cite), sorted, then shuffled
  2. identify-regression ids idr-001..idr-021, sorted, then shuffled
About 30% (Python round) of each pool is held out. Mira's regressions, the
firestop regressions, and the other regression phrasings are forced onto the
in-sample side and are not part of either shuffle. idr-022..026 are a separate
held-out block and are not shuffled into the original 21.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

SEED = 20261020
ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / 'queries.json'
IDR_SOURCE = Path('/cursor/stores/bot/datanerd/research/identify-regression.json')
LABEL = 'model-checked, not human-verified'

MIRA_LONG = (
    "We manufacture NailBase CI-50, a 50 mm rigid foam panel with a 6 mm fibre-cement facer "
    "that replaces 11 mm OSB sheathing on 2x6 walls at 400 mm o.c. Vinyl siding is nailed "
    "directly into the facer with no furring. We want approval to sell it across Alberta and "
    "to build a pilot house in Edmonton: 2-storey single-family, about 190 m2, unsprinklered, "
    "builder Birchfield Example Homes, address 0000 Example Way NW. We have our product data "
    "sheet, a US lab permeance test summary, and an unsigned draft engineer letter about nail "
    "pull-out. We have no CCMC evaluation yet, no air-leakage test, and no bracing design. "
    "Do we need an engineer to stamp anything?"
)
MIRA_GOLD = ['9.27.5.1.(2)', '9.27.5.3.(3)(b)', '9.23.17.3.(1)']
MIRA_DISTRACTOR = ['9.29.9.3.']


def holdout(rng: random.Random, ids: list[str]) -> tuple[list[str], list[str]]:
    ordered = sorted(ids)
    rng.shuffle(ordered)
    k = int(round(0.30 * len(ordered)))
    held = sorted(ordered[:k])
    kept = sorted(ordered[k:])
    return kept, held


def repo_key_queries() -> list[dict]:
    out = []
    for path in sorted((ROOT / 'evals_dev' / 'cases').glob('dev-*.json')):
        case = json.loads(path.read_text())
        gold = [row['provision'] for row in case['gold']['must_cite'] if row.get('division') == 'B' and row.get('provision')]
        if not gold:
            continue
        out.append({
            'id': case['id'],
            'pool': 'repo-key',
            'scored': True,
            'query': case['description'],
            'gold': gold,
            'gold_level': 'provision',
            'gold_source': f'evals_dev/cases/{path.name} gold.must_cite',
            'distractors': [],
            'label': 'model-checked dev keys, not human-verified',
        })
    return out


def idr_queries() -> list[dict]:
    payload = json.loads(IDR_SOURCE.read_text())
    out = []
    for case in payload['cases']:
        articles = [row['article'] for row in case['gold_articles']]
        distractors = [row['article'] for row in case['must_not_return']]
        note = None
        if case['id'] in {'idr-001', 'idr-002'} and '9.23.17.3.' in articles:
            note = 'Unc confirmed 9.23.17.3.(1) is gold for case A. Counted as gold. model-checked, not human-verified.'
        out.append({
            'id': case['id'],
            'pool': 'identify-regression',
            'scored': True,
            'role': case.get('role'),
            'query': case['description'],
            'gold_articles': articles,
            'gold_level': 'article',
            'gold_source': 'datanerd identify-regression.json gold_articles (codedb-checked 2nd printing); quotes not copied',
            'distractors': distractors,
            'label': LABEL,
            'note': note,
        })
    return out


def regressions() -> list[dict]:
    common = {
        'pool': 'regression',
        'split': 'in-sample',
        'scored': False,
        'forced_in_sample': True,
        'label': LABEL,
    }
    return [
        {
            **common,
            'id': 'mira-sheathing-nail-siding',
            'query': 'sheathing nail siding',
            'gold': list(MIRA_GOLD),
            'gold_level': 'provision',
            'gold_source': 'Case A article-shortlist (9.27.5.1.(2), 9.27.5.3.(3)(b)) and Unc confirmation of 9.23.17.3.(1)',
            'distractors': list(MIRA_DISTRACTOR),
            'assert': 'all_gold_covered_in_top5_and_distractor_absent',
        },
        {
            **common,
            'id': 'mira-foam-insulation-sheathing',
            'query': 'foam insulation sheathing',
            'gold': list(MIRA_GOLD),
            'gold_level': 'provision',
            'gold_source': 'Case A article-shortlist (9.27.5.1.(2), 9.27.5.3.(3)(b)) and Unc confirmation of 9.23.17.3.(1)',
            'distractors': list(MIRA_DISTRACTOR),
            'assert': 'all_gold_covered_in_top5_and_distractor_absent',
        },
        {
            **common,
            'id': 'mira-nailbase-long',
            'query': MIRA_LONG,
            'gold': list(MIRA_GOLD),
            'gold_articles': ['9.27.5.1.', '9.27.5.3.', '9.23.17.3.'],
            'gold_level': 'provision',
            'gold_source': 'Same three provisions as the short Mira queries. Article check: at least 2 of 3 in the top 5.',
            'distractors': list(MIRA_DISTRACTOR),
            'assert': 'at_least_2_of_3_articles_in_top5_and_distractor_absent',
        },
        {
            **common,
            'id': 'reg-cladding-furring',
            'query': 'cladding fastened through exterior insulation into furring',
            'expected': ['9.27.5.1.(1)', '9.27.5.1.(2)', '9.27.5.3.'],
            'gold_level': 'provision',
            'gold_source': None,
            'note': 'Regression, not gold. The phrasing is not a repo key. Expected ids are the Case A sentences and the furring article named for this check.',
            'distractors': list(MIRA_DISTRACTOR),
            'assert': 'cladding_sentences_and_furring_article_in_top5',
        },
        {
            **common,
            'id': 'reg-mfr-vinyl-into-facer',
            'query': 'vertical vinyl siding, ring-shank nails @ 400 o.c. into facer, no furring',
            'gold_source': None,
            'note': 'Manufacturer phrasing copied from the Case A wall-section note. Regression, not gold: the note is not a keyed query.',
            'assert': None,
        },
        {
            **common,
            'id': 'reg-caseb-pex',
            'query': 'Ours are mostly PVC drain pipe and bundles of PEX, and some holes are bigger than the listing allows.',
            'gold_source': None,
            'note': 'Case B phrasing copied from the project brief. Regression, not gold: this sentence is not a keyed query.',
            'assert': None,
        },
        {
            **common,
            'id': 'reg-firestop-plastic-pipe',
            'query': 'firestop plastic pipe penetration',
            'expected': ['3.1.9.4.(2)', '3.1.9.4.(4)', '3.1.9.4.(7)', '9.10.9.7.', '3.1.9.1.(1)'],
            'exact': ['3.1.9.1.(1)'],
            'top_k': 8,
            'gold_source': None,
            'note': 'Unc GC firestop run, plus Karen: 3.1.9.1.(1) itself is required in the top 8. In-sample regression, not gold. Also covers 3.1.9.4.(2)/(4)/(7) and 9.10.9.7.',
            'assert': 'expected_covered_in_top_k',
        },
        {
            **common,
            'id': 'reg-fire-separation-penetration',
            'query': 'fire separation penetration',
            'expected': ['9.10.9.6.', '9.10.9.7.', '3.1.9.4.(2)'],
            'top_k': 8,
            'gold_source': None,
            'note': 'Unc GC firestop run. In-sample regression, not gold. Covers 9.10.9.6, 9.10.9.7, and 3.1.9.4.(2).',
            'assert': 'expected_covered_in_top_k',
        },
        {
            **common,
            'id': 'reg-sprinkler-firestop',
            'query': 'sealant around sprinkler pipes through a fire separation, firestop system',
            'expected': ['3.1.9.1.', '3.1.9.4.(1)'],
            'exact': ['3.1.9.1.'],
            'plus': ['9.10.9.9.(3)'],
            'top_k': 8,
            'gold_source': None,
            'note': 'Unc GC firestop run. 3.1.9.1 and 3.1.9.4.(1) are required in the top 8. 9.10.9.9.(3) is a plus, not required.',
            'assert': 'expected_covered_in_top_k',
        },
    ]


# Held out as a block. Not part of the seeded shuffle. Part 3 gold,
# Part 9 analogues in must_not_return. No code quotes.
PART3 = [
    {
        'id': 'idr-022',
        'query': "We're the GC on a six-storey wood-frame apartment, all rental units, sprinklered throughout. The developer now wants to add a seventh floor of units on top, still wood. Is that a problem, or can we just keep framing?",
        'gold_articles': ['3.2.2.51.', '3.2.2.48.'],
        'distractors': ['9.29.9.3.', '9.10.8.1.', '9.10.4.1.'],
    },
    {
        'id': 'idr-023',
        'query': "Four storeys: shops on the street level, apartments on the three floors above, sprinklered. The drawings show the floor over the shops as the same 1-hour floor as every other level. The owner asks if that's enough between the stores and the apartments.",
        'gold_articles': ['3.1.3.1.', '3.2.2.7.'],
        'distractors': ['9.29.9.3.', '9.10.9.13.', '9.10.8.1.'],
    },
    {
        'id': 'idr-024',
        'query': 'Fit-out of a banquet hall on the second floor of an existing two-storey building, about 400 seats. The owner wants only one exit stair from the hall so the kitchen can go where the second stair is drawn. Can we do that?',
        'gold_articles': ['3.4.2.1.', '3.3.1.5.'],
        'distractors': ['9.29.9.3.', '9.9.8.2.', '9.9.9.1.'],
    },
    {
        'id': 'idr-025',
        'query': "Two-storey office building, about 1,400 m2 on each floor, wood frame, no sprinklers. The floor between the levels is drawn as plain joists and drywall with no rating. The owner says it's just an office so it doesn't need anything special.",
        'gold_articles': ['3.2.2.64.', '3.2.2.62.'],
        'gold_any': ['3.2.2.64.(2)(a)', '3.2.2.62.(2)'],
        'distractors': ['9.29.9.3.', '9.10.8.1.', '9.10.18.2.'],
        'note': 'A hit is either 3.2.2.64.(2)(a) or 3.2.2.62.(2).',
    },
    {
        'id': 'idr-026',
        'query': 'Six-storey hotel. The electrician ran bundles of cable through the rated corridor walls and the drywallers packed the holes with mineral wool and regular caulk. There are also plastic electrical boxes back-to-back in the suite walls. The inspector wants a listed system for each one. Can we leave them?',
        'gold_articles': ['3.1.9.1.', '3.1.9.2.', '3.1.9.3.'],
        'distractors': ['9.29.9.3.', '9.10.9.6.', '9.10.9.7.'],
    },
]


def part3_queries() -> list[dict]:
    rows = []
    for case in PART3:
        rows.append({
            'pool': 'part3-held-out',
            'split': 'held-out',
            'scored': False,
            'forced_held_out': True,
            'id': case['id'],
            'query': case['query'],
            'gold_articles': case['gold_articles'],
            'gold_any': case.get('gold_any'),
            'gold_level': 'article',
            'gold_source': 'identify-regression.json idr-022..026 Part 3 gold; quotes not copied',
            'distractors': case['distractors'],
            'label': 'model-checked, not human-verified',
            'note': case.get('note') or 'Held out as a block before scoring. Not in the seeded shuffle.',
        })
    return rows


def main() -> None:
    rng = random.Random(SEED)
    repo = repo_key_queries()
    idr = idr_queries()
    repo_in, repo_out = holdout(rng, [row['id'] for row in repo])
    idr_in, idr_out = holdout(rng, [row['id'] for row in idr])
    repo_in, repo_out = set(repo_in), set(repo_out)
    idr_in, idr_out = set(idr_in), set(idr_out)
    for row in repo:
        row['split'] = 'in-sample' if row['id'] in repo_in else 'held-out'
    for row in idr:
        row['split'] = 'in-sample' if row['id'] in idr_in else 'held-out'
    part3 = part3_queries()
    queries = repo + idr + part3 + regressions()
    payload = {
        'label': LABEL,
        'seed': SEED,
        'split_algorithm': (
            'random.Random(20261020). Shuffle sorted repo-key ids first, then sorted '
            'idr-001..021 ids. Hold out round(0.30*n) from the front of each shuffled list. '
            'Regression queries are forced in-sample and are not shuffled. '
            'idr-022..026 are a separate held-out block and are not shuffled.'
        ),
        'gold_counts': {
            'repo_key_with_gold': len(repo),
            'identify_regression_with_gold': len(idr),
            'part3_held_out': len(part3),
            'mira_regressions_with_gold_reported_separately': 3,
            'regressions_without_gold': 6,
            'note': 'Gold is copied from evals_dev must_cite or identify-regression gold_articles. Nothing was added by hand except Unc\'s confirmation that 9.23.17.3.(1) counts for idr-001/002, where that article was already on the list. idr-022..026 are scored on their own and do not change the 21-case split.',
        },
        'queries': queries,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n')
    print(f'wrote {OUT}')
    print('repo-key', len(repo_in), 'in-sample', len(repo_out), 'held-out')
    print('idr', len(idr_in), 'in-sample', len(idr_out), 'held-out')
    print('held-out repo', sorted(repo_out))
    print('held-out idr', sorted(idr_out))
    print('part3 held-out', [row['id'] for row in part3])


if __name__ == '__main__':
    main()
