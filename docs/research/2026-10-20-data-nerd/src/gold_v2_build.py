import json, re, sqlite3, subprocess, hashlib, sys
DB='/workspace/batatis/codedb-snapshot/codedb.sqlite'; c=sqlite3.connect(DB); ERR=[]
LABEL='model-checked, not human-verified'; R='/workspace/batatis/research/'
PDF='/workspace/batatis-pr16/reference/codes/NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2.pdf'
n=lambda s: re.sub(r'\s+',' ',(s or '')).strip()
def prov(pid,div='B'):
    r=c.execute('select pdf_page,text,article_title from provisions where division=? and id=?',(div,pid)).fetchone()
    if not r: ERR.append('missing '+pid)
    return r
def G(pid,quote,role,tier,conf,why,div='B'):
    r=prov(pid,div)
    if r and n(quote) not in n(r[1]): ERR.append('quote mismatch '+pid)
    art=re.match(r'^(\d+\.\d+\.\d+\.\d+\.)',pid).group(1); a=prov(art,div)
    return dict(division=div,provision=pid,article=art,article_title=(a[2] if a and a[2] else c.execute('select title from provisions where division=? and id=?',(div,art)).fetchone()[0]),role=role,tier=tier,confidence=conf,quote=quote,pdf_page=r[0] if r else None,reasoning=why,label=LABEL)
def NOTE(nid,quote):
    r=c.execute("select pdf_page,text from notes where division='B' and note_id=?",(nid,)).fetchone()
    if not r or n(quote) not in n(r[1]): ERR.append('note mismatch '+nid)
    return dict(note=nid,pdf_page=r[0] if r else None,quote=quote,label=LABEL)
# ---- Appendix C climate data, parsed from the official 2nd-printing PDF
def page_txt(p): return subprocess.run(['pdftotext','-layout','-f',str(p),'-l',str(p),PDF,'-'],capture_output=True,text=True).stdout
num=re.compile(r'^[−\-]?\d+(\.\d+)?$')
C2={}; C3={}; c2pages=set(); c3pages=set()
for p in range(660,676):
    t=page_txt(p)
    for ln in t.split('\n'):
        k=ln.split()
        if len(k)>=17 and all(num.match(x) for x in k[-16:]) and not num.match(k[0]):
            C2[' '.join(k[:-16])]=dict(page=p,HDD=int(k[-11]),moisture_index=float(k[-7]),hwp_1_50=float(k[-1])); c2pages.add(p)
        elif len(k)>=4 and all(num.match(x) for x in k[-3:]) and not num.match(k[0]) and 'Table C-3' in t:
            C3[' '.join(k[:-3])]=dict(page=p,Sa02=float(k[-1])); c3pages.add(p)
if not ('Table C-2' in page_txt(min(c2pages)) and len(C2)>100): ERR.append('Table C-2 parse')
mi_max=max(v['moisture_index'] for v in C2.values()); hdd_min=min(v['HDD'] for v in C2.values())
coch=dict(C2['Cochrane'], **{'Sa02':C3['Cochrane']['Sa02'],'Sa02_page':C3['Cochrane']['page']})
climate=dict(source='NBC(AE) 2023 2nd printing, Division B Appendix C, Table C-2 "Climatic Design Data for Selected Locations in Alberta" and Table C-3 "Seismic Design Data for Selected Locations in Alberta for Part 9 Design"', pdf=PDF, pdf_sha256_prefix=hashlib.sha256(open(PDF,'rb').read()).hexdigest()[:16],
  table_C2_pages=sorted(c2pages), table_C3_pages=sorted(c3pages), C2_locations_parsed=len(C2), C2_moisture_index_max=mi_max, C2_HDD_min=hdd_min,
  cochrane=coch, method='pdftotext -layout row parse (16 numeric columns; HDD = col 6, moisture index = col 10, 1/50 hourly wind pressure = last); '+LABEL)

src=json.load(open(R+'identify-gold-proposals.json'))
HIGH_IDS=['dev-006','dev-010','dev-011','dev-015']
high={}
for k in HIGH_IDS:
    ents=src['detail'][k]
    for e in ents:
        r=prov(e['provision'])
        if r and n(e['quote']) not in n(r[1]): ERR.append('v1 quote mismatch '+e['provision'])
        if r and r[0]!=e['pdf_page']: ERR.append('v1 page mismatch '+e['provision'])
    high[k]=dict(status='high (adopted in v1)', gold=[e for e in ents if e['tier']=='primary'], candidates=[e for e in ents if e['tier']!='primary'])

# ---- dev-009: upgraded
high['dev-009']=dict(status='upgraded: medium -> high (Article level)', gold=[
  G('9.27.2.2.(5)','exterior walls exposed to precipitation shall be protected against precipitation ingress by an exterior cladding assembly consisting of a first plane of protection and a second plane of protection incorporating a capillary break, where a) the number of degree-days is less than 3400 and the moisture index is greater than 0.90, or b) the number of degree-days is 3400 or more, and the moisture index is greater than 1.00.','benchmark','primary','high (Article 9.27.2.2.); pinpoint (5) medium',
    'The inspectors\' "gap behind the cladding" is the capillary break, and the Sentence that says when one is required is 9.27.2.2.(5). Scoring is at Article level, and every reading of the case (capillary break required or not, the (6) exceptions, what counts as a break under (1)) sits in Article 9.27.2.2., so the Article is high-confidence. Whether (5) is triggered depends on the site climate. The Table C-2 values are recorded below for the officer; the gold does not decide whether the panel complies.')],
 candidates=[
  G('9.27.2.2.(4)','Exterior walls exposed to precipitation shall be protected against precipitation ingress by an exterior cladding assembly consisting of a first plane of protection and a second plane of protection, where such walls enclose spaces of residential occupancy','scope','secondary','high','Houses: the two-plane requirement applies regardless of climate; same Article.'),
  G('9.27.2.2.(1)','a cladding assembly is deemed to have a capillary break between the cladding and the backing assembly, where a) there is a drained and vented air space not less than 9.5 mm deep behind the cladding','definition','secondary','high','What counts as a capillary break; same Article.'),
  G('9.27.2.2.(6)','the first and second planes of protection need not incorporate a capillary break, where a) it can be shown that omitting the capillary break will not adversely affect the performance of the building assemblies','exception','secondary','medium','The route the manufacturer\'s evidence would target if (5) applies; same Article.')],
 supporting=dict(note=NOTE('A-9.27.2.','Part 5 and Part 9 of the NBC(AE) recognize that mass walls and face-sealed, concealed barrier and rainscreen assemblies have their place in the Canadian context.'),
   climate_facts=f'Table C-2 (PDF pages {min(c2pages)}-{max(c2pages)}): {len(C2)} Alberta locations parsed. Lowest degree-days {hdd_min} (so every listed location is in branch (5)(b), "3400 or more"); highest moisture index {mi_max} (the (5)(b) threshold is "greater than 1.00"). These are recorded facts for the officer and are not a compliance finding. A site not listed in Table C-2 needs its own values.'),
 missing_to_confirm=['site location (if not in Table C-2)','backing materials (for 9.27.2.2.(6)(c))'],
 evidence_basis='case description + known_facts + codedb + Appendix C of the official PDF; the case gold/should_cite fields were not used as evidence')

kept={'dev-005':dict(status='not upgraded', confidence='low', gold_proposed=[G('9.10.14.5.(1)','each exposing building face and any exterior wall located above an exposing building face that encloses an attic or roof space shall be constructed in conformance with Table 9.10.14.5.-A','benchmark','primary','low','Part 9 branch.')],
   competing=[G('3.2.3.7.(1)','the fire-resistance rating, construction and cladding for exposing building faces of buildings or fire compartments of Group A, B, C, D or Group F, Division 3 occupancy classification shall comply with Table 3.2.3.7.','candidate','secondary','low','Part 3 branch.'),
              G('9.10.15.1.(1)','buildings that contain only dwelling units and have no dwelling unit above another dwelling unit','scope','secondary','low','If no dwelling unit is above another, 9.10.15. (not 9.10.14.) governs.')],
   scope_quotes=[G('1.3.3.3.(1)','of 3 storeys or less in building height, having a building area not exceeding 600 m²','scope','scope','n/a','Part 9 limits',div='A')],
   why_not_high='Three different Articles are possible, depending on facts the description does not give: Part 3 Div B 3.2.3.7. if the building is over 3 storeys or over 600 m² (Div A 1.3.3.3.(1)); Div B 9.10.15.5. if no dwelling unit is above another (Div B 9.10.15.1.(1)); otherwise Div B 9.10.14.5. "Small apartment buildings" fixes none of these.',
   missing_facts=['building height in storeys','building area','whether any dwelling unit is above another','limiting distance / unprotected-opening %']),
 'dev-007':dict(status='not upgraded', confidence='medium', gold_proposed=[G('9.27.3.3.(1)','Except as provided in Articles 9.27.3.4. to 9.27.3.6., at least one layer of sheathing membrane shall be applied beneath cladding.','benchmark','primary','medium','Omitting the housewrap departs from this Sentence unless an exception Article applies.')],
   competing=[G('9.27.3.4.(1)','Where non-wood-based rigid exterior insulating sheathing, or exterior insulating sheathing with an integral sheathing membrane is installed, a separate sheathing membrane is not required.','candidate','secondary','medium','If the board qualifies, no membrane is required and the departure moves to the joints in 9.27.3.4.(2) (butted, unsealed).'),
              G('9.27.3.4.(2)','the joints of sheathing panels not subject to moisture deterioration shall be i) sealed at all joints, or ii) lapped or tongue and groove, and detailed to ensure drainage of water to the exterior','candidate','secondary','medium','Joint rule if 9.27.3.4.(1) applies.')],
   supporting=[NOTE('A-9.27.3.4.(2)','Butt joints can drain to either side and so should not be used unless they are sealed.')],
   why_not_high='The scored Article flips between 9.27.3.3. and 9.27.3.4. depending on whether the specified board is "non-wood-based rigid exterior insulating sheathing" (9.27.3.4.(1)). The applicant calls it "semi-rigid". The code does not define "rigid", and codedb has no Note on 9.27.3.4.(1) (only A-9.27.3.4.(2) on joints). No public Alberta guidance was found in this pass that classifies semi-rigid mineral wool board.',
   missing_facts=['product data sheet / material standard and rigidity classification of the mineral wool board']),
 'dev-012':dict(status='not upgraded (raised low -> medium)', confidence='medium', gold_proposed=[G('9.23.13.1.(2)','Bracing to resist lateral loads shall be designed and constructed as follows','benchmark','primary','medium','Low-to-moderate-force bracing rule; the site values now fall in this Article\'s scope.'),G('9.23.13.1.(1)','This Article applies in locations where the seismic spectral acceleration, Sa(0.2), is not more than 0.70 and the 1-in-50 hourly wind pressure is less than 0.80 kPa.','scope','primary','high (for the climate branch)','Cochrane values below.')],
   competing=[G('9.23.1.1.(1)','This Section applies to constructions where wall, floor and roof planes are generally comprised of lumber frames of small repetitive structural members, or engineered components','scope','secondary','medium','Whether a SIP house is inside Section 9.23. at all.'),
              G('9.4.1.1.(1)','be designed according to Part 4 using the loads and deflection and vibration limits specified in i) Part 9, or ii) Part 4.','candidate','secondary','medium','Engineering-design route if Section 9.23. does not apply to the SIP system.')],
   supporting=[NOTE('A-9.23.1.1.','The prescriptive requirements in Section 9.23. apply only to standard light wood-frame construction.')],
   climate_resolved=f"Cochrane: Table C-3 Sa(0.2) = {coch['Sa02']} (PDF page {coch['Sa02_page']}); Table C-2 1-in-50 hourly wind pressure = {coch['hwp_1_50']} kPa (PDF page {coch['page']}). Both are within the 9.23.13.1.(1) limits, so the high-force branch 9.23.13.2. is not the scoped Article for this town.",
   why_not_high='The climate fact is resolved, but the scope fact is not. If the SIP system counts as standard light wood-frame construction, 9.23.13.1. is the benchmark; if not, Note A-9.23.1.1. sends design to Part 4 (9.4.1.1.(1)(c)). The description gives no product evaluation. Public SIP documents found (an Ontario Minister\'s ruling cited by a manufacturer; CCMC listings) are not Alberta and not for this product, so they were not used.',
   missing_facts=['SIP product and any CCMC evaluation number','whether the panel system is framed (studs/splines) or stressed-skin only','site address within Cochrane (Table C-2/C-3 give town values)']),
 'dev-020':dict(status='unchanged: no defensible gold', confidence=None, why_not_high='Part 3 vs Part 9 cannot be decided (v1 finding, not re-opened).')}
if ERR: print('\n'.join(ERR)); sys.exit(1)
order=['dev-006','dev-009','dev-010','dev-011','dev-015']
patches=[dict(file=f'evals_dev/cases/{k}.json',op='add',path='/gold/identify_gold',value=[dict(division=g['division'],provision=g['provision'],role=g['role'],confidence='high',label=LABEL) for g in high[k]['gold']]) for k in order]
patches+=[dict(file=f'evals_dev/cases/{k}.json',op='add',path='/gold/identify_gold_candidates',value=[dict(division=g['division'],provision=g['provision'],role=g['role'],confidence=v['confidence'],label=LABEL) for g in v['gold_proposed']+v['competing']]) for k,v in kept.items() if k!='dev-020']
out=dict(meta=dict(title='Identify gold v2: high-confidence group for BAT-26', generated='2026-10-20 (America/Edmonton, MDT UTC-6)', label=LABEL, supersedes='research/identify-gold-proposals.{md,json} (v1, kept unchanged)',
  codedb_snapshot=dict(path=DB,sha256=hashlib.sha256(open(DB,'rb').read()).hexdigest()), edition='NBC(AE) 2023 2nd printing', scoring='Article level (engine/identify/benchmark.py _article()); must_cite stays empty on ask cases (SCHEMA rule 3); gold goes in gold.identify_gold',
  high_group=order, high_n=len(order), scored_n_if_adopted=11+len(order), guardrails='Golds name the provision at issue; they never say the design complies or fails. Evidence = case description + known_facts + codedb + public sources; case gold/should_cite/seed fields were not used as evidence.', builder='research/src/gold_v2_build.py'),
 climate_data=climate, high=high, not_high=kept, patches=patches)
json.dump(out,open(R+'identify-gold-v2.json','w'),ensure_ascii=False,indent=2)
# ---- md
L=[f"# {out['meta']['title']}\n",f"**Label: {LABEL}.** Generated {out['meta']['generated']} by Data Nerd. Read-only. Codedb {out['meta']['edition']} (sha256 `{out['meta']['codedb_snapshot']['sha256'][:12]}…`). v1 (`identify-gold-proposals.*`) is kept unchanged.\n",
 f"**High group: n = {len(order)}** ({', '.join(order)}). If Backy adopts it, the scored set grows from 11 to {11+len(order)}. Scoring is at Article level. `must_cite` stays empty on these ask cases (SCHEMA rule 3); the gold goes in `gold.identify_gold`.\n",
 f"**Guardrails.** {out['meta']['guardrails']}\n","## Summary\n","| case | result | primary gold (Article) | confidence | missing fact |","|---|---|---|---|---|"]
for k in order:
    g=high[k]['gold'][0]; L.append(f"| {k} | {high[k]['status']} | Div B {g['provision']} ({g['article']}, PDF p.{g['pdf_page']}) | {g['confidence']} | — |")
for k,v in kept.items():
    g=(v.get('gold_proposed') or [None])[0]
    L.append(f"| {k} | {v['status']} | {('Div B '+g['provision']+' ('+g['article']+', PDF p.'+str(g['pdf_page'])+')') if g else '—'} | {v['confidence']} | {'; '.join(v.get('missing_facts',[])) or '—'} |")
def ent(e): return f"- **Div {e['division']} {e['provision']}** ({e['article_title']}, PDF p.{e['pdf_page']}). Role `{e['role']}`, tier {e['tier']}, confidence **{e['confidence']}**. *{LABEL}*\n  - Quote: \"{e['quote']}\"\n  - Reasoning: {e['reasoning']}"
L.append("\n## Upgraded: dev-009\n")
for e in high['dev-009']['gold']+high['dev-009']['candidates']: L.append(ent(e))
s=high['dev-009']['supporting']; L.append(f"- Note {s['note']['note']} (on PDF page {s['note']['pdf_page']}): \"{s['note']['quote']}\"\n- Climate facts: {s['climate_facts']}\n- Still to confirm (does not change the Article): {', '.join(high['dev-009']['missing_to_confirm'])}.\n- Evidence basis: {high['dev-009']['evidence_basis']}.")
for k in ['dev-005','dev-007','dev-012']:
    v=kept[k]; L.append(f"\n## Not upgraded: {k} ({v['confidence']})\n")
    for e in v['gold_proposed']+v['competing']+v.get('scope_quotes',[]): L.append(ent(e))
    for s_ in v.get('supporting',[]): L.append(f"- Note {s_['note']} (PDF p.{s_['pdf_page']}): \"{s_['quote']}\"")
    if v.get('climate_resolved'): L.append(f"- Resolved: {v['climate_resolved']}")
    L.append(f"- **Why not high:** {v['why_not_high']}\n- **Missing fact(s):** {'; '.join(v['missing_facts'])}.")
L.append("\n## Kept from v1 (high)\n")
for k in HIGH_IDS:
    for e in high[k]['gold']: L.append(f"- {k}: "+ent(e)[2:])
L.append(f"\n## Climate data used\n\n{climate['source']}. Table C-2 on PDF pages {min(c2pages)}–{max(c2pages)}; Table C-3 on PDF pages {min(c3pages)}–{max(c3pages)}. Method: {climate['method']}.\n\n## Patches\n\nSee `patches` in the json: `identify_gold` for the {len(order)} high cases and `identify_gold_candidates` for 005/007/012.")
open(R+'identify-gold-v2.md','w').write('\n'.join(L)+'\n'); print('OK', len(order), len(C2), mi_max, hdd_min, coch)
