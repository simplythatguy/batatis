import sys, json, os, time, hashlib, threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
_HERE = Path(__file__).resolve().parent
_REPO = next(p for p in _HERE.parents if (p / 'engine' / 'identify' / 'jevkit').is_dir())
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_REPO / 'engine' / 'identify'))
from jevkit import client
from corpus import card
CACHE = '/tmp/jev-bench/out/jev_cache.jsonl'
_lock = threading.Lock()
_cache = {}
if os.path.exists(CACHE):
    for line in open(CACHE):
        r = json.loads(line); _cache[(r['qkey'], r['case'], r['art'])] = r['p']
USAGE = {'requests':0, 'input_tokens':0, 'output_tokens':0, 'errors':0, 'latency_ms':[]}
QUESTIONS = {
 'govern': "Article {L} states a requirement that directly governs the situation described in `proposal`: the proposal must meet that requirement, relies on it, or departs from it.",
 'helps': "Passage {L} contains information that directly helps with the query in `proposal`.",
}
def _qkey(name): return name
def judge(case, arts_by_id, art_ids, qname='govern', chars=700, max_state=56000, workers=8, timeout=60, tag=None):
    key = tag or qname
    todo = [a for a in art_ids if (key, case['id'], a) not in _cache]
    batches, cur, size = [], [], 0
    base = len(json.dumps(case['query'])) + 300
    for a in todo:
        t = card(arts_by_id[a], chars); l = len(json.dumps(t)) + 12
        if cur and base + size + l > max_state: batches.append(cur); cur, size = [], 0
        cur.append((a, t)); size += l
    if cur: batches.append(cur)
    def run(batch):
        state = {'proposal': case['query'], 'articles': {f'A{i}': t for i,(a,t) in enumerate(batch)}}
        qs = {f'q{i}': client.noul(QUESTIONS[qname].format(L=f'A{i}')) for i in range(len(batch))}
        for attempt in range(4):
            try:
                t0=time.time(); rep = client.ask(state, qs, timeout=timeout); dt=(time.time()-t0)*1000
                with _lock:
                    USAGE['requests']+=1; u=rep.get('usage',{}); USAGE['input_tokens']+=u.get('input_tokens',0); USAGE['output_tokens']+=u.get('output_tokens',0); USAGE['latency_ms'].append(dt)
                    with open(CACHE,'a') as f:
                        for i,(a,_) in enumerate(batch):
                            p = rep['answers'][f'q{i}']['noul']; _cache[(key, case['id'], a)] = p
                            f.write(json.dumps({'qkey':key,'case':case['id'],'art':a,'p':p})+'\n')
                return
            except Exception as e:
                with _lock: USAGE['errors']+=1
                time.sleep(1.5*(attempt+1))
        raise RuntimeError('batch failed after retries')
    if batches:
        with ThreadPoolExecutor(max_workers=workers) as pool: list(pool.map(run, batches))
    return {a: _cache[(key, case['id'], a)] for a in art_ids}
