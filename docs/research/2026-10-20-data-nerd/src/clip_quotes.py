"""Clip verbatim quotes >25 words (Backy, Oct 20 2026). Run AFTER the builders.
Map: src/clip_map.txt (index<TAB>clip), keyed to the long-quote order in /tmp-independent originals stored in src/clip_originals.json.
Every clipped piece (split on …) is verified to be an exact substring of the original verified quote."""
import json,sys,os
os.chdir(os.path.dirname(os.path.abspath(__file__))+'/..')
orig=json.load(open('src/clip_originals.json',encoding='utf-8'))
m={int(l.split('\t')[0]):l.split('\t',1)[1] for l in open('src/clip_map.txt',encoding='utf-8').read().split('\n') if l}
full2clip={}
for x in orig:
    c=m[x['k']]; ps=[p.strip() for p in c.split('…') if p.strip()]
    assert sum(len(p.split()) for p in ps)<=25, x['k']
    assert all(any(p in o.strip() for o in x['q'].split('…')) for p in ps), x['k']
    full2clip[x['q']]=c
def walk(o,cnt,f):
    if isinstance(o,dict):
        for k,v in list(o.items()):
            if k=='quote' and isinstance(v,str) and v in full2clip:
                o[k]=full2clip[v]; o.setdefault('quote_clipped',True); cnt[f]=cnt.get(f,0)+1
            else: walk(v,cnt,f)
    elif isinstance(o,list):
        for v in o: walk(v,cnt,f)
cnt={};mdcnt={};left=[]
for f in ['carlos-s1-backing','identify-regression','identify-gold-v2','human-review-triggers']:
    d=json.load(open(f+'.json',encoding='utf-8')); walk(d,cnt,f)
    json.dump(d,open(f+'.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
    md=open(f+'.md',encoding='utf-8').read(); n=0
    for q,c in sorted(full2clip.items(),key=lambda kv:-len(kv[0])):
        n+=md.count(q); md=md.replace(q,c)
    open(f+'.md','w',encoding='utf-8').write(md); mdcnt[f]=n
EXTRA=[("Part 4 of Division B is written on the assumption that structural design will be carried out by a registered professional who is qualified to perform such design.","Part 4 … is written on the assumption that structural design will be carried out by a registered professional who is qualified to perform such design.")]
for full,c in EXTRA:
    ps=[p.strip() for p in c.split('…') if p.strip()]; assert all(p in full for p in ps) and sum(len(p.split()) for p in ps)<=25
    for f in ['human-review-triggers']:
        for ext in ['.json','.md']:
            t=open(f+ext,encoding='utf-8').read()
            if full in t: cnt[f+' (notes)']=cnt.get(f+' (notes)',0)+t.count(full)//(2 if ext=='.json' else 1) if ext=='.json' else cnt.get(f+' (notes)',0); open(f+ext,'w',encoding='utf-8').write(t.replace(full,c))
print('json clipped',cnt); print('md replacements',mdcnt)

# Post-fix (validator superseded_edition): label the 2012 appeal quote as historical context, outside the quoted words.
A='  > The submission of Schedules for all Professional Involvement is required to comply with the ABC 2006.'
t=open('human-review-triggers.md',encoding='utf-8').read()
if A in t and A+' — (historical context, previous Alberta Edition)' not in t:
    open('human-review-triggers.md','w',encoding='utf-8').write(t.replace(A,A+' — (historical context, previous Alberta Edition)'))
