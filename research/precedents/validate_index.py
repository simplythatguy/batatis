"""Validate source provenance, schema, edition-aware links and coverage of the index."""
import pathlib,json,re,hashlib,collections,sys
ROOT=pathlib.Path(__file__).resolve().parents[2];OUT=ROOT/'research/precedents'
records=json.loads((OUT/'index.json').read_text());errors=[];warnings=[]
required='id issuer type code_edition title summary articles_varied objectives_functions_stated conditions applies_to date url local_path topics'.split()
allowed=set('variance interpretation bulletin erratum spv policy ccmc-summary'.split())
topics=set('process-and-admin code-structure-and-attribution professional-involvement evidence-and-conformity egress-and-single-stair fire-separations-and-spatial-separation combustible-construction-and-mass-timber building-envelope-insulation-cladding housing-secondary-suites-part9 structural-and-framing hvac-ventilation-plumbing firefighting-alarms-sprinklers energy-efficiency occupancy-and-accessibility'.split())
ids=set();pages=[json.loads(x) for x in (ROOT/'reference/text/NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2.jsonl').read_text().splitlines()]
for r in records:
 missing=set(required)-r.keys()
 if missing:errors.append((r['id'],'missing fields',sorted(missing)))
 if r['id'] in ids:errors.append((r['id'],'duplicate ID'))
 ids.add(r['id'])
 if r['type'] not in allowed:errors.append((r['id'],'type'))
 if not r['topics'] or not set(r['topics'])<=topics:errors.append((r['id'],'topics',r['topics']))
 for field in ['summary','conditions','applies_to']:
  if 'TODO' in str(r[field]):errors.append((r['id'],'unfinished',field))
 p=ROOT/r['local_path'] if r.get('local_path') else None
 if p:
  if not p.is_file():errors.append((r['id'],'missing local source'))
  elif r.get('sha256') and hashlib.sha256(p.read_bytes()).hexdigest()!=r['sha256']:errors.append((r['id'],'source hash changed'))
  if p.suffix=='.pdf' and not p.read_bytes().startswith(b'%PDF'):errors.append((r['id'],'invalid PDF header'))
 elif not r.get('local_unavailable_reason'):errors.append((r['id'],'missing local-source reason'))
 if not r.get('url') or not re.match('https?://',r['url']):errors.append((r['id'],'missing URL'))
 if r.get('url_unavailable_reason'):warnings.append((r['id'],r['url_unavailable_reason']))
 if r.get('source_text_path'):
  f=ROOT/r['source_text_path'];ps=[json.loads(x) for x in f.read_text().splitlines()];t=re.sub(r'\s+','','\n'.join(x['text'] for x in ps))
  if not ps:errors.append((r['id'],'empty source text'))
  if len(ps)!=r['source_pages']:errors.append((r['id'],'source page count'))
  for a in r['articles_varied']+r['articles_referenced']:
   root=re.match(r'\d{1,2}(?:\.\d+){3}',a['original_citation'])[0]
   if root not in t:errors.append((r['id'],'original citation not in source',root))
   receipt=ROOT/a['verification_receipt']
   if not receipt.is_file():errors.append((r['id'],'missing search receipt'))
   if a['status'] not in ['not-found','outside-nbc-scope']:
    page=a['pdf_page'];current=re.sub(r'\s+','',pages[page-1]['text']);curroot=re.search(r'Article (\d{1,2}(?:\.\d+){3})',a['ae2023_provision'])[1]
    if curroot not in current:errors.append((r['id'],'mapped page mismatch',curroot,page))
   elif a.get('ae2023_provision') is not None or a.get('pdf_page') is not None:errors.append((r['id'],'unverified mapping has page'))
 # Guidance must not be mistaken for an issued alternative solution.
 if r['type'] not in ['variance','spv'] and r['articles_varied']:errors.append((r['id'],'guidance has varied articles'))
expected={p.stem for p in (ROOT/'reference/precedents').rglob('*.pdf')};indexed={r['id'] for r in records if r.get('source_text_path')}
if expected!=indexed:errors.append(('PDF coverage mismatch',sorted(expected-indexed),sorted(indexed-expected)))
supp=json.loads((OUT/'supplemental-citation-checks.json').read_text())
if any(x['status']=='not-found' for x in supp):warnings.extend(('supplemental',x['article']) for x in supp if x['status']=='not-found')
code_pdf=ROOT/'reference/codes/NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2.pdf'
code_text=ROOT/'reference/text/NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2.jsonl'
summary={'code_reference':{'pdf_path':str(code_pdf.relative_to(ROOT)),'pdf_sha256':hashlib.sha256(code_pdf.read_bytes()).hexdigest(),'text_sha256':hashlib.sha256(code_text.read_bytes()).hexdigest(),'text_pages':len(pages),'text_up_to_date_by_mtime':code_text.stat().st_mtime>=code_pdf.stat().st_mtime},'local_pdf_url_statuses':dict(collections.Counter(r.get('url_check',{}).get('http_status','unchecked') for r in records if r.get('source_text_path'))),'source_conflict_records':[r['id'] for r in records if r.get('source_conflicts')],'accessed':'2026-10-18','records':len(records),'local_pdf_records':len(indexed),'local_source_records':sum(r.get('local_path') is not None for r in records),'partial_source_records':sum(r['review_status']=='partial-source' for r in records),'types':dict(collections.Counter(r['type'] for r in records)),'article_reference_statuses':dict(collections.Counter(a['status'] for r in records for k in ['articles_varied','articles_referenced'] for a in r[k])),'selected_article_searches':len(list((OUT/'citation-receipts').glob('[0-9]*.json'))),'supplemental_searches':len(supp),'errors':errors,'warnings':warnings,'scope':'Structural/provenance/current-article-presence validation. No technical acceptance, full sentence validation, or full semantic edition equivalence certification.'}
(OUT/'validation.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n');print(json.dumps(summary,indent=2,ensure_ascii=False));sys.exit(bool(errors))
