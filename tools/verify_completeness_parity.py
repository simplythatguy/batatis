#!/usr/bin/env python3
"""Full semantic parity: saved preflight -> actual export bytes -> same-file officer import.

Every item, finding, blocking decision and normalized value is compared. Extraction
uncertainty is an ordinary state that must match; it is never accepted as disagreement.
Repository demo statements stay unchanged. Their Markdown bytes are rendered into
readable source PDFs, stored through the real owned-file adapter and kept in the package.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.codes import Codes
from engine.completeness_report import saved_case_response
from engine.export.demo_cases import CASES, DEMO_DIR, demo_case, spec
from engine.export.scc import ExportBlocked, export_case
from engine.models import Fact, Source
from engine.professional_resolution import requirement_fingerprint
from engine.review.package import review_case, review_uploads
from engine.store import CaseStore
from engine.tests.package_review_fixtures import text_pdf

SCENARIOS = ('baseline', 'vague-risk', 'unrelated-measures', 'assumed-fact', 'second-site',
             'missing-attachment', 'unconfirmed-owner', 'attachment-citation', 'attachment-contradiction')


def semantic(report):
    """Exclude source pointers only. Values retain case, punctuation, numbers and all non-whitespace."""
    def ws(value):
        return ' '.join(value.split()) if isinstance(value, str) else value
    fields = ('key', 'field', 'section', 'label', 'verdict', 'reason_code', 'certainty', 'finding_status',
              'severity', 'routed_to', 'export_blocking', 'submission_blocking', 'value', 'reason', 'fix_hint')
    items = []
    for item in report.items:
        row = {key: ws(getattr(item, key)) for key in fields}
        row['citations'] = [ws(citation) for citation in item.citations]
        items.append(row)
    assert len({item['key'] for item in items}) == len(items), 'requirement keys must be unique'
    return {'schema_version': report.schema_version, 'policy_version': report.policy_version, 'stage': report.stage,
            'administrative_only': report.administrative_only,
            'not_a_compliance_determination': report.not_a_compliance_determination,
            'ready_for_export': report.ready_for_export,
            'export_reasons': [ws(reason) for reason in report.export_reasons],
            'items': sorted(items, key=lambda item: item['key'])}


def fact(key, value, *, confirmed=True):
    return Fact(field=key, value=value, kind='pointed', status='confirmed' if confirmed else 'unconfirmed',
                source=Source(type='user_text', ref='SYNTHETIC parity mutation', quote=str(value)))


def run(out):
    out.mkdir(parents=True, exist_ok=True)
    codes = Codes()
    manifest = {'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'code_db_sha256': hashlib.sha256(codes.db_path.read_bytes()).hexdigest(),
                'scope': 'all administrative items and findings; pointers/sources excluded from semantic equality',
                'applications': 3, 'scenarios_per_application': len(SCENARIOS), 'packages': [],
                'item_comparisons': 0, 'exact_packages': 0, 'successful_official_exports': 0, 'failures': []}
    for name in CASES:
        folder = out / name
        folder.mkdir(exist_ok=True)
        store = CaseStore(folder / 'cases.sqlite')
        base = demo_case(name, codes)
        store.put(base)
        original_sources = []
        documents = spec(name)['documents']
        for document in documents:
            path = DEMO_DIR / name / document['file']
            raw = path.read_bytes()
            data = text_pdf(raw.decode('utf-8').splitlines())
            source_name = Path(document['file']).stem + '.pdf'
            saved = store.put_file(base.id, source_name, data)
            entry = next(entry for entry in base.facts if entry.field == f'evidence.{document["id"]}.file_ref')
            entry.value = saved['id']
            entry.source = Source(type='file', ref=saved['id'], quote=raw.decode('utf-8'))
            original_sources.append({'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(raw).hexdigest(),
                                     'stored_pdf_sha256': hashlib.sha256(data).hexdigest()})
        # Explicit fictional fixture setup: bind the fixture's recorded determination to the same
        # supplied text now held as owned PDFs. Mutations subsequently invalidate it normally.
        for resolution in base.professional_resolutions:
            resolution.content_fingerprint = requirement_fingerprint(base)
        for scenario in SCENARIOS:
            case = base.model_copy(deep=True)
            if scenario == 'vague-risk':
                case.facts.append(fact('process.risk_assessment', 'low risk'))
            elif scenario == 'unrelated-measures':
                case.facts.append(fact('process.mitigating_measures', 'Violet umbrellas rotate quietly beside distant galaxies.'))
            elif scenario == 'assumed-fact':
                case.facts.append(fact('process.assumptions_and_limits', 'The emergency crews will arrive within three minutes.'))
            elif scenario == 'second-site':
                case.facts.append(fact('additional_location', '999 Other Example Street'))
            elif scenario == 'missing-attachment':
                key = f'evidence.{documents[0]["id"]}.file_ref'
                case.facts = [entry for entry in case.facts if entry.field != key]
            elif scenario == 'unconfirmed-owner':
                case.facts.append(fact('owner_name', 'SYNTHETIC pending changed owner', confirmed=False))
            elif scenario in ('attachment-citation', 'attachment-contradiction'):
                content = ('SYNTHETIC parity mutation\nNBC(AE) 2023 Division B 99.99.99.99.'
                           if scenario == 'attachment-citation' else 'SYNTHETIC parity mutation\nlimiting distance: 1.20 m')
                if scenario == 'attachment-contradiction':
                    original = next(entry.value for entry in reversed(case.facts) if entry.field == 'alternative_description')
                    case.facts.append(fact('alternative_description', original + ' limiting distance: 0.40 m'))
                saved = store.put_file(case.id, 'actual-mutated-source.pdf', text_pdf(content.splitlines()))
                entry = next(entry for entry in case.facts if entry.field == f'evidence.{documents[0]["id"]}.file_ref')
                entry.value = saved['id']
                entry.source = Source(type='file', ref=saved['id'], quote='A benign stale extraction that must not own checks.')
            case = store.put(case)
            applicant = saved_case_response(case, codes, store=store).policy
            saved_officer = review_case(case, codes, store).policy
            try:
                exported = export_case(case, codes=codes, store=store)
                official = True
                manifest['successful_official_exports'] += 1
            except ExportBlocked as blocked:
                assert blocked.reasons == applicant.export_reasons
                exported = export_case(case, codes=codes, store=store, draft=True)
                official = False
            path = folder / f'{scenario}.pdf'
            path.write_bytes(exported.pdf)
            officer = review_uploads([('same-file-import.pdf', path.read_bytes())], codes)
            left, saved_semantic, right = semantic(applicant), semantic(saved_officer), semantic(officer.policy)
            exact = left == saved_semantic == right
            manifest['item_comparisons'] += len(left['items'])
            if not exact:
                manifest['failures'].append(f'{name}/{scenario}: full semantic mismatch')
                (folder / f'{scenario}-mismatch.json').write_text(json.dumps({'applicant': left, 'officer': right}, indent=2))
            else:
                manifest['exact_packages'] += 1
            if scenario != 'baseline' and official:
                manifest['failures'].append(f'{name}/{scenario}: incomplete mutation unexpectedly exported officially')
            if name == 'b-contractor-firestop-nonconformance' and scenario == 'baseline' and not official:
                manifest['failures'].append('Completed contractor example did not produce a genuine final successful export')
            if scenario == 'attachment-citation' and not any(item.reason_code == 'nonexistent_provision' for item in applicant.items):
                manifest['failures'].append(f'{name}: actual attachment citation was missed')
            if scenario == 'attachment-contradiction' and not any(item.reason_code == 'contradiction' for item in applicant.items):
                manifest['failures'].append(f'{name}: actual attachment contradiction was missed')
            (folder / f'{scenario}-applicant.json').write_text(applicant.model_dump_json(indent=2))
            (folder / f'{scenario}-officer.json').write_text(officer.policy.model_dump_json(indent=2))
            record = {'application': name, 'scenario': scenario, 'official_export': official, 'exact': exact,
                      'items': len(left['items']), 'findings': len(officer.findings),
                      'blockers': len(applicant.export_reasons), 'pdf': str(path),
                      'pdf_sha256': hashlib.sha256(exported.pdf).hexdigest(), 'sources': original_sources}
            manifest['packages'].append(record)
            print(json.dumps({key: value for key, value in record.items() if key != 'sources'}), flush=True)
    assert manifest['successful_official_exports'] >= 1
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({key: value for key, value in manifest.items() if key != 'packages'}, indent=2))
    return not manifest['failures']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=Path('/tmp/batatis-shared-completeness-full-parity'))
    raise SystemExit(0 if run(parser.parse_args().out) else 1)
