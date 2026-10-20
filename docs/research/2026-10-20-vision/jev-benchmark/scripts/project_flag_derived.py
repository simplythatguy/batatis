import sys, json, time
sys.path.insert(0, '/tmp/jev-bench/scripts')
from corpus import articles
import jevrun
arts = articles()
# deterministic scope first: Part 9 building -> Part 9 articles only (cross-references would be added by code)
ids = [a for a in arts if arts[a]['part'] in ('9', 9)]
project = ("Project facts (from drawings and the applicant): new rowhouse building in Calgary, Alberta; 4 houses in a row, "
  "each house has a secondary suite in the basement; 2 storeys plus basement; wood-frame; Part 9 residential; no sprinklers; "
  "party walls between houses are 1 h fire separations (not firewalls); forced-air heating with ducts serving both suites; "
  "basement suite has 1 bedroom with a window, an exterior door at the rear, a bathroom and a kitchen; smoke alarms shown in living room and hall; "
  "ceiling between suite and upper dwelling unit not specified; DERIVED BY CODE: the building contains more than 2 houses with a secondary suite, and the party walls separating them are not firewalls; building on its own lots with limiting distance over 1.2 m at the ends.")
case = {'id': 'demo-rowhouse', 'query': project}
jevrun.QUESTIONS['flag'] = ("A plan reviewer would likely raise an issue under Article {L} for the project in `proposal`: the design as described "
                            "appears not to meet this article, or the drawings omit information needed to check it.")
t0 = time.time()
P = jevrun.judge(case, arts, ids, qname='flag', tag='flag_demo_rowhouse_p9_derived', workers=8)
print('Part 9 articles screened:', len(ids), '| wall s', round(time.time()-t0,1), '| tokens', jevrun.USAGE['input_tokens'])
for t in (0.9, 0.8, 0.7, 0.5):
    print(f'p>={t}: {sum(1 for v in P.values() if v>=t)} articles')
top = sorted(P.items(), key=lambda kv: -kv[1]); rank = {a:i+1 for i,(a,_) in enumerate(top)}
watch = ['9.10.11.2.','9.10.13.13.','9.10.9.16.','9.9.10.1.','9.10.19.3.','9.10.19.5.','9.11.1.1.','9.10.11.1.']
print('ranks of expected issues:', {a: (rank[a], round(P[a],2)) for a in watch})
print('top 25:')
for a,p in top[:25]: print(f'  {p:.2f} {a:12s} {arts[a]["title"][:62]}')
