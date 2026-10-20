"""Verify selected source citations using codesearch and substantive article headings.
Found means presence only, not unchanged wording or technical equivalence across editions.
"""
import json,pathlib,re,subprocess,collections
ROOT=pathlib.Path(__file__).resolve().parents[2];OUT=ROOT/'research/precedents'
CODE='NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2'
ps=[json.loads(x) for x in (ROOT/'reference/text'/f'{CODE}.jsonl').read_text().splitlines()]
heading=re.compile(r'(?m)^[ \t]*(\d{1,2}\.\d{1,2}\.\d{1,2}\.\d{1,3})\.[ \t]+([^\n]+)')
articles=collections.defaultdict(list);active=None
for p in ps:
 text=p['text'];divs=re.findall(r'Division\s+([ABC])\b',text[-650:]);div=divs[-1] if divs else None
 matches=[]
 for m in heading.finditer(text):
  title=m[2].strip()
  if re.match(r'(?:Division|National|\d|©)',title) or re.search(r'\.\s*\.\s*\.',title):continue
  matches.append(m)
 for i,m in enumerate(matches):
  body=text[m.end():matches[i+1].start() if i+1<len(matches) else len(text)]
  if div and re.search(r'(?m)^\s*1\)',body):
   rec={'division':div,'article':m[1]+'.','title':m[2].strip(),'page':p['page'],'text':body}
   articles[(div,m[1])].append(rec)
# Check all explicit source references, retaining source spelling separately.
records=json.loads((OUT/'index.json').read_text());notes=json.loads((OUT/'reviewed-notes.json').read_text())
# Explicitly stated historical Part 10 labelling departure.
for r in records:
 if re.search(r'19-bcv-001(?:r1)?$',r['id']):
  notes[r['id']]['selected_citations']=['B:10.1.1.4.(3)']
(outnotes:=OUT/'reviewed-notes.json').write_text(json.dumps(notes,indent=2,ensure_ascii=False)+'\n')
cache={};receipt_dir=OUT/'citation-receipts';receipt_dir.mkdir(exist_ok=True)
for r in records:
 for c in notes.get(r['id'],{}).get('selected_citations',[]):
  root=re.match(r'\d{1,2}(?:\.\d+){3}',c.split(':',1)[1])[0]
  if root not in cache:
   pat=r'(?<!\d)'+re.escape(root)+r'\.(?!\d)'
   cmd=[str(ROOT/'.venv/bin/python'),'-I','tools/codesearch.py','find',pat,'--doc','NBC-AE','--max','1000','--context','0']
   p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,check=True)
   cache[root]={'command':cmd,'stdout':p.stdout,'stderr':p.stderr,'exit_code':p.returncode}
   (receipt_dir/(root+'.json')).write_text(json.dumps(cache[root],indent=2)+'\n')
 def current(c):
  div,cite=c.split(':',1);root=re.match(r'\d{1,2}(?:\.\d+){3}',cite)[0]
  sourceps=[]
  for line in (ROOT/r['source_text_path']).read_text().splitlines():
   p=json.loads(line)
   if root in re.sub(r'\s+','',p['text']):sourceps.append(p['page'])
  item={'original_citation':cite,'original_division':div if div in 'ABC' else None,'original_code':r['code_edition'] if div in 'ABC' else div,'ae2023_provision':None,'pdf_page':None,'status':'not-found','source_pdf_pages':sourceps,'verification_receipt':str((receipt_dir/(root+'.json')).relative_to(ROOT))}
  if div not in ['A','B','C']:
   item.update(status='outside-nbc-scope',verification_note='Source refers to another code/standard. An NBC number match would not establish the requested provision. Required NBC search was still run.');return item
  found=articles.get((div,root),[])
  found=[x for x in found if re.search(rf'PDF p\.{x["page"]}\]',cache[root]['stdout'])]
  if found:
   f=found[0];item.update(ae2023_provision=f'Div {div}, Article {root}.',pdf_page=f['page'],status='same-number-present',ae2023_title=f['title'])
   # Sentence numbers are retained from the source but this index only verifies the article heading.
   item['verification_note']='Article heading and division verified in NBC(AE) 2023 p2; sentence/clause text and cross-edition equivalence are not certified by this index.'
  else:item['verification_note']='No substantive same-number article heading in the stated division was verified. Do not infer a successor from another division, note, index, table or standard.'
  return item
 selected=[current(c) for c in notes.get(r['id'],{}).get('selected_citations',[])]
 # Related benchmarks/conditions are not departures for guidance documents.
 r['articles_varied']=selected if r['type'] in ['variance','spv'] else []
 r['articles_referenced']=selected if r['type'] not in ['variance','spv'] else []
 r['article_list_scope']=notes.get(r['id'],{}).get('citation_scope_note','Source-selected provision references. For variances/SPVs these include the cited benchmark and any explicitly identified conditions; not an exhaustive professional code analysis.')
 if not selected:r['article_list_scope']=notes.get(r['id'],{}).get('citation_scope_note','No exact building-code article is designated by this source summary; empty does not mean the project touches no code requirements.')
 r.pop('selected_citations',None)
 statements=collections.defaultdict(list)
 for line in (ROOT/r['source_text_path']).read_text().splitlines():
  p=json.loads(line)
  for v in set(re.findall(r'\b(?:O[SPHEA]\d+(?:\.\d+)*|F\d{2})\b',p['text'])):statements[v].append(p['page'])
 r['objectives_functions_stated']=[{'statement':k,'source_pdf_pages':v} for k,v in sorted(statements.items())]
 r['objectives_functions_note']='Only identifiers printed by the source are listed. No attribution pairs are inferred; use current Division B attribution tables to complete Section C.'
 if r.get('date') is None:r['date_unavailable_reason']='UNVERIFIED: no unambiguous issue/revision date has been assigned; consult the source.'
 if r['issuer']=='Government of Alberta':r['family_id']=re.sub(r'(?:r\d+|-rev\d+)$','',r['id'])
 else:r['family_id']=r['id']
 r['use_class']='historical' if r['source_status'] in ['withdrawn','archived','superseded'] or ('2014' in r['id'] or '2019' in r['id']) else 'on-hold' if 'on-hold' in r['source_status'] else 'guidance' if r['type'] not in ['variance','spv'] else 'posted-variance'
 (OUT/'index.json.tmp').write_text(json.dumps(records,indent=2,ensure_ascii=False)+'\n');(OUT/'index.json.tmp').replace(OUT/'index.json')
counts=collections.Counter(x['status'] for r in records for k in ['articles_varied','articles_referenced'] for x in r[k])
print('Verified',len(cache),'unique article-number searches;',dict(counts))
for r in records:
 for k in ['articles_varied','articles_referenced']:
  for a in r[k]:
   if a['status']=='not-found':print('NOT FOUND',r['id'],a['original_division'],a['original_citation'])
