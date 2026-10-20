import sys, json
sys.path.insert(0, '/tmp/jev-bench/scripts')
from corpus import articles
import jevrun
arts = articles()
cases = {c['id']: c for c in json.load(open('/tmp/jev-bench/data/cases.json'))}
st2 = json.load(open('/tmp/jev-bench/out/jev_stage2.json'))['stage2_exh60']
P = {}
for line in open(jevrun.CACHE):
    r = json.loads(line)
    if r['qkey']=='govern_exhaustive': P[(r['case'], r['art'])] = r['p']
rows=[]
for cid,c in cases.items():
    for g in c['gold']:
        rank = st2[cid].index(g)+1
        rows.append((P[(cid,g)], rank, cid, g))
rows.sort()
print('Lowest-probability gold articles (exhaustive p, final rank):')
for p,rank,cid,g in rows[:14]:
    print(f'p={p:.3f} rank={rank:4d} {cid[:44]:44s} gold {g:12s} {arts[g]["title"][:45]:45s} | Q: {cases[cid]["query"][:110]}')
