import sys, json
sys.path.insert(0, '/tmp/jev-bench/scripts')
from metrics import evaluate, fmt
man = {m['case']: m for m in json.load(open('/tmp/jev-bench/out/verifier_manifest.json'))}
ans = [json.loads(l) for l in open('/tmp/jev-bench/verifier/answers.jsonl') if l.strip()]
ans = {a['case']: a for a in ans}
cases = [{'id': c, 'gold': man[c]['gold']} for c in sorted(ans)]
st2 = json.load(open('/tmp/jev-bench/out/jev_stage2.json'))['stage2_exh60']
def norm(x): 
    x = x.strip().rstrip('.') + '.'
    return x
ver = {c: [norm(r['article']) for r in ans[c].get('ranked', [])] for c in ans}
jev = {c: st2[man[c]['id']] for c in ans}
# verifier + outside suggestions appended (scored separately)
ver_out = {c: ver[c] + [norm(o['article']) for o in ans[c].get('outside', [])] for c in ans}
ks = (1, 2, 3, 5)
print(f'n={len(cases)} cases scored')
print(fmt('Jev 2-stage (same cases)', evaluate(jev, cases, ks), ks))
print(fmt('Sonnet verifier (top-40 Jev shortlist)', evaluate(ver, cases, ks), ks))
print(fmt('Verifier + outside picks', evaluate(ver_out, cases, ks), ks))
# precision of the verifier's top pick by its own p
rows = []
for c in ans:
    r = ans[c].get('ranked', [])
    if r: rows.append((r[0].get('p', 0), norm(r[0]['article']) in man[c]['gold'], c))
for t in (0.9, 0.8, 0.0):
    sel = [ok for p, ok, _ in rows if p >= t]
    print(f'verifier top-1 with p>={t}: {sum(sel)}/{len(sel)} correct')
outs = [(c, o['article'], norm(o['article']) in man[c]['gold']) for c in ans for o in ans[c].get('outside', [])]
print('outside suggestions:', len(outs), 'of which gold:', sum(1 for *_, ok in outs if ok))
missing_in_shortlist = [c for c in ans if not man[c]['gold_in_candidates']]
print('cases with no gold in shortlist:', missing_in_shortlist, [ (o['article']) for c in missing_in_shortlist for o in ans[c].get('outside', [])])
for c in sorted(ans):
    top = ver[c][:1]; g = man[c]['gold']
    print(f'  {c} gold={g} verifier_top={top} jev_top={jev[c][:1]} {"OK" if top and top[0] in g else "--"}')
