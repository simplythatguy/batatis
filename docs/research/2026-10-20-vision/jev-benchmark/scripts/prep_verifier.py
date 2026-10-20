import sys, json, random
sys.path.insert(0, '/tmp/jev-bench/scripts')
from corpus import articles
arts = articles()
cases = [c for c in json.load(open('/tmp/jev-bench/data/cases.json')) if c['type'] in ('variance','spv')]
st2 = json.load(open('/tmp/jev-bench/out/jev_stage2.json'))['stage2_exh60']
rnd = random.Random(20261020)
manifest = []
for n, c in enumerate(cases, 1):
    cand = st2[c['id']][:40]
    shuffled = cand[:]; rnd.shuffle(shuffled)
    lines = [f"# Case V{n:02d}", "", "## Proposal (description of the alternative solution or situation; article numbers were removed and shown as [ref])", "", c['query'], "",
             "## Candidate NBC(AE) 2023 2nd printing, Division B articles (order is random)", ""]
    for i, a in enumerate(shuffled, 1):
        x = arts[a]
        body = x['text'][:900] + ('...' if len(x['text']) > 900 else '')
        lines.append(f"### C{i}: Article {a} {x['title']}  (Part {x['part']} > {x['section']} > {x['subsection']})")
        lines.append(body); lines.append("")
    open(f'/tmp/jev-bench/verifier/case-V{n:02d}.md','w').write('\n'.join(lines))
    manifest.append({'case': f'V{n:02d}', 'id': c['id'], 'gold': c['gold'], 'gold_in_candidates': [g for g in c['gold'] if g in cand]})
json.dump(manifest, open('/tmp/jev-bench/out/verifier_manifest.json','w'), indent=1)  # gold stays outside the verifier folder
print(len(manifest), 'cases written;', sum(1 for m in manifest if m['gold_in_candidates']), 'have >=1 gold in candidates;',
      sum(len(m['gold_in_candidates']) for m in manifest), 'of', sum(len(m['gold']) for m in manifest), 'gold articles in candidates')
