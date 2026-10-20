import json, re, sqlite3, subprocess, unicodedata
from pathlib import Path
R = Path('/workspace/batatis/research'); DB = '/workspace/batatis/codedb-snapshot/codedb.sqlite'
c = sqlite3.connect(DB); ERR = []
def n(s):
    s = unicodedata.normalize('NFKC', s).replace('’', "'").replace('“', '"').replace('”', '"')
    return re.sub(r'\s+', ' ', s).strip()
def pdfpage(pdf, quote):
    pages = int(re.search(r'Pages:\s+(\d+)', subprocess.run(['pdfinfo', pdf], capture_output=True, text=True).stdout).group(1))
    for p in range(1, pages + 1):
        t = subprocess.run(['pdftotext', '-f', str(p), '-l', str(p), pdf, '-'], capture_output=True, text=True).stdout
        if n(quote) in n(t): return p
    ERR.append(f'not found in {pdf}: {quote}'); return None
def code(div, pid, quote, kind='provision'):
    if kind == 'note':
        r = c.execute('select pdf_page, text from notes where division=? and note_id=?', (div, pid)).fetchone()
    else:
        r = c.execute('select pdf_page, text from provisions where division=? and id=?', (div, pid)).fetchone()
    if not r or n(quote) not in n(r[1]): ERR.append(f'codedb mismatch {div} {pid}')
    return dict(source=f'NBC(AE) 2023 2nd printing, Div {div} {"Note " if kind=="note" else ""}{pid}', page=r[0] if r else None,
                url='codedb snapshot (NBC(AE) 2023 2nd printing PDF)', quote=quote, verification=f'codedb-checked, PDF p.{r[0] if r else "?"}')
def pdf(label, path, url, quote, licence=None):
    p = pdfpage(path, quote)
    d = dict(source=label, page=p, url=url, quote=quote, verification=f'source-PDF-checked (local copy {path}), p.{p}')
    if licence: d['licence'] = licence
    return d
B = '/workspace/batatis'
SCA = f'{B}/research/src/leg/S01.pdf'; SCAURL = 'https://kings-printer.alberta.ca/documents/Acts/S01.pdf'
OGL = 'Open Government Licence - Alberta'
claims = [
 dict(claim='CCMC (NRC) evaluates construction products for code compliance to help manufacturers get market acceptance.',
      sources=[dict(source='NRC, Canadian Construction Materials Centre (web page)', page=None,
                    url='https://nrc.canada.ca/en/certifications-evaluations-standards/canadian-construction-materials-centre',
                    quote='The Canadian Construction Materials Centre (CCMC) assesses compliance with Canadian building, energy and safety codes.',
                    verification='web-fetched 2026-10-20 (WebFetch); not archived locally')]),
 dict(claim='Alberta recognises CCMC evaluation reports, and those of organizations approved by the Provincial Building Administrator, as a way to show code compliance.',
      sources=[code('A', '1.2.2.1.(2)', 'Evaluation reports issued by the Canadian Construction Materials Centre, National Research Council of Canada, or an organization approved by the Provincial Building Administrator may be used in determining compliance with the requirements of this Code.')]),
 dict(claim='The PBA approves other evaluators by STANDATA (e.g. QAI Laboratories, 23-BCI-005; also 23-BCI-006, -007, -013, -040 per the local STANDATA set).',
      sources=[pdf('STANDATA 23-BCI-005, Approved organization - QAI Laboratories (May 2024)', f'{B}/sources/standata/23-BCI-005.pdf',
                   'https://open.alberta.ca/dataset/cb3d1662-1354-45c8-aab8-29b91f2a6c35/resource/57cebce9-5fe6-4583-a0bd-f2e4c7eedec9/download/ma-23-bci-005-approved-organization-qai-laboratories.pdf',
                   'This interpretation recognizes QAI Laboratories as an approved organization that issues evaluation reports that may be used to determine compliance with the requirements of the NBC(AE).', OGL)]),
 dict(claim='A province-wide variance is requested from the Provincial Building Administrator, applies everywhere in Alberta, and must address a province-wide issue; these are published as STANDATA variances (23-BCV series).',
      sources=[code('C', '2.2.1.2.(1)', 'A written request for a variance may be submitted to the Provincial Building Administrator.'),
               code('C', 'A-2.2.1.2.', 'The application to the Provincial Building Administrator must show that the issue is province-wide.', kind='note'),
               pdf('STANDATA 23-BCV-001, Window opening control devices (2024-04)', f'{B}/sources/standata/23-BCV-001.pdf',
                   'https://open.alberta.ca/dataset/08ac69ae-5639-46a3-83d2-c52246c78621/resource/01b622f0-f4a1-426d-b15f-ffc25e725949/download/ma-standata-variance-building-23-bcv-001-2024-04.pdf',
                   'This VARIANCE is applicable throughout the Province of Alberta.', OGL)]),
 dict(claim='A site-specific variance is issued by a safety codes officer (or an Administrator) when the alternative gives approximately equivalent or greater safety; the officer must notify an Administrator.',
      sources=[pdf('Safety Codes Act, RSA 2000 c S-1, s.38(1)', SCA, SCAURL, 'An Administrator or a safety codes officer may issue a written variance with respect to any thing, process or activity to which this Act applies if the Administrator or officer is of the opinion that the variance provides approximately equivalent or greater safety performance'),
               pdf('Safety Codes Act s.38(3)', SCA, SCAURL, 'A safety codes officer on issuing a variance shall notify an Administrator.')]),
 dict(claim='For building, the officer must document the alternative solution per Division C 2.3.1 and send each variance to the Safety Codes Council within 10 days.',
      sources=[pdf('SCC Information Bulletin IB-2025-11-18, Mandatory Documentation of Variances', f'{B}/sources/IB-2025-11-18.pdf',
                   'https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2025-11-18%20Mandatory%20Documentation%20of%20Variances.pdf',
                   'Submit a copy of each variance to the Safety Codes Council within 10 days of issuance.'),
               pdf('IB-2025-11-18', f'{B}/sources/IB-2025-11-18.pdf',
                   'https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2025-11-18%20Mandatory%20Documentation%20of%20Variances.pdf',
                   'Document alternative solutions as required by Division C of the applicable code.')]),
 dict(claim='From December 1, 2026 variances are registered through the SCC Orders and Variances Portal; registration is not Council approval.',
      sources=[pdf('SCC Information Bulletin IB-2026-10-01, Orders and Variances Registration Changes', f'{B}/forms/IB-2026-10-01.pdf',
                   'https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-01%20Orders%20and%20Variances%20Registration%20Changes.pdf',
                   'Variances must be registered in OVP at the time of issuance or as soon as reasonably practicable thereafter.'),
               pdf('IB-2026-10-01', f'{B}/forms/IB-2026-10-01.pdf',
                   'https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-01%20Orders%20and%20Variances%20Registration%20Changes.pdf',
                   'Registration of an order or variance through OVP does not constitute Council approval of that order or variance')]),
 dict(claim='The Act lets an Administrator record a variance and the location it applies to (variance register).',
      sources=[pdf('Safety Codes Act s.62', SCA, SCAURL, 'An Administrator may place an entry on the relevant information system that briefly indicates the subject-matter of a variance and the location of the thing, process or activity to which the variance applies.')]),
]
unverified = [
 'No Safety Codes Act section creating a building-PRODUCT approval was found. s.40 (design registration) and s.43(2) (things "approved by the regulations") exist but were not confirmed to apply to building products. In the building discipline, product acceptance enters through NBC(AE) Div A 1.2.2.1.(2), not the Act. UNVERIFIED.',
 'Whether a Part 9 product evaluation must be a CCMC "evaluation" versus a "listing" for Alberta acceptance: Div A 1.2.2.1.(2) names "evaluation reports"; the status of other listings was not checked. UNVERIFIED.',
]
summary = ('A product approval and a variance answer different questions. Product approval is market-wide: a CCMC evaluation report, or one from an evaluator the Provincial Building Administrator has approved, can be used anywhere in Alberta to show the product meets the code. '
           'A variance (alternative solution) is a decision about one building or site: a safety codes officer accepts it when it gives about the same or better safety, documents it under Division C 2.3.1, and registers it with the Safety Codes Council. '
           'A province-wide STANDATA variance from the Provincial Building Administrator is the exception, but it needs a province-wide issue, not one company\'s product. '
           'So a manufacturer wanting "approval across Alberta" needs an evaluation report; a pilot house can go ahead on a site variance in the meantime.')
pav = dict(summary=summary, claims=claims, unverified=unverified, label='model-checked, not human-verified')
if ERR: print('\n'.join(ERR)); raise SystemExit(1)
p = R/'identify-regression.json'; d = json.load(open(p)); d['product_approval_vs_variance'] = pav
json.dump(d, open(p, 'w'), ensure_ascii=False, indent=2); print('OK claims', len(claims))
