"""Build the Div B article corpus and a BM25 article ranker from codedb.sqlite (read-only)."""
import re, sqlite3, json, sys
DB = '/Users/aamia/.t3/projects/batatis/codedb/build/codedb.sqlite'
STOP = set("""a an and are as at be been but by can for from has have if in into is it its may must not of on or
our shall should such than that the their then there these this those to under was were when where which while
who will with within without would per via any all each other also only more most than some same apply applies
applied ref allows allow accepts accept explains describes requirements requirement buildings building""".split())
def con():
    c = sqlite3.connect(f'file:{DB}?mode=ro', uri=True); c.row_factory = sqlite3.Row; return c
def articles():
    c = con()
    titles = {r['id']: r['title'] for r in c.execute("select id, title from provisions where doc='NBC-AE' and division='B' and level in ('section','subsection')")}
    arts = {}
    for r in c.execute("select id, part, section, subsection, title from provisions where doc='NBC-AE' and division='B' and level='article' order by sort_key"):
        arts[r['id']] = dict(id=r['id'], part=r['part'], title=r['title'], section=titles.get(r['section'],''),
                             subsection=titles.get(r['subsection'],''), parts=[])
    for r in c.execute("select article, level, text from provisions where doc='NBC-AE' and division='B' and level in ('sentence','clause','subclause') order by sort_key"):
        a = arts.get(r['article'])
        if a is None or not r['text']: continue
        t = re.sub(r'\s+', ' ', r['text']).strip()
        if a['parts'] and t in a['parts'][-1]: continue
        a['parts'].append(t)
    for a in arts.values():
        a['text'] = ' '.join(a.pop('parts'))
    return arts
def card(a, n=700):
    head = f"{a['title']} (Part {a['part']} > {a['section']} > {a['subsection']})"
    body = a['text'][:n] + ('...' if len(a['text']) > n else '')
    return f"{head}: {body}"
def bm25_rank(query, limit=3000):
    words = [w for w in re.findall(r"[a-z][a-z0-9-]{2,}", query.lower()) if w not in STOP]
    if not words: return []
    q = ' OR '.join('"%s"' % w.replace('"','') for w in dict.fromkeys(words))
    c = con()
    best = {}
    for r in c.execute("select id, bm25(provisions_fts, 0, 0, 0, 4.0, 1.0) as s from provisions_fts where provisions_fts match ? and doc='NBC-AE' and division='B' order by s limit ?", (q, limit)):
        m = re.match(r'(\d+\.\d+\.\d+\.\d+\.)', r['id'])
        if not m: continue
        art = m.group(1)
        if art not in best or r['s'] < best[art]: best[art] = r['s']
    return [a for a,_ in sorted(best.items(), key=lambda kv: kv[1])]
if __name__ == '__main__':
    arts = articles()
    print(len(arts), 'articles; avg text', sum(len(a['text']) for a in arts.values())//len(arts), 'chars')
    print(card(arts['9.9.10.1.'])[:500])
    print(bm25_rank('Window opening control devices for fall protection and bedroom escape')[:10])
