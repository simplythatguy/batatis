import json, re, sys, sqlite3, collections
idx = json.load(open(sys.argv[1])); db = sys.argv[2]; out = sys.argv[3]
c = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
art_ids = {r[0] for r in c.execute("select id from provisions where doc='NBC-AE' and division='B' and level='article'")}
num = re.compile(r'\b(?:Div(?:ision)?\.?\s*[ABC],?\s*)?(?:(?:Articles?|Sentences?|Clauses?|Subsections?|Sections?|Tables?|Parts?)\s+)?\d+(?:\.\d+)+\.?(?:\(\d+\))*(?:\([a-z]\))*', re.I)
cases, seen = [], set()
for r in idx:
    t = r.get('type')
    if t in ('variance','spv','policy'):
        refs = r.get('articles_varied') or []
        ok_status = ('same-number-present','topic-successor-found-equivalence-unverified')
    elif t in ('interpretation','bulletin') and r.get('code_edition') == 'NBC(AE) 2023':
        refs = (r.get('articles_varied') or []) + (r.get('articles_referenced') or [])
        ok_status = ('same-number-present',)
    else:
        continue
    gold = set()
    for a in refs:
        if a.get('status') not in ok_status: continue
        m = re.match(r'Div B, Article\s+([\d.]+)', a.get('ae2023_provision') or '')
        if m and m.group(1) in art_ids: gold.add(m.group(1))
    if not gold: continue
    title = re.sub(r'^\s*[\w-]*\d[\w-]*\s*[-–:]\s*', '', r.get('title') or '')
    text = f"{title}. {r.get('summary') or ''} Applies to: {r.get('applies_to') or ''}"
    text = num.sub('[ref]', text)
    text = re.sub(r'(\[ref\][\s,;and]*)+', '[ref] ', text).strip()
    key = re.sub(r'\W+', ' ', text.lower())
    if key in seen: continue
    seen.add(key)
    cases.append(dict(id=r['id'], type=t, edition=r.get('code_edition'), query=text, gold=sorted(gold)))
json.dump(cases, open(out,'w'), indent=1)
print(len(cases), 'cases;', dict(collections.Counter(x['type'] for x in cases)))
print('gold sizes:', dict(sorted(collections.Counter(len(x['gold']) for x in cases).items())))
print('parts of gold:', dict(collections.Counter(g.split('.')[0] for x in cases for g in x['gold'])))
leak = [x['id'] for x in cases if re.search(r'\d+\.\d+\.\d+', x['query'])]
print('queries still containing numbers like a.b.c:', leak)
