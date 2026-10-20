import sys, json
sys.path.insert(0, '/tmp/jev-bench/scripts')
from corpus import bm25_rank
from metrics import evaluate, fmt
cases = json.load(open('/tmp/jev-bench/data/cases.json'))
ranked = {c['id']: bm25_rank(c['query']) for c in cases}
json.dump(ranked, open('/tmp/jev-bench/out/bm25_ranked.json','w'))
print(fmt('BM25 (all cases)', evaluate(ranked, cases)))
for t in ('variance','spv','interpretation','bulletin'):
    sub=[c for c in cases if c['type']==t]
    if sub: print(fmt(f'BM25 {t} (n={len(sub)})', evaluate(ranked, sub)))
