import sys, json, time
sys.path.insert(0, '/tmp/jev-bench/scripts')
from corpus import articles
from metrics import evaluate, fmt
import jevrun
arts = articles(); all_ids = list(arts)  # code order
cases = json.load(open('/tmp/jev-bench/data/cases.json'))
bm = json.load(open('/tmp/jev-bench/out/bm25_ranked.json'))
t0 = time.time()
rer, exh = {}, {}
for i, c in enumerate(cases):
    cand = bm[c['id']][:60]
    pr = jevrun.judge(c, arts, cand, tag='govern_rerank60')
    rer[c['id']] = sorted(cand, key=lambda a: -pr[a]) + [a for a in bm[c['id']] if a not in pr]
    pe = jevrun.judge(c, arts, all_ids, tag='govern_exhaustive', workers=8)
    exh[c['id']] = sorted(all_ids, key=lambda a: -pe[a])
    print(f'{i+1}/{len(cases)} {c["id"]} done; requests {jevrun.USAGE["requests"]} tokens {jevrun.USAGE["input_tokens"]} errors {jevrun.USAGE["errors"]} elapsed {time.time()-t0:.0f}s', flush=True)
json.dump({'rerank60': rer, 'exhaustive': exh}, open('/tmp/jev-bench/out/jev_ranked.json','w'))
lat = sorted(jevrun.USAGE['latency_ms']); 
print('USAGE', {k: v for k, v in jevrun.USAGE.items() if k!='latency_ms'}, 'latency p50/p95 ms', lat[len(lat)//2] if lat else None, lat[int(len(lat)*.95)] if lat else None)
print(fmt('BM25', evaluate(bm, cases)))
print(fmt('BM25 top60 -> Jev rerank', evaluate(rer, cases)))
print(fmt('Jev exhaustive (2080 arts)', evaluate(exh, cases)))
