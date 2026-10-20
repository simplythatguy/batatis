import json
d=json.load(open('/workspace/batatis/research/carlos-s1-backing.json')); m=d['meta']; L=[]
A=L.append; esc=lambda s:str(s).replace('|','\\|').replace('\n','<br>')
def cit(x):
    if 'provision' in x: return f"Div {x['division']} {x['provision']} (PDF p.{x['pdf_page']}): \"{x['quote']}\""
    return f"{x['source']} ({x['url']}), page {x['pdf_page']} of the PDF: \"{x['quote']}\""
A(f"# {m['title']}\n\n**Label: {m['label']}.** Generated {m['generated']} by Data Nerd. Public sources only. Codedb: {m['edition'] if 'edition' in m else m['codedb_snapshot']['edition']}, sha256 `{m['codedb_snapshot']['sha256'][:12]}…`. Builder: `{m['builder']}` (every quote is string-matched against codedb or pdftotext; the build fails on a mismatch). Report: `{m['report']}`.\n")
p1=d['part1_variance_vs_redesign']
A("## 1. Variance vs redesign: decision rule\n"); A(f"**App answer:** {p1['app_answer']}\n\n*Wording: {p1['app_answer_source']}.*\n")
for s in p1['rule']: A(f"- {s}")
A("\n**Citations (verbatim):**\n")
for x in p1['citations']: A(f"- {cit(x)}. *({x['why']})*")
A("\n**Attribution lookups (Carlos case):**\n")
for it in p1['carlos_attribution']['items']:
    rows=' '.join(r['bracket'] for r in it['rows'])
    src=f" (from {it['rows'][0]['table']}, PDF p.{it['rows'][0]['pdf_page']})" if it['rows'] else ''
    A(f"- Div B {it['provision']} {rows}{src}; attribution_status `{it['attribution_status']}`" + ('' if it['rows'] else '; no rows, so show "lookup not available"'))
A("\n**Case B evidence:**\n")
for e in p1['carlos_evidence']: A(f"- `{e['file']}` line {e['line']}: `{e['text']}`")
p2=d['part2_sprinkler_exempt']; C=p2['citations']
A("\n## 2. The sprinkler 'exempt' claim\n"); A(f"Report: `{p2['claim_in_report']['file']}` line {p2['claim_in_report']['line']}: `{p2['claim_in_report']['text']}`\n")
for e in p2['claim_in_case']: A(f"- `{e['file']}` line {e['line']}: `{e['text']}`")
A(f"\n**Scope note.** {p2['scope_note']}\n")
A("### 2A. Does the building need sprinklers? Decision table\n\n| condition | result | next |\n|---|---|---|")
for r in p2['decision_table_building']: A(f"| {esc(r['condition'])} | {esc(r['result'])} | {esc(r['next'])} |")
A("\n### 2B. Sprinkler penetration 'exempt' claim: what the app does\n\nThe app never rules on the exemption; each row asks for evidence or opens an officer gap.\n\n| item | provisions | App action |\n|---|---|---|")
for r in p2['decision_table_penetration']: A(f"| {esc(r['item'])} | {esc(r['result'])} | {esc(r['app_action'])} |")
A("\n### Evidence the app must have before it accepts 'exempt'\n\n| field | ask | basis |\n|---|---|---|")
for r in p2['evidence_to_ask']: A(f"| `{r['field']}` | {esc(r['ask'])} | {esc(r['basis'])} |")
A(f"\n### Alberta-specific\n\n{p2['alberta_note']}\n")
for k,t in [('scope','Part 9 vs Part 3 scope, classification'),('definitions','Definitions (Div A 1.4.1.2.(1))'),('part3_size','Part 3 building size and sprinkler Articles'),('part9','Part 9'),('penetrations','Penetrations'),('alberta_specific','Alberta-specific')]:
    A(f"\n**{t}:**\n")
    for x in C[k]:
        extra=f" *({x['why']})*" if x.get('why') else (f" *({x['page_note']})*" if x.get('page_note') else '')
        A(f"- {cit(x)}{extra}")
A("\n## 3. Fact-extraction regression cases (Carlos style)\n")
for f in d['part3_fact_extraction_cases']:
    src=f['source']; sf=src['file'] if isinstance(src['file'],str) else '; '.join(src['file'])
    A(f"### {f['id']}: {f['title']}\nSource: `{sf}`" + (f" lines {src['lines']}" if 'lines' in src else '') + (f". {src['why']}" if src.get('why') else '') + f". *{f['label']}*\n")
    if src.get('note'): A(f"Note: {src['note']}.\n")
    A("```text\n"+f['snippet']+"\n```\n"); A("Expected fields:\n```json\n"+json.dumps(f['expected'],ensure_ascii=False,indent=1)+"\n```")
    A("Must not: "+'; '.join(f['must_not'])+'.'); 
    if f.get('must'): A("Must: "+'; '.join(f['must'])+'.')
    if f.get('still_missing'): A("Still missing (ask): "+', '.join(f['still_missing'])+'.')
    A('')
import re
def pre(line):
    def f(mo):
        i=mo.group(0)
        if i.startswith(('1.2.1.1','1.3.3.','2.1.1.2','2.2.1.1','1.4.1.2')): d='A'
        elif i.startswith('2.3.1'): d='C'
        else: d='B'
        return f'Div {d} {i}'
    return re.sub(r'(?<!Div [ABC] )(?<![A-]\d)(?<!Table )(?<![\w.-])\d{1,2}\.\d{1,2}\.\d{1,2}\.(?:\d{1,3}\.)?(?:\(\d+\))?(?:\([a-z]\))?',f,line)
out=[]; code=False
for ln in '\n'.join(L).split('\n'):
    if ln.startswith('```'): code=not code; out.append(ln); continue
    if code: out.append(ln); continue
    parts=re.split(r'(`[^`]*`|\"[^\"]*\")',ln)
    out.append(''.join(p if p.startswith(('"','`')) else pre(p) for p in parts))
open('/workspace/batatis/research/carlos-s1-backing.md','w').write('\n'.join(out)+'\n'); print('md ok', len(L))
