"""Where Elephant 1 helps: score a short candidate list, and compare with the Luna verifier on the same list.

The free Elephant route allows 50 requests a day, so the only affordable use is one request over a short
list (10 articles fit in one 16K-token request). For cases whose metadata names NBC(AE) 2023 articles,
the list is built only from what the system has: the provisions the document review cited (resolved in
the code database) and keyword-search hits on the proposal text. Reference articles are never inserted.

    .venv/bin/python -m evals_dev.data_prompts.elephant --run it1-review --split dev --max-requests 45

Writes .dpe-cache/elephant/<run>/<case>.json and prints the separation of reference and other candidates
by Elephant probability, the Luna verifier's picks, and combined hand-over rules.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import corpus, gold, ledger, sut

OUT = ledger.CACHE.parent / 'elephant'
POOL = 10
PROPOSAL_CHARS = 1500


def proposal(case: corpus.Case, result: dict) -> str:
    review = ((result.get('case') or {}).get('intake') or {}).get('review') or {}
    facts = [f['text'] for f in review.get('facts') or []
             if f.get('status') in ('proposed', 'existing', 'condition', 'decided', 'stated')]
    text = case.prompt.split('\n\nAttachments:')[0] + '\n' + '\n'.join(facts)
    return text[:PROPOSAL_CHARS]


def pool(result: dict, query: str, db: Path, arts: dict) -> list[str]:
    from engine.identify.corpus import bm25_rank
    review = ((result.get('case') or {}).get('intake') or {}).get('review') or {}
    out: list[str] = []
    for p in review.get('provisions') or []:
        rid = p.get('resolves_to') or ''
        if p.get('division') == 'B' and rid:
            article = '.'.join(rid.rstrip('.').split('(')[0].rstrip('.').split('.')[:4]) + '.'
            if article in arts and article not in out:
                out.append(article)
    for article in bm25_rank(query, db):
        if len(out) >= POOL:
            break
        if article in arts and article not in out:
            out.append(article)
    return out[:POOL]


def auc(pos: list[float], neg: list[float]) -> float | None:
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return round(wins / (len(pos) * len(neg)), 4)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('--split', default='dev')
    parser.add_argument('--max-requests', type=int, default=45)
    parser.add_argument('--report-only', action='store_true')
    args = parser.parse_args(argv)
    from engine.codes import Codes, default_db
    from engine.identify.corpus import articles
    from engine.identify.llm import OpenAIVerifier
    from engine.identify.providers import transports
    from engine.identify.screen import ELEPHANT_MODEL, Judge
    folder = OUT / args.run
    folder.mkdir(parents=True, exist_ok=True)
    db = default_db()
    codes = Codes(db)
    arts = articles(db)
    runs = ledger.CACHE.parent / 'runs' / args.run / 'cases'
    todo = []
    for case in corpus.select(args.split):
        g = gold.article_gold(case, codes)
        path = runs / f'{case.id}.json'
        if g and path.exists():
            todo.append((case, g, json.loads(path.read_text())))
    if not args.report_only:
        sut.load_env()
        sut.configure(live=True, elephant=True)
        tp = transports('dpe', scoring={'elephant'})
        if tp.elephant is None:
            raise SystemExit('Elephant transport unavailable: ' + str(tp.unavailable))
        used = 0
        for case, g, result in todo:
            out_path = folder / f'{case.id}.json'
            if out_path.exists():
                continue
            if used >= args.max_requests:
                print(f'request cap {args.max_requests} reached')
                break
            query = proposal(case, result)
            ids = pool(result, query, db, arts)
            judge = Judge(tp.elephant, chars=700, model=ELEPHANT_MODEL, method='elephant', question_style='self')
            batches = len(judge.batches(query, arts, ids))
            if used + batches > args.max_requests:
                print(f'request cap {args.max_requests} reached')
                break
            record = {'case_id': case.id, 'gold': g, 'pool': ids, 'query': query}
            try:
                record['elephant'] = judge.judge(query, arts, ids)
            except Exception as error:
                record['elephant_error'] = f'{type(error).__name__}: {getattr(error, "code", error)}'
            used += judge.usage.requests
            try:
                verifier = OpenAIVerifier(tp.openai, arts, model='gpt-6-luna', effort='medium')
                checked = verifier.verify(query, ids)
                record['luna_picks'] = [p.article for p in checked.picks]
            except Exception as error:
                record['luna_error'] = f'{type(error).__name__}'
            out_path.write_text(json.dumps(record, indent=1))
            print(case.id, 'requests', judge.usage.requests, 'gold in pool', len(set(g) & set(ids)), '/', len(g),
                  record.get('elephant_error', ''), flush=True)
        print('elephant requests used this run:', used)
    report(folder)
    return 0


def report(folder: Path) -> None:
    rows = [json.loads(p.read_text()) for p in sorted(folder.glob('*.json'))]
    rows = [r for r in rows if 'elephant' in r]
    pos, neg, in_pool, total_gold = [], [], 0, 0
    for r in rows:
        gold_set = set(r['gold'])
        total_gold += len(gold_set)
        in_pool += len(gold_set & set(r['pool']))
        for a, p in r['elephant'].items():
            (pos if a in gold_set else neg).append(p)
    print(f'cases {len(rows)}, reference articles {total_gold}, in the candidate list {in_pool}')
    print(f'Elephant AUC (reference vs other candidates): {auc(pos, neg)}  n_pos {len(pos)} n_neg {len(neg)}')
    print('threshold  keep_rate  reference_recall_in_pool  precision')
    for t in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
        kept_pos = sum(p >= t for p in pos)
        kept_neg = sum(p >= t for p in neg)
        kept = kept_pos + kept_neg
        print(f'  {t:.1f}      {kept / max(1, len(pos) + len(neg)):.2f}       {kept_pos / max(1, len(pos)):.2f}'
              f'                     {kept_pos / max(1, kept):.2f}')
    luna = [r for r in rows if 'luna_picks' in r]
    tp = sum(len(set(r['luna_picks']) & set(r['gold'])) for r in luna)
    picks = sum(len(r['luna_picks']) for r in luna)
    gold_in_pool = sum(len(set(r['gold']) & set(r['pool'])) for r in luna)
    print(f'Luna verifier: picks {picks}, reference picked {tp} of {gold_in_pool} in pool '
          f'(precision {tp / max(1, picks):.2f}, recall {tp / max(1, gold_in_pool):.2f})')
    for t in (0.3, 0.5, 0.7):
        both = sum(len({a for a in r['luna_picks'] if r['elephant'].get(a, 0) >= t} & set(r['gold'])) for r in luna)
        kept = sum(len({a for a in r['luna_picks'] if r['elephant'].get(a, 0) >= t}) for r in luna)
        print(f'  Luna pick and Elephant >= {t}: kept {kept}, reference {both} '
              f'(precision {both / max(1, kept):.2f}, recall {both / max(1, gold_in_pool):.2f})')


if __name__ == '__main__':
    raise SystemExit(main())
