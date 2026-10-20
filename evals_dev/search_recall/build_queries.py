"""Freeze the search-recall query set and the seeded holdout.

Run once, before looking at variant scores. The committed queries.json is the
set that was scored. Re-running this script with the same seed reproduces the
same split; it does not retune anything.

Holdout draw, in order, from random.Random(20261020):
  1. repo-key ids (evals_dev must_cite), sorted, then shuffled
  2. identify-regression ids idr-001..idr-021, sorted, then shuffled
About 30% (Python round) of each pool is held out. Mira's three regressions
and the other regression phrasings are forced onto the in-sample side and are
not part of either shuffle.
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
    ]


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
    queries = repo + idr + regressions()
    payload = {
        'label': LABEL,
        'seed': SEED,
        'split_algorithm': (
            'random.Random(20261020). Shuffle sorted repo-key ids first, then sorted '
            'idr ids. Hold out round(0.30*n) from the front of each shuffled list. '
            'Regression queries are forced in-sample and are not shuffled.'
        ),
        'gold_counts': {
            'repo_key_with_gold': len(repo),
            'identify_regression_with_gold': len(idr),
            'mira_regressions_with_gold_reported_separately': 3,
            'regressions_without_gold': 3,
            'note': 'Gold is copied from evals_dev must_cite or identify-regression gold_articles. Nothing was added by hand except Unc\'s confirmation that 9.23.17.3.(1) counts for idr-001/002, where that article was already on the list.',
        },
        'queries': queries,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n')
    print(f'wrote {OUT}')
    print('repo-key', len(repo_in), 'in-sample', len(repo_out), 'held-out')
    print('idr', len(idr_in), 'in-sample', len(idr_out), 'held-out')
    print('held-out repo', sorted(repo_out))
    print('held-out idr', sorted(idr_out))


if __name__ == '__main__':
    main()
