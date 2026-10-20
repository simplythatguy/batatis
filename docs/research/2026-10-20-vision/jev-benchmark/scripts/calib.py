import sys, json
sys.path.insert(0, '/tmp/jev-bench/scripts')
import jevrun
cases = {c['id']: c for c in json.load(open('/tmp/jev-bench/data/cases.json'))}
S = {}
for line in open(jevrun.CACHE):
    r = json.loads(line)
    if r['qkey']=='govern_stage2_exh60': S.setdefault(r['case'], {})[r['art']] = r['p']
# top-1 selective precision
rows = []
for cid, d in S.items():
    a, p = max(d.items(), key=lambda kv: kv[1]); rows.append((p, a in cases[cid]['gold']))
rows.sort(reverse=True)
print('Top-1 pick: precision when only answering above a confidence threshold')
for t in [0.9, 0.8, 0.7, 0.6, 0.5, 0.0]:
    sel = [ok for p, ok in rows if p >= t]
    print(f'  p>={t:.1f}: answered {len(sel):2d}/{len(rows)} cases, precision {sum(sel)/max(1,len(sel)):.2f}')
# all pairs: reliability bins
pairs = [(p, a in cases[cid]['gold']) for cid, d in S.items() for a, p in d.items()]
print('All stage-2 candidate judgments, reliability (share that are gold) per probability bin:')
for lo, hi in [(0.9,1.01),(0.8,0.9),(0.7,0.8),(0.5,0.7),(0.3,0.5),(0.1,0.3),(0.0,0.1)]:
    b = [ok for p, ok in pairs if lo <= p < hi]
    print(f'  [{lo:.1f},{min(hi,1):.1f}): n={len(b):4d} gold-rate {sum(b)/max(1,len(b)):.2f}')
