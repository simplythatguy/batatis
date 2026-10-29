"""Code identification on the real cases: the product's deterministic ranking against the model's verified picks."""
from __future__ import annotations

from common import RUNS, load_cases, read_json, write_json
from arms import valid_picks


def recall(ranked: list[str], gold: list[str], k: int) -> tuple[int, int, bool]:
    top = ranked[:k]
    hits = sum(g in top for g in gold)
    return hits, len(gold), hits == len(gold)


def main() -> None:
    rows = []
    for case in load_cases():
        r1_path = RUNS / 'responses' / 'r1' / f"{case['id']}.json"
        if not r1_path.exists():
            continue
        s0 = read_json(RUNS / 'stage0' / f"{case['id']}.json")
        r1 = read_json(r1_path)
        picks = [p['id'] for p in valid_picks(case, s0, r1)]
        raw = [p.get('id') for p in r1.get('picks', [])]
        merged = list(dict.fromkeys(picks + s0['prod_rank']))
        rows.append({'id': case['id'], 'type': case['type'], 'gold': case['gold'], 'raw_picks': raw, 'picks': picks,
                     'dropped': len(raw) - len(picks), 'scope': r1.get('scope'),
                     'prod': {k: recall(s0['prod_rank'], case['gold'], k) for k in (1, 3, 10)},
                     'model': {k: recall(picks, case['gold'], k) for k in (1, 3, 8)},
                     'merged': {k: recall(merged, case['gold'], k) for k in (1, 3, 10)},
                     'pool_has_gold': any(g in s0['pool'] for g in case['gold'])})
    write_json(RUNS / 'results' / 'identify_metrics.json', rows)
    n, g = len(rows), sum(len(r['gold']) for r in rows)
    print(f'cases {n}, cited articles {g}, cases with a cited article in the pool {sum(r["pool_has_gold"] for r in rows)}')
    for arm in ('prod', 'model', 'merged'):
        for k in sorted(rows[0][arm]):
            first = sum(r[arm][k][0] > 0 for r in rows)
            arts = sum(r[arm][k][0] for r in rows)
            full = sum(r[arm][k][2] for r in rows)
            print(f'{arm:7s} top{k:<2d} any cited {first}/{n}  articles {arts}/{g}  all cited {full}/{n}')
    print('model picks dropped by the quote/pool check:', sum(r['dropped'] for r in rows),
          'of', sum(len(r['raw_picks']) for r in rows), '| scope other:', sum(r['scope'] == 'other' for r in rows))


if __name__ == '__main__':
    main()
