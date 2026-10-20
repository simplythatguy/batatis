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
   missing_facts=['building height in storeys','building area','whether any dwelling unit is above another','limiting distance / unprotected-opening %'],
   settling_facts=[dict(fact='building height in storeys and building area',settles='Part 9 vs Part 3: Div A 1.3.3.3.(1) (3 storeys or less, 600 m² or less); above either limit, Div B 3.2.3.7.'),
     dict(fact='whether any dwelling unit is above another dwelling unit',settles='Div B 9.10.15. (no unit above another, Div B 9.10.15.1.(1)) vs Div B 9.10.14.'),
     dict(fact='limiting distance and the permitted unprotected-opening %',settles='which row of Table 9.10.14.5.-A (or Div B 9.10.15.5.(2)/(3)) applies, and whether a waiver Sentence such as Div B 9.10.14.5.(3) is in play'),
     dict(fact='complete wall assembly and any CAN/ULC-S134 test of it',settles='whether the tested-assembly routes (Clause 3.1.5.5.(1)(b) via Div B 9.10.14.5.(2) or Div B 9.10.15.5.(2)(c)/(3)(d)) are available; the stated flame-spread rating of 75 is a fact to compare with the 25 limits in those Sentences, not a finding')],
   public_source_check='None settles it. The four facts are project facts and the request is product-wide, so no public source can supply them. NRC CCMC Registry search (2026-10-20) found wood-plastic composite evaluations for decking only (for example CCMC 14114-R, 14154-R, 14342-R), none for siding and none with a CAN/ULC-S134 result. Stays low.'),
 'dev-007':dict(status='not upgraded', confidence='medium', gold_proposed=[G('9.27.3.3.(1)','Except as provided in Articles 9.27.3.4. to 9.27.3.6., at least one layer of sheathing membrane shall be applied beneath cladding.','benchmark','primary','medium','Omitting the housewrap departs from this Sentence unless an exception Article applies.')],
   competing=[G('9.27.3.4.(1)','Where non-wood-based rigid exterior insulating sheathing, or exterior insulating sheathing with an integral sheathing membrane is installed, a separate sheathing membrane is not required.','candidate','secondary','medium','If the board qualifies, no membrane is required and the departure moves to the joints in 9.27.3.4.(2) (butted, unsealed).'),
              G('9.27.3.4.(2)','the joints of sheathing panels not subject to moisture deterioration shall be i) sealed at all joints, or ii) lapped or tongue and groove, and detailed to ensure drainage of water to the exterior','candidate','secondary','medium','Joint rule if 9.27.3.4.(1) applies.')],
   supporting=[NOTE('A-9.27.3.4.(2)','Butt joints can drain to either side and so should not be used unless they are sealed.')],
   why_not_high='The scored Article flips between 9.27.3.3. and 9.27.3.4. depending on whether the specified board is "non-wood-based rigid exterior insulating sheathing" (9.27.3.4.(1)). The applicant calls it "semi-rigid". The code does not define "rigid", and codedb has no Note on 9.27.3.4.(1) (only A-9.27.3.4.(2) on joints). No public Alberta guidance was found in this pass that classifies semi-rigid mineral wool board.',
   missing_facts=['product data sheet / material standard and rigidity classification of the mineral wool board']),
 'dev-012':dict(status='not upgraded (medium; primary flipped to 9.4.1.1. on public CCMC evidence)', confidence='medium', gold_proposed=[G('9.4.1.1.(1)','structural members and their connections shall a) conform to requirements provided elsewhere in this Part, b) be designed according to good engineering practice','benchmark','primary','medium','Route Article for structural members outside the Section 9.23. prescriptive scope. CCMC 13016-R (below) frames SIP framing as an alternative solution to 9.4.1.1.(1)(c) and Section 9.23.')],
   competing=[G('9.23.13.1.(2)','Bracing to resist lateral loads shall be designed and constructed as follows','candidate','secondary','medium','Applies only if the SIP system is inside Section 9.23. (members at 600 mm o.c. or less); its Clause (b) also allows Part 4 or good engineering practice.'),
              G('9.23.13.1.(1)','This Article applies in locations where the seismic spectral acceleration, Sa(0.2), is not more than 0.70 and the 1-in-50 hourly wind pressure is less than 0.80 kPa.','scope','secondary','high (for the climate branch)','Cochrane values below.'),
              G('9.23.1.1.(1)','the small repetitive structural members are spaced not more than 600 mm o.c.','scope','secondary','medium','The scope test that decides between the two Articles. The one public CCMC SIP evaluation read has ribs at 1.2 m o.c.')],
   supporting=[NOTE('A-9.23.1.1.','The prescriptive requirements in Section 9.23. apply only to standard light wood-frame construction.')],
   public_sources=[dict(source='NRC CCMC Registry, CCMC 13016-R, Insulspan Structural Insulated Panel (SIP) System (Plasti-Fab Ltd.), status Active, modified 2025-10-21; compliance NBC 2010 and NBC 2015 (historical context: not the NBC(AE) 2023, and not shown to be the case product)', url='https://nrc.canada.ca/en/certifications-evaluations-standards/canadian-construction-materials-centre/ccmc-publications/document.html?id=13016-R&type=cert',
        quotes=['an alternative solution to Clause 9.4.1.1.(1)(c), General (Structural Design Requirements and Application Limitations), and Section 9.23., Wood-Frame Construction',
                'Note that only the Insulspan System with a structural stud or joist at 1.2 m (4 ft.) o.c. is CCMC-evaluated',
                'Any other panel installations, in particular loadbearing applications without structural members, are not CCMC-evaluated',
                'pre-engineered wall and roof Insulspan panel resistance values for LSD design, for the specified gravity loads',
                'With no hold-downs, the Insulspan SIP System is limited for use in geographical locations where the q1/50 wind load is less than 0.6 kPa'],
        verified='quotes checked against the WebFetch rendering of the public page on 2026-10-20; a direct curl from the box failed (HTTP 000)',
        reading='The evaluation covers gravity loads only; racking resistance is not in its compliance table, so it does not evaluate "panels resist wind racking with supplier shear values". Its compliance edition is NBC 2015 (historical context).'),
      dict(source='Alberta STANDATA 19-BCV-020 Structural Insulated Panels, May 2021, issued under the NBC(AE) 2019 (historical context: Open Alberta states STANDATA are obsolete for new construction once a new Code comes into effect)', url='https://open.alberta.ca/dataset/5a1e414d-6639-467d-b5a4-6d68454f1340/resource/4e9bae1e-bb8a-460e-9ae0-e105e7f8255b/download/ma-standata-building-code-variance-19-bcv-020.pdf',
        quotes=['Currently SIPs are not a referenced product or system in the NBC(AE)','CCMC evaluations that state materials, products and systems for SIPs are in compliance with the NBC are recognized in Alberta'],
        verified='quotes checked against pdftotext of the public PDF fetched 2026-10-20 (local copy kept in /tmp only, not committed)',
        reading='Shows how Alberta handled SIPs under the previous edition (CCMC evaluation, or an alternative solution by a registered professional). Not current; the routing decision stays with the SCO.')],
   climate_resolved=f"Cochrane: Table C-3 Sa(0.2) = {coch['Sa02']} (PDF page {coch['Sa02_page']}); Table C-2 1-in-50 hourly wind pressure = {coch['hwp_1_50']} kPa (PDF page {coch['page']}). Both are within the 9.23.13.1.(1) limits, so the high-force branch 9.23.13.2. is not the scoped Article for this town.",
   why_not_high='The public evidence now favours 9.4.1.1. as the Article at issue for SIPs generally: codedb Note A-9.23.1.1. limits Section 9.23. to standard light wood-frame construction; 9.23.1.1.(1)(b) requires members at 600 mm o.c. or less; and the one public CCMC SIP evaluation found (13016-R) has ribs at 1.2 m o.c. and treats SIP framing as an alternative to 9.4.1.1.(1)(c) and Section 9.23. It is still not high because the case names no product, so neither its member spacing nor any CCMC evaluation can be checked. A SIP with studs at 600 mm o.c. or less would put the case back inside Section 9.23. (9.23.13.1.(2)). CCMC 13016-R covers gravity loads, not racking, and its compliance edition is NBC 2015 (historical context, previous national edition).',
   missing_facts=['SIP product and any CCMC evaluation number','structural member (rib/stud/spline) spacing, to test Div B 9.23.1.1.(1)(b)','whether the supplier shear values are from a CCMC evaluation or proprietary test data (racking is not in CCMC 13016-R)','site address within Cochrane (Table C-2/C-3 give town values)']),
 'dev-020':dict(status='unchanged: no defensible gold', confidence=None, why_not_high='Part 3 vs Part 9 cannot be decided (v1 finding, not re-opened).')}
if ERR: print('\n'.join(ERR)); sys.exit(1)
order=['dev-006','dev-009','dev-010','dev-011','dev-015']
patches=[dict(file=f'evals_dev/cases/{k}.json',op='add',path='/gold/identify_gold',value=[dict(division=g['division'],provision=g['provision'],role=g['role'],confidence='high',label=LABEL) for g in high[k]['gold']]) for k in order]
patches+=[dict(file=f'evals_dev/cases/{k}.json',op='add',path='/gold/identify_gold_candidates',value=[dict(division=g['division'],provision=g['provision'],role=g['role'],confidence=v['confidence'],label=LABEL) for g in v['gold_proposed']+v['competing']]) for k,v in kept.items() if k!='dev-020']
out=dict(meta=dict(title='Identify gold v2: high-confidence group for BAT-26', generated='2026-10-20 (America/Edmonton, MDT UTC-6)', label=LABEL, supersedes='research/identify-gold-proposals.{md,json} (v1, kept unchanged)',
  codedb_snapshot=dict(path=DB,sha256=hashlib.sha256(open(DB,'rb').read()).hexdigest()), edition='NBC(AE) 2023 2nd printing', scoring='Article level (engine/identify/benchmark.py _article()); must_cite stays empty on ask cases (SCHEMA rule 3); gold goes in gold.identify_gold',
  high_group=order, high_n=len(order), scored_n_if_adopted=11+len(order), guardrails='Golds name the provision at issue; they never say the design complies or fails. Evidence = case description + known_facts + codedb + public sources; case gold/should_cite/seed fields were not used as evidence.', builder='docs/research/2026-10-20-data-nerd/src/gold_v2_build.py'),
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
    for ps in v.get('public_sources',[]):
        L.append(f"- Public source: {ps['source']}. <{ps['url']}>. Verification: {ps['verified']}. *{LABEL}*")
        for q in ps['quotes']: L.append(f"  - \"{q}\"")
        L.append(f"  - Reading: {ps['reading']}")
    for sf in v.get('settling_facts',[]): L.append(f"- Settling fact: **{sf['fact']}**, which settles {sf['settles']}.")
    if v.get('public_source_check'): L.append(f"- Public-source check: {v['public_source_check']}")
    L.append(f"- **Why not high:** {v['why_not_high']}\n- **Missing fact(s):** {'; '.join(v['missing_facts'])}.")
L.append("\n## Kept from v1 (high)\n")
for k in HIGH_IDS:
    for e in high[k]['gold']: L.append(f"- {k}: "+ent(e)[2:])
L.append(f"\n## Climate data used\n\n{climate['source']}. Table C-2 on PDF pages {min(c2pages)}–{max(c2pages)}; Table C-3 on PDF pages {min(c3pages)}–{max(c3pages)}. Method: {climate['method']}.\n\n## Patches\n\nSee `patches` in the json: `identify_gold` for the {len(order)} high cases and `identify_gold_candidates` for 005/007/012.")
open(R+'identify-gold-v2.md','w').write('\n'.join(L)+'\n'); print('OK', len(order), len(C2), mi_max, hdd_min, coch)
