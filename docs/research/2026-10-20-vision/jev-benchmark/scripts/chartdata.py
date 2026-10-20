import sys, json
sys.path.insert(0, '/tmp/jev-bench/scripts')
from metrics import evaluate
cases = json.load(open('/tmp/jev-bench/data/cases.json'))
bm = json.load(open('/tmp/jev-bench/out/bm25_ranked.json'))
jr = json.load(open('/tmp/jev-bench/out/jev_ranked.json')); s2 = json.load(open('/tmp/jev-bench/out/jev_stage2.json'))
ks = (1,3,5,10,20,50,100,200)
out = {}
for name, r in [('bm25', bm), ('rerank', jr['rerank60']), ('screen', s2['stage2_exh60'])]:
    m = evaluate(r, cases, ks)
    out[name] = {'recall': [round(m[f'recall@{k}'], 3) for k in ks], 'hit': [round(m[f'hit@{k}'], 3) for k in ks], 'mrr': round(m['mrr'], 3)}
print(json.dumps({'ks': ks, **out}))
