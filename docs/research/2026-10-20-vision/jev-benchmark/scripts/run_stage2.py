import sys, json
sys.path.insert(0, '/tmp/jev-bench/scripts')
from corpus import articles
from metrics import evaluate, fmt
import jevrun
arts = articles(); all_ids = list(arts)
cases = json.load(open('/tmp/jev-bench/data/cases.json'))
bm = json.load(open('/tmp/jev-bench/out/bm25_ranked.json'))
jr = json.load(open('/tmp/jev-bench/out/jev_ranked.json'))
exh = jr['exhaustive']; rer = jr['rerank60']
# probabilities from cache
P = {}
for line in open(jevrun.CACHE):
    r = json.loads(line)
    if r['qkey']=='govern_exhaustive': P[(r['case'], r['art'])] = r['p']
# threshold curve (exhaustive)
print('threshold  recall  mean_pass  max_pass')
for t in [0.9,0.8,0.7,0.6,0.5,0.4,0.3,0.2,0.15,0.1,0.07,0.05,0.03,0.02,0.01]:
    rec=0; npass=[]
    for c in cases:
        passed={a for a in all_ids if P[(c['id'],a)]>=t}; npass.append(len(passed))
        rec += len(passed & set(c['gold']))/len(c['gold'])
    print(f'{t:>8} {rec/len(cases):7.3f} {sum(npass)/len(npass):10.1f} {max(npass):9d}')
# stage 2: exhaustive top-60 -> comparative re-judge in one batch
st2 = {}
for c in cases:
    cand = exh[c['id']][:60]
    pr = jevrun.judge(c, arts, cand, tag='govern_stage2_exh60', workers=1)
    st2[c['id']] = sorted(cand, key=lambda a: -pr[a]) + exh[c['id']][60:]
# union stage: BM25 top30 + exhaustive top30 -> re-judge together
un = {}
for c in cases:
    cand = list(dict.fromkeys(bm[c['id']][:30] + exh[c['id']][:60]))[:60]
    pr = jevrun.judge(c, arts, cand, tag='govern_stage2_union60', workers=1)
    rest = [a for a in exh[c['id']] if a not in pr]
    un[c['id']] = sorted(cand, key=lambda a: -pr[a]) + rest
def rrf(*lists, k=60):
    s={}
    for L in lists:
        for i,a in enumerate(L): s[a]=s.get(a,0)+1/(k+i+1)
    return sorted(s, key=lambda a:-s[a])
fus = {c['id']: rrf(rer[c['id']], exh[c['id']]) for c in cases}
json.dump({'stage2_exh60': st2, 'union60': un, 'rrf': fus}, open('/tmp/jev-bench/out/jev_stage2.json','w'))
print(fmt('BM25', evaluate(bm, cases)))
print(fmt('BM25 top60 -> Jev rerank', evaluate(rer, cases)))
print(fmt('Jev exhaustive', evaluate(exh, cases)))
print(fmt('Exhaustive -> top60 rejudge', evaluate(st2, cases)))
print(fmt('BM25 30 + Exh -> rejudge 60', evaluate(un, cases)))
print(fmt('RRF(rerank, exhaustive)', evaluate(fus, cases)))
print('USAGE', {k:v for k,v in jevrun.USAGE.items() if k!='latency_ms'})
