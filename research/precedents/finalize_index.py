"""Apply conservative cross-edition/role annotations and append dataset/source-gap records."""
import pathlib,json,re,hashlib,collections,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2];OUT=ROOT/'research/precedents'
records=json.loads((OUT/'index.json').read_text());records=[r for r in records if r.get('source_text_path')]
byid={r['id']:r for r in records}
# Preserve older same-number lookup results as presence checks, never equivalence claims.
for r in records:
 old=('2014' in r['id'] or '2019' in r['id'] or r['code_edition'] in ['ABC 2014','NBC(AE) 2019'])
 if old:r['use_class']='historical';r['edition_use']='Historical edition/policy text. Do not use unchanged for a new 2023-edition project; confirm current AHJ applicability. Same-number presence is not equivalence.'
 for a in r['articles_varied']+r['articles_referenced']:
  if old and a['status']=='same-number-present':a['status']='same-number-present-equivalence-unverified'
 # Clearly separate contextual/condition references from the varied benchmark.
 related=[]
 if re.search(r'(14-bcv-001|19-bcv-015)$',r['id']):related=['8.1.1.1.']
 if re.search(r'(14-bcv-020|19-bcv-016)$',r['id']):related=['3.2.5.12.','9.10.1.3.']
 if r['id'].endswith('19-bcv-023'):related=['9.36.2.6.(1)']
 if r['id'].endswith('23-bcv-013'):related=['3.8.3.7.(2)']
 if r['id'].endswith('calgary-spv-004-ventilation-indoor-air-quality'):related=['6.2.1.1.(1)']
 if re.search(r'19-bcv-020(?:-rev1)?$',r['id']):related=[a['original_citation'] for a in r['articles_varied']]
 if related:
  moved=[a for a in r['articles_varied'] if a['original_citation'] in related]
  r['articles_varied']=[a for a in r['articles_varied'] if a['original_citation'] not in related]
  r['articles_referenced'].extend(moved)
 for field in ['articles_varied','articles_referenced']:
  for a in r[field]:a['citation_relation']='source-identified-varied-benchmark' if field=='articles_varied' else 'context-or-condition-not-designated-as-varied'
 # Two specific crosswalks supported by corresponding current provincial documents.
 for a in r['articles_varied']:
  oldroot=re.match(r'\d{1,2}(?:\.\d+){3}',a['original_citation'])[0]
  target=None;reason=None
  if re.search(r'(14-bcv-009|19-bcv-011)$',r['id']) and oldroot=='3.1.6.5':target=('standata-nbc2023-variance-23-bcv-011r1','3.1.18.5.');reason='The later greenhouse-film variance identifies the flame-resistance requirement at the new article. Same old number now addresses encapsulation ratings.'
  if re.search(r'(14-bcv-005|19-bcv-002|19-bcv-021)$',r['id']) and oldroot=='2.4.5.1':target=('standata-nbc2023-variance-23-bcv-002','2.5.1.1.(2)');reason='The current off-site-construction review variance identifies Division C 2.5.1.1; the older Division C 2.4.5.1 is not a current heading.'
  if target:
   tr=byid[target[0]];ta=next(x for x in tr['articles_varied'] if x['original_citation']==target[1]);a.setdefault('same_number_lookup',{k:a.get(k) for k in ['ae2023_provision','pdf_page','status','ae2023_title']})
   a.update(ae2023_provision=ta['ae2023_provision'],pdf_page=ta['pdf_page'],status='topic-successor-found-equivalence-unverified',ae2023_title=ta['ae2023_title'],crosswalk_source_id=tr['id'],crosswalk_source_url=tr['url'],crosswalk_verification_receipt=ta['verification_receipt'],verification_note=reason+' This identifies a topic successor, not identical wording or permission to reuse the old variance.')
 if r['id']=='standata-nbc2023-errata-23-bce-001':r['source_conflicts']=[{'issue':'23-BCE-001 changes Site Class E shear-strength symbol to overbarred s_u; supplied second-printing PDF p.481 still shows a plain symbol in that bullet.','source_pdf_pages':[2],'ae2023_pdf_page':481,'evidence':'research/precedents/source-views/ae2023-p2-table-4.1.8.4-B-detail.png','resolution':'UNVERIFIED: issuer/professional clarification; current-code citation edition remains NBC(AE) 2023 p2.'}]
 if r['id'] in ['standata-nbc2023-interpretation-23-bci-024','standata-nbc2023-interpretation-23-bci-026']:
  r.setdefault('source_conflicts',[]).append({'issue':'Source cites Div C 2.3.1.2.; no such article was found in the supplied second printing. Div C documentation article 2.3.1.1. is separately verified.','resolution':'Retain original as not-found. Do not invent a current 2.3.1.2. or silently substitute it.'})
 # Exact local/remote receipts where available.
 checks=OUT/'url-checks.jsonl'
 if checks.exists():
  ch={x['id']:x for x in map(json.loads,checks.read_text().splitlines())}.get(r['id'])
  if ch and ch['url']==r['url']:r['url_check']=ch

# Correct the previously HTTP-only FAQ link with a verified HTTPS equivalent.
faq=byid['scc-variance-faqs'];faq['url']=faq['url'].replace('http://','https://');faq['url_check']={'method':'HEAD HTTPS retry','accessed':'2026-10-18','http_status':'200','content_type':'application/pdf','url':faq['url']}

def base(id,issuer,typ,edition,title,summary,scope,conditions,url,path,topics):
 return dict(id=id,issuer=issuer,type=typ,code_edition=edition,title=title,summary=summary,articles_varied=[],articles_referenced=[],objectives_functions_stated=[],conditions=conditions,applies_to=scope,date=None,url=url,local_path=path,topics=topics,accessed='2026-10-18',review_status='source-indexed',family_id=id,use_class='dataset-summary',source_status='public-source',sha256=hashlib.sha256((ROOT/path).read_bytes()).hexdigest() if path else None)
cc=json.loads((OUT/'ccmc-summary.json').read_text());scc=json.loads((OUT/'scc-article-counts.json').read_text())
records.append(base('ccmc-registry-summary','National Research Council Canada / CCMC','ccmc-summary','Mixed editions; inspect each product assessment','CCMC registry snapshot – 462 product assessments',f'Supplied snapshot contains {cc["assessments"]} unique active assessment entries; MasterFormat and referenced-standard strings provide product/evidence routing, not a current Alberta acceptance finding.','Product/manufacturer-specific evidence search.',cc['product_path'],cc['source_url'],'reference/data/ccmc-registry.json',['evidence-and-conformity','building-envelope-insulation-cladding','structural-and-framing']))
records[-1].update(url_unavailable_reason='UNVERIFIED live refresh: curl exit 6, could not resolve host const-bers-app-prod.corp.nrc.gc.ca on 2026-10-18; the supplied JSON is the data source.',url_check={'method':'HEAD','http_status':'000','curl_exit_code':6,'accessed':'2026-10-18','error':'Could not resolve host'},date_unavailable_reason='Snapshot does not identify a registry-wide publication/as-of date; local review date is not provider freshness.',summary_data_path='research/precedents/ccmc-summary.json',population=cc['population'])
records.append(base('scc-variance-data-summary','Safety Codes Council','bulletin','Multiple code labels/editions; retain raw labels','SCC public variance dashboard – article-count summary','Public model query returned 95 code/article groups and a published Article Count sum of 3,118; counts are not unique applications. Visible model/report is labelled 2026 Q1.','Provincewide registered-variance trend discovery within the published dataset.',scc['quality_checks']['limitations'],'https://www.safetycodes.ab.ca/data-hub/variance-data/','research/precedents/scc-article-counts.json',['process-and-admin','evidence-and-conformity']))
records[-1].update(date='2026-08-14',date_meaning='Power BI model last refresh; period label is 2026 Q1, not an application issue date.',data_source_receipts=['research/precedents/source-catalog/scc-powerbi-schema.json','research/precedents/source-catalog/scc-powerbi-models.json','research/precedents/source-catalog/scc-query-request.json','research/precedents/source-catalog/scc-query-response.json','research/precedents/source-catalog/scc-grain-request.json','research/precedents/source-catalog/scc-grain-response.json'],quality_report='research/precedents/scc-quality.json')
spv=base('calgary-spv-007-alarmed-backwater-valve','City of Calgary','spv','National Plumbing Code 2020','SPV-007 – Alarmed Normally Open Backwater Valves (inaccessible live source)','Search-cached first-page evidence describes a valve serving at most two dwelling units; the live PDF URL returned 404 on both Calgary hosts.','A dwelling with a secondary suite; cached evidence only.',['UNVERIFIED: complete current source/status could not be obtained. Do not treat this entry as active permission.','Cached first-page conditions identify an alarm for occupants, unrestricted valve access, and stopping plumbing use during backup until restored.'],'https://www.calgary.ca/content/dam/www/pda/pd/documents/building/variances/alarmed-normally-open-spv-007.pdf',None,['hvac-ventilation-plumbing','housing-secondary-suites-part9'])
spv.update(date='2025-06-20',review_status='partial-source',source_status='unlisted-live-url-404',use_class='unverified-source-gap',url_unavailable_reason='GET returned HTTP 404 on www.calgary.ca and www-prd.calgary.ca on 2026-10-18; search service retained cached first-page text. One direct web retry also returned 404.',local_unavailable_reason='No valid local PDF retrieved; returned HTML 404 page is retained in source-catalog/calgary-spv-007-404.html.',source_evidence_path='research/precedents/source-catalog/missing-calgary-receipts.json',articles_varied=[{'original_citation':'2.4.6.4.(5)(b)','original_code':'National Plumbing Code 2020','ae2023_provision':None,'pdf_page':None,'status':'outside-nbc-scope','source_pdf_pages':[1],'verification_receipt':'research/precedents/citation-receipts/2.4.6.4.json','verification_note':'Cached plumbing reference; required NBC search receipt retained, with no NBC identity/equivalence asserted.'}])
records.append(spv)
# Attach successful independent URL receipts for newly added source/summary rows.
url_checks={x['id']:x for x in map(json.loads,(OUT/'url-checks.jsonl').read_text().splitlines())}
for record in records:
 check=url_checks.get(record['id'])
 if check and check['url']==record['url']:record['url_check']=check

# Every dataset/source-gap record keeps explicit field semantics.
for r in records:
 if r.get('source_conflicts'):
  r['source_conflicts']=list({json.dumps(c,sort_keys=True):c for c in r['source_conflicts']}.values())
 r.pop('selected_citations',None)
 if r['id'].startswith('calgary-spv-004'):r.pop('url_unavailable_reason',None)
(OUT/'index.json').write_text(json.dumps(records,indent=2,ensure_ascii=False)+'\n')
print('FINAL CHECKPOINT',len(records),'records;',sum(r.get('local_path') is not None for r in records),'local files;',sum(r['review_status']=='partial-source' for r in records),'source gap')
