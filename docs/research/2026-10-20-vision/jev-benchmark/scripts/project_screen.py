import sys, json, time
sys.path.insert(0, '/tmp/jev-bench/scripts')
from corpus import articles
import jevrun
arts = articles(); ids = list(arts)
project = ("Project facts (from drawings and the applicant): new rowhouse building in Calgary, Alberta; 4 houses in a row, "
  "each house has a secondary suite in the basement; 2 storeys plus basement; wood-frame; Part 9 residential; no sprinklers; "
  "party walls between houses are 1 h fire separations (not firewalls); forced-air heating with ducts serving both suites; "
  "basement suite has 1 bedroom with a window, an exterior door at the rear, a bathroom and a kitchen; smoke alarms shown in living room and hall; "
  "ceiling between suite and upper dwelling unit not specified; building on its own lots with limiting distance over 1.2 m at the ends.")
case = {'id': 'demo-rowhouse', 'query': project}
QQ = "Article {L} states a requirement that applies to this building or its parts as described in `proposal`, so a plan reviewer would check it."
jevrun.QUESTIONS['applies'] = QQ
t0 = time.time()
P = jevrun.judge(case, arts, ids, qname='applies', tag='applies_demo_rowhouse', workers=8)
print('wall s', round(time.time()-t0,1), 'tokens', jevrun.USAGE['input_tokens'], 'requests', jevrun.USAGE['requests'])
for t in (0.9, 0.8, 0.7, 0.5, 0.3, 0.1):
    print(f'p>={t}: {sum(1 for v in P.values() if v>=t)} articles')
top = sorted(P.items(), key=lambda kv: -kv[1])
watch = ['9.10.11.2.','9.10.13.13.','9.10.9.16.','9.9.10.1.','9.10.19.3.','9.10.19.5.','9.11.1.1.','9.10.11.1.','9.10.19.1.','9.9.9.1.']
rank = {a:i+1 for i,(a,_) in enumerate(top)}
print('ranks of expected articles:', {a: (rank[a], round(P[a],2)) for a in watch})
print('top 30:')
for a,p in top[:30]: print(f'  {p:.2f} {a:12s} {arts[a]["title"][:60]}')
