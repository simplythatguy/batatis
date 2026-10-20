"""Bounded read-only HEAD checks, checkpointed after every URL."""
import pathlib,json,subprocess,concurrent.futures
OUT=pathlib.Path(__file__).resolve().parent
records=json.loads((OUT/'index.json').read_text());checks=OUT/'url-checks.jsonl'
def check(r):
 p=subprocess.run(['curl','-sSL','-I','--max-time','18','-A','Mozilla/5.0','-o','/dev/null','-w','%{http_code}|%{content_type}|%{url_effective}',r['url']],capture_output=True,text=True)
 bits=p.stdout.split('|',2);return dict(id=r['id'],url=r['url'],accessed='2026-10-18',method='HEAD (redirects followed)',http_status=bits[0] if bits else None,content_type=bits[1] if len(bits)>1 else None,effective_url=bits[2] if len(bits)>2 else None,curl_exit_code=p.returncode,error=p.stderr)
with checks.open('w') as f,concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
 for i,result in enumerate(ex.map(check,records),1):
  f.write(json.dumps(result)+'\n');f.flush()
  if result['http_status']!='200' or result['curl_exit_code']:print('URL ISSUE',result['id'],result['http_status'],result['error'],flush=True)
print('URL checks saved',len(records),flush=True)
