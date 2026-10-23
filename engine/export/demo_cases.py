"""The three G3 demo cases (manufacturer, general contractor, homebuilder) as completed Batatis cases.

EXAMPLE DATA. Each case is built from `evals/demo-cases/export/<case>.json`: the fictional applicant's confirmed
facts (including explicit not-applicable facts), the attached example input files, a stored code-identification
record and the applicant's confirmed provisions. Every process-field passage in those files is fictional applicant
text written for the demo, labelled EXAMPLE; production code never writes one. Section C rows are rebuilt from the
code database here, exactly as the confirm route does, so nothing in the fixture can supply an attribution.

Used by `scripts/gate_g3.py` and `engine/tests/test_export_g3.py`; not shipped in the deployment bundle.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..codes import Codes
from ..models import Case, EvidenceItem, Fact, Jurisdiction, ProfessionalRequirementResolution, Source
from ..professional_resolution import requirement_fingerprint
from ..models_identify import (ArticleDecision, BenchmarkRecord, IdentifyArticle, IdentifyResult, IdentifyTrace,
                               Term)
from ..section_c import section_c_rows
from ..section_d import section_d_plan

ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = ROOT / 'evals' / 'demo-cases'
CASES = ('a-manufacturer-nailbase-sheathing', 'b-contractor-firestop-nonconformance', 'c-homebuilder-infill-house')
DECIDED_AT = '2026-10-21T00:00:00Z'


def spec(name: str) -> dict:
    data = json.loads((DEMO_DIR / 'export' / f'{name}.json').read_text())
    # Preserve the journey candidate's fictional layout determinations with the
    # engine fixtures, without depending on a separately restored evals directory.
    resolutions = json.loads((Path(__file__).parent / 'fixtures' / 'demo-professional-resolutions.json').read_text())
    if name in resolutions and 'professional_requirement_resolution' not in data:
        data['professional_requirement_resolution'] = resolutions[name]
    return data


def _fact(key: str, value, ref: str, source_type: str = 'user_text') -> Fact:
    return Fact(field=key, value=value, kind='pointed', status='confirmed',
                source=Source(type=source_type, ref=ref, quote=str(value)))


def _identify(data: dict, codes: Codes) -> IdentifyResult:
    articles = []
    for rank, art in enumerate(data['articles'], start=1):
        rec = codes.provision(art['provision'], 'B')
        if rec is None:
            raise KeyError(f'{art["provision"]} is not a Division B article')
        words = ' '.join(rec['text'].split()[1:15])         # first words of the body, verbatim, after "1)"
        rows = section_c_rows([art['provision']], codes)
        articles.append(IdentifyArticle(
            rank=rank, provision=rec['id'], title=rec.get('article_title') or '', part=int(rec['id'].split('.')[0]),
            citation=rec['citation'], link=f'/code/{rec["id"]}', quote=words, quote_source='codedb',
            status=art['status'], commit_reason=art['commit_reason'], verifier='not_run',
            objectives=[Term(id=o) for o in dict.fromkeys(p.objective for r in rows for p in r.pairs)],
            functions=[Term(id=f) for f in dict.fromkeys(p.function for r in rows for p in r.pairs)],
            attribution_missing=not any(r.pairs for r in rows), decision=data['decisions'].get(rec['id'])))
    bench = data['benchmark']
    rec = codes.provision(bench['provision_id'], 'B')
    benchmark = BenchmarkRecord(identified=True, basis=bench['basis'], provision=rec['id'].split('(')[0],
                                provision_id=rec['id'], citation=rec['citation'], sentence=rec['text'],
                                departure=bench['departure'], departure_status='confirmed', attribution_missing=False)
    return IdentifyResult(
        mode='fake', source='fake', label='fake (demo fixture)', narrowed=True, articles=articles,
        committed=[a['provision'] for a in data['articles'] if a['status'] == 'committed'],
        benchmark=benchmark, scored_at=DECIDED_AT, description_sha256='0' * 64,
        decisions={k: ArticleDecision(decision=v, decided_at=DECIDED_AT) for k, v in data['decisions'].items()},
        trace=IdentifyTrace(config={}, config_hash='demo', exhaustive=True, articles_expected=len(articles),
                            articles_scored=len(articles), ranker='fake', verifier='none'))


def demo_case(name: str, codes: Codes | None = None) -> Case:
    codes = codes or Codes()
    data = spec(name)
    ref = f'demo-case:{name}:applicant'
    facts = [_fact(key, value, ref) for key, value in data['facts'].items()]
    facts += [_fact(f'not_applicable.{key}', reason, ref, 'user_click') for key, reason in data['not_applicable'].items()]
    case = Case(title=data['title'], jurisdiction=Jurisdiction(**data['jurisdiction']), facts=facts)
    case.identify = _identify(data['identify'], codes)
    for article in data['identify']['decisions']:
        rec = codes.provision(article, 'B')
        case.facts.append(Fact(field=f'citation.{article}', value=article, kind='exact', status='confirmed',
                               source=Source(type='user_click', ref=article, quote=rec['citation'])))
    case.provisions = list(data['provisions'])
    case.section_c = section_c_rows(case.provisions, codes)
    for doc in data['documents']:
        path = DEMO_DIR / name / doc['file']
        file_ref = path.relative_to(ROOT).as_posix()          # repo-relative: no local path reaches the PDF
        eid = doc['id']
        case.evidence.append(EvidenceItem(id=eid, description=doc['title'], status='evidence_listed', kind='file'))
        case.facts.append(Fact(field=f'evidence.{eid}.file_ref', value=file_ref, kind='pointed', status='confirmed',
                               source=Source(type='file', ref=file_ref, quote=path.read_text())))
        case.facts += [_fact(f'evidence.{eid}.{key}', doc[key], ref)
                       for key in ('title', 'responsible_party', 'issuer', 'date') if doc.get(key)]
    ids = [doc['id'] for doc in data['documents']]
    for n, item in enumerate(section_d_plan(case, codes).items):
        case.facts.append(_fact(f'evidence.{ids[n % len(ids)]}.covers.{item.id}', True, ref, 'user_click'))
    # Some completed layout examples need a scoped officer determination. This is
    # explicit fictional fixture data, never inferred from an applicant fact or
    # professional_status. Bind it after the entire example content is assembled.
    if resolution := data.get('professional_requirement_resolution'):
        case.professional_resolutions.append(ProfessionalRequirementResolution(
            **resolution, content_fingerprint=requirement_fingerprint(case)))
    return case


def demo_cases(codes: Codes | None = None) -> dict[str, Case]:
    codes = codes or Codes()
    return {name: demo_case(name, codes) for name in CASES}
