"""Rebuild the local precedent index from primary PDFs and reviewed notes.
Run from repo root: .venv/bin/python research/precedents/build_index.py
Only writes research/precedents/. Citation receipts use the required codesearch CLI.
"""
import collections, hashlib, html, json, pathlib, re, subprocess, sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
OUT=ROOT/'research/precedents'
ACCESS='2026-10-18'
PUBLICATIONS={
 'ab-2014-variance':'https://open.alberta.ca/publications/standata-building-code-variance-2014',
 'ab-2019-variance':'https://open.alberta.ca/publications/standata-building-code-variance-national-building-code-2019-alberta-edition',
 'ab-2023-variance':'https://open.alberta.ca/publications/standata-variance-building-national-building-code-2023-alberta-edition',
 'ab-2023-interpretation':'https://open.alberta.ca/publications/standata-interpretation-building-national-building-code-2023-alberta-edition',
 'ab-2023-bulletin':'https://open.alberta.ca/publications/standata-bulletin-building-national-building-code-2023-alberta-edition',
 'ab-2023-errata':'https://open.alberta.ca/publications/standata-errata-building-national-building-code-2023-alberta-edition',
 'ab-2019-errata':'https://open.alberta.ca/publications/standata-building-code-errata-nbc-2019-alberta-edition',
 'scc-notice':'https://open.alberta.ca/publications/notice-variances-under-the-safety-codes-act-2019',
 'calgary':'https://www.calgary.ca/development/permits/building-regulation-advisories.html',
 'edmonton':'https://www.edmonton.ca/residential_neighbourhoods/application-requirements-house-permits',
 'scc':'https://www.safetycodes.ab.ca/permits-inspections/variances/'
}
def dump(p,obj):
 p=OUT/p;tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n');tmp.replace(p)
def norm(s):return re.sub(r'[^a-z0-9]','',s.lower().replace('rev','r'))
def identifier(s):
 m=re.search(r'(\d{2})[- ]?(BC[VIBE])[- ]?(\d{3})(?:[\s(\-]*(?:REV|R)\s*(\d+))?',s,re.I)
 return norm(m[0]) if m else None

def catalogue():
 records=[]
 for f in sorted((OUT/'source-catalog').glob('ab-*.html')):
  for li in re.findall(r'<li class="resource-item".*?</li>',f.read_text(),re.S):
   m=re.search(r'<a class="heading" href="([^"]+)" title="([^"]+)"',li)
   if m:
    title=html.unescape(m[2]);status=next((k.lower().replace(' ','-') for k in ['WITHDRAWN','ON HOLD - UNDER REVIEW','SUPERSEDED','ARCHIVED'] if k in title),'listed')
    records.append(dict(catalog=f.stem,url=html.unescape(m[1]),title=title,publication_url=PUBLICATIONS.get(f.stem),source_status=status))
 dump(pathlib.Path('source-catalog/alberta-resources.json'),records);return records

def source_links(name):
 s=(OUT/'source-catalog'/f'{name}.html').read_text()
 return list(dict.fromkeys(html.unescape(x) for x in re.findall(r'(?:href|src)=[\'\"]([^\'\"]+)',s)))

MUNICIPAL_URL_KEYS={
 'calgary-spv-001-zero-lot-line-2026-03':'zero-lot-line-march-2026',
 'calgary-spv-003-construction-of-exposed-building-face':'spv-003',
 'calgary-spv-006-firewall-rowhouse-secondary-suites':'spv-006',
 'calgary-new-standing-posted-variance-procedure':'standing-posted-variance-procedure',
 'calgary-request-for-specific-variance':'request-for-specific-variance',
 'calgary-building-advisory-b23-001-code-transition':'b23-001',
 'calgary-plumbing-advisory-p15-002-secondary-suites-backwater-valves':'backwater',
 'edmonton-policy-b14-01-reduced-or-zero-lot-line':'ReducedZero_LotLineProject.pdf',
 'edmonton-policy-b14-01g-reduced-zero-lot-line-detached-garages':'Policy_B14-01G',
 'edmonton-policy-b19-03-area-separation-walls':'Policy_B19_03',
 'edmonton-policy-b19-04-small-building-access':'B19-04_Small',
 'edmonton-policy-b23-01-row-house-fire-separation-more-than-two-secondary-suites':'Policy-B23-01',
 'edmonton-policy-b23-02-window-opening-control-devices':'Policy-B23-02',
 'edmonton-policy-bulletin-b23-03-roof-truss-engineering':'PolicyBulletin-B23-03',
 'edmonton-policy-interpretation-b23-05-application-of-9944':'b23-05-application',
 'edmonton-alternative-solution-secondary-suites-in-row-houses':'Alternative-Solution-for-Secondary-Suites',
 'scc-variance-faqs':'Variance FAQs.pdf',
}

def get_source(p,cat):
 if p.parent.name=='alberta-standata':
  found=[x for x in cat if identifier(x['title'])==identifier(p.stem)]
  # Same identifiers occur only in the matching code cycle/type.
  if len(found)==1:return found[0]
  return None
 issuer=p.parent.name
 links=source_links('scc' if issuer=='safety-codes-council' else issuer)
 key=MUNICIPAL_URL_KEYS.get(p.stem)
 if key:
  found=[u for u in links if key.lower() in u.lower()]
  if found:
   from urllib.parse import urljoin,quote
   return dict(url=quote(urljoin(PUBLICATIONS['scc' if issuer=='safety-codes-council' else issuer],found[0]),safe=':/?=&%').replace('http://ebs.safetycodes.ab.ca/','https://ebs.safetycodes.ab.ca/'),publication_url=PUBLICATIONS['scc' if issuer=='safety-codes-council' else issuer],source_status='listed')
 if p.stem=='scc-notice-variances-under-safety-codes-act-2019':
  s=(OUT/'source-catalog/scc-notice.html').read_text();m=re.search(r'href="(https://open.alberta.ca/dataset/[^\"]+\.pdf)"',s)
  if m:return dict(url=html.unescape(m[1]),publication_url=PUBLICATIONS['scc-notice'],source_status='listed')
 return None

MONTHS={m:i for i,m in enumerate(['January','February','March','April','May','June','July','August','September','October','November','December'],1)}
def issued(text):
 m=re.search(r'Date\s+Issued\s*:\s*([A-Za-z]+)\s+(\d{4})',text,re.I)
 if not m:m=re.search(r'\b('+'|'.join(MONTHS)+r')\s+(20\d{2})',text,re.I)
 return f'{m[2]}-{MONTHS[m[1].title()]:02d}' if m and m[1].title() in MONTHS else None

def main():
 cat=catalogue();old={x['id']:x for x in json.loads((OUT/'index.json').read_text())}
 notes=json.loads((OUT/'reviewed-notes.json').read_text()) if (OUT/'reviewed-notes.json').exists() else {}
 records=[]
 for p in sorted((ROOT/'reference/precedents').rglob('*.pdf')):
  r=old.get(p.stem,dict(id=p.stem,issuer={'alberta-standata':'Government of Alberta','calgary':'City of Calgary','edmonton':'City of Edmonton','safety-codes-council':'Safety Codes Council'}[p.parent.name],type='bulletin',articles_varied=[],objectives_functions_stated=[],conditions=[],topics=[]))
  f=ROOT/'reference/text'/(p.stem+'.jsonl');pages=[json.loads(x) for x in f.read_text().splitlines()];t='\n'.join(x['text'] for x in pages)
  src=get_source(p,cat)
  if src:
   r.update(src);r.pop('url_unavailable_reason',None)
   if src.get('title'):r['title']=re.sub(r'^\[[^]]+\]\s*-\s*','',src['title'])
  else:r['url_unavailable_reason']='UNVERIFIED: no exact download match recovered from the saved official index page.'
  r.update(local_path=str(p.relative_to(ROOT)),source_text_path=str(f.relative_to(ROOT)),source_pages=len(pages),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),accessed=ACCESS,date=issued(pages[0]['text']),source_claim='Official document title, scope, operative conditions, and cited provisions; see source PDF pages.',source_pdf_pages=list(range(1,len(pages)+1)))
  if '2014' in p.stem or '2019' in p.stem:
   r['edition_use']='Historical edition only; Alberta says earlier-edition STANDATA are obsolete for new construction under a later code. Same-number mapping does not establish equivalence.'
  else:r['edition_use']='Check source status, jurisdiction, scope and all operative conditions before relying on this record; an interpretation/bulletin is not an issued project variance.'
  r['source_status']=r.get('source_status','unverified')
  if p.stem in notes:
   r.update(notes[p.stem]);r['review_status']='source-indexed'
  records.append(r)
  if len(records)%15==0:dump(pathlib.Path('index.json'),records+[x for x in old.values() if x['id'] not in {q['id'] for q in records}])
 dump(pathlib.Path('index.json'),records)
 print('CHECKPOINT',len(records),'records;',sum(bool(x.get('url')) for x in records),'exact URLs;',sum(x['review_status']=='source-indexed' for x in records),'reviewed')
 for r in records:
  if not r.get('url'):print('URL GAP',r['id'])
if __name__=='__main__':main()
