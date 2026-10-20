"""Search current provisions mentioned by the errata register and SCC ranking."""
import pathlib,json,re,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2];OUT=ROOT/'research/precedents'
text=(OUT/'errata.md').read_text();roots=set(re.findall(r'(?<![\d.])\d{1,2}(?:\.\d{1,2}){2}\.\d{1,3}(?=\.)',text));checks=[]
if (OUT/'scc-article-counts.json').exists():
 for r in json.loads((OUT/'scc-article-counts.json').read_text())['rows']:
  if r['discipline']=='Building' and r.get('normalized_article'):roots.add(r['normalized_article'].rstrip('.'))
for root in sorted(roots):
 pat=r'(?<!\d)'+re.escape(root)+r'\.(?!\d)';cmd=[str(ROOT/'.venv/bin/python'),'-I','tools/codesearch.py','find',pat,'--doc','NBC-AE','--max','1000','--context','0'];p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,check=True)
 check={'article':root+'.','command':cmd,'pdf_pages':[int(n) for n in re.findall(r'PDF p\.(\d+)\]',p.stdout)],'status':'text-present' if 'no matches' not in p.stdout else 'not-found'};checks.append(check)
 (OUT/'citation-receipts'/('supplemental-'+root+'.json')).write_text(json.dumps({**check,'stdout':p.stdout},indent=2)+'\n')
for pattern,label in [(r'D-1\.7\.1\.','D-1.7.1.'),(r'D-2\.3\.4\.-B','Table D-2.3.4.-B')]:
 cmd=[str(ROOT/'.venv/bin/python'),'-I','tools/codesearch.py','find',pattern,'--doc','NBC-AE','--max','100','--context','0'];p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,check=True);checks.append({'article':label,'command':cmd,'pdf_pages':[int(n) for n in re.findall(r'PDF p\.(\d+)\]',p.stdout)],'status':'text-present' if 'no matches' not in p.stdout else 'not-found'})
(OUT/'supplemental-citation-checks.json').write_text(json.dumps(checks,indent=2)+'\n');print('Supplemental current-code searches',len(checks),'not found',[c['article'] for c in checks if c['status']=='not-found'])
