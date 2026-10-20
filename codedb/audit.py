"""Repeatable 30-provision source check using the repository's codesearch CLI.

Outputs only metadata in its report; captured copyrighted page text stays under build/.
This checks extraction identity and source locations, not interpretation or exhaustiveness.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import subprocess
import sys
from pathlib import Path

from . import store
from .sources import BUILD_DIR, ROOT


def spot_check(seed=20261018):
    rng = random.Random(seed)
    con = store.connect()
    pool = [dict(r) for r in con.execute("SELECT * FROM provisions WHERE doc='NBC-AE' AND level IN ('article','sentence') "
                                       "ORDER BY division,sort_key")]
    con.close()
    selected = []
    # Random within strata: all divisions, all Div B parts, both article and sentence.
    for division in ('A','C'):
        selected.extend(rng.sample([r for r in pool if r['division']==division],4))
    for part in sorted({r['part'] for r in pool if r['division']=='B'}):
        for level in ('article','sentence'):
            selected.append(rng.choice([r for r in pool if r['division']=='B' and r['part']==part and r['level']==level]))
    selected.extend(rng.sample([r for r in pool if r['division']=='B' and r not in selected],30-len(selected)))
    page_dir = BUILD_DIR/'audit'/'pages'
    page_dir.mkdir(parents=True,exist_ok=True)
    cache = {}

    def page(n):
        if n not in cache:
            output = subprocess.check_output([sys.executable,'-I',str(ROOT/'tools'/'codesearch.py'),
                                              'page','NBC-AE',str(n)],text=True)
            (page_dir/f'{n}.txt').write_text(output,encoding='utf8')
            cache[n] = output
        return cache[n]

    compact = lambda t: re.sub(r'\s+','',t)
    checks = []
    for row in selected:
        first,last = row['pdf_page'],row['pdf_page_end']
        source = compact('\n'.join(page(n) for n in range(first,last+1)))
        lines = [row['id']+' '+row['title']] if row['level']=='article' else row['text_raw'].splitlines()
        # Ordered substring check tolerates running headers/footers at page breaks;
        # comparing one concatenated string would incorrectly call those mismatches.
        cursor=0
        matches=True
        for line in lines:
            at=source.find(compact(line),cursor)
            if at<0:
                matches=False
                break
            cursor=at+len(compact(line))
        begin=compact(lines[0]) in compact(page(first)) if lines else False
        end=compact(lines[-1]) in compact(page(last)) if lines else False
        label = row['level']=='article' or row['text_raw'].startswith(str(row['sentence'])+') ')
        checks.append({'division':row['division'],'id':row['id'],'level':row['level'],'part':row['part'],
                       'pdf_page':first,'pdf_page_end':last,'ordered_source_text_match':matches,
                       'starts_on_claimed_page':begin,'ends_on_claimed_page':end,'label_matches':label,
                       'ok':matches and begin and end and label})
    mismatch=sum(not r['ok'] for r in checks)
    result={'seed':seed,'method':'random stratified by division and Div B part; source = tools/codesearch.py page NBC-AE N',
            'sample_size':len(checks),'mismatches':mismatch,'mismatch_pct':round(100*mismatch/len(checks),2),
            'checks':checks,'source_page_output_sha256':{str(k):hashlib.sha256(v.encode()).hexdigest() for k,v in sorted(cache.items())}}
    out=BUILD_DIR/'spot-check.json'
    out.write_text(json.dumps(result,indent=2)+'\n')
    print(f'{len(checks)} source checks; {mismatch} mismatches ({result["mismatch_pct"]}%); {out}')
    return result


if __name__=='__main__':
    raise SystemExit(1 if spot_check()['mismatches'] else 0)
