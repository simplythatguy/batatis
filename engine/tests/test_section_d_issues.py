"""Section D issues recommend evidence. They do not certify a design or invent a citation."""
import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from engine.api import create_app
from engine.models import Case, Source
from engine.section_d import ALTERNATIVE_EVIDENCE_TYPES, CONFIDENCE_LADDER
from engine.professional import ProfessionalFacts
from engine.section_d_flag_eval import (
    RULE_IDS, Signals, VariantScore, counterfactual, flag_label, flag_question, headline, load_cases,
    load_codes, load_heldout, main, score, winner,
)
from engine.section_d_issues import (
    GENERIC_FALLBACK_QUESTION, PROCESS_RULES, PROFESSIONAL_REQUEST, PROFESSIONAL_RULES,
    generic_fallback_on_dev, professional_confirmed, render_practice, section_d_issues,
)
from engine.store import CaseStore
from engine.tests.case_builder_fixtures import fact

# Recommendation text must not claim compliance or safety. Objective titles from the
# code ("Safety") are not copied into these strings; the test scans the whole payload.
CLAIM_PHRASES = (
    r'\bcomplies\b', r'\bcompliant\b', r'\bcompliance\b', r'\bsafe\b', r'\bsafety\b',
    r'meets the code', r'meets code', r'satisfies the code', r'\bwe conclude\b',
    r'has been approved', r'\bis approved\b', r'performance is achieved',
    r'equivalent performance is', r'design is acceptable', r'this design complies',
)

BENCHMARK = '9.10.15.5.(8)'
NO_ROW = '9.10.14.2.(1)'
UNKNOWN = '9.99.99.99.(1)'


class FakeCodes:
    """In-memory stand-in. Every citation string is recorded when it is handed out."""

    def __init__(self):
        self.rows = {}
        self.issued: set[str] = set()
        # Like Codes: a database path. It does not exist, so text validation never reads the real corpus.
        self.db_path = Path('unused-synthetic-corpus')

    def add(self, division, provision_id, **extra):
        citation = extra.pop('citation', f'fixture:{division}:{provision_id}')
        row = {'id': provision_id, 'division': division, 'citation': citation, 'level': 'sentence',
               'children': [], 'attributions': [], 'attribution_status': {'status': 'none', 'root_provision': None,
               'root_method': None}, 'intents': [], 'intent_comparison': []}
        row.update(extra)
        self.rows[(division, provision_id)] = row
        return self

    def provision(self, provision_id, division='B'):
        if division is None:
            # Like Codes.provision: an unqualified id resolves only when exactly one division has it.
            found = [row for (div, pid), row in self.rows.items() if pid == provision_id]
            if len(found) > 1:
                raise ValueError(f'{provision_id} exists in several divisions')
            row = found[0] if found else None
        else:
            row = self.rows.get((division, provision_id))
        if row:
            self.issued.add(row['citation'])
        return row

    def citation(self, provision_id, division='B'):
        row = self.provision(provision_id, division)
        return row['citation'] if row else None

    def definition(self, code):
        return None


def codes_with_rules():
    from engine.human_review import REVIEW_PROVISIONS
    codes = FakeCodes()
    for division, provision_id in (*RULE_IDS, *REVIEW_PROVISIONS):
        codes.add(division, provision_id)
    codes.add('B', BENCHMARK, attribution_status={'status': 'direct', 'root_provision': None, 'root_method': None},
              attributions=[{'bracket': '[F03-OP3.1]', 'clauses': [], 'application_note': None,
                             'table_id': 'Table 9.38.1.1.', 'pdf_page': 1, 'fs': ['F03'], 'objectives': ['OP3.1']}])
    codes.add('B', NO_ROW)
    # Every exported appendix cites the alternative-solution clause; the shared policy reads it back.
    codes.add('A', '1.2.1.1.(1)(b)')
    return codes


def _strings(payload):
    if isinstance(payload, str):
        yield payload
    elif isinstance(payload, dict):
        for value in payload.values():
            yield from _strings(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _strings(value)


def _citations(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key == 'citation' and isinstance(value, str):
                yield value
            else:
                yield from _citations(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _citations(value)


def _house_facts():
    values = dict(occupancy='single_family', part4_design=False, preserved_wood_foundation_part4=False,
                  roof_trusses=False, prescriptive_route_confirmed=True, ahj_requires_professional=False,
                  special_safety_concerns=False, professional_judgement_required=False,
                  professional_scope_resolved=True, fire_suppression=False, fire_alarm=False)
    return [fact(key, value) for key, value in values.items()]


def test_confirmed_provision_recommends_ladder_and_lists_empty_process_fields():
    codes = codes_with_rules()
    issue = section_d_issues(Case(provisions=[BENCHMARK], facts=[fact('pathway', 'alternative')]), codes)[0]
    assert issue.provision.provision_id == BENCHMARK and issue.provision.citation == codes.rows[('B', BENCHMARK)]['citation']
    assert issue.objective == 'OP3.1' and issue.function == 'F03'
    assert issue.recommended_types == CONFIDENCE_LADDER + ALTERNATIVE_EVIDENCE_TYPES
    empty = [field.id for field in issue.empty_process_fields]
    assert {'risk_assessment', 'mitigating_measures', 'assumptions_and_limits'} <= set(empty)
    assert not set(empty) & set(issue.recommended_types)
    assert issue.status == 'open' and issue.practice_of_engineering.value == 'unknown'
    assert issue.practice_of_engineering.question


def test_unknown_reference_has_no_citation_and_missing_attribution_asks():
    codes = codes_with_rules()
    issues = section_d_issues(Case(provisions=[UNKNOWN, NO_ROW]), codes)
    missing = next(issue for issue in issues if issue.entered_reference == UNKNOWN)
    assert missing.provision is None and missing.question
    assert UNKNOWN not in ''.join(_citations(missing.model_dump()))
    assert not re.search(r'NBC\(AE\).{0,80}' + re.escape(UNKNOWN), missing.model_dump_json())
    blank = next(issue for issue in issues if issue.provision and issue.provision.provision_id == NO_ROW)
    assert blank.objective is None and blank.function is None and blank.question
    assert blank.provision.citation == codes.rows[('B', NO_ROW)]['citation']


def test_no_issue_text_claims_compliance_or_safety_and_citations_stay_inside_codedb():
    codes = codes_with_rules()
    cases = [
        Case(provisions=[BENCHMARK, UNKNOWN, NO_ROW]),
        Case(provisions=[BENCHMARK], facts=[fact('part4_design', True)]),
        Case(provisions=[BENCHMARK], facts=_house_facts()),
        Case(provisions=[BENCHMARK], facts=[fact('span_m', 18)]),
        Case(provisions=[BENCHMARK], facts=[fact('pathway', 'acceptable')]),
    ]
    for case in cases:
        payload = [issue.model_dump() for issue in section_d_issues(case, codes)]
        # Statute titles such as the Safety Codes Act are pinpoints, not a safety claim.
        scanned = json.loads(json.dumps(payload))
        def drop_cites(node):
            if isinstance(node, dict):
                return {key: drop_cites(value) for key, value in node.items()
                        if key not in ('cite', 'quote', 'act')}
            if isinstance(node, list):
                return [drop_cites(value) for value in node]
            return node
        blob = json.dumps(drop_cites(scanned))
        for pattern in CLAIM_PHRASES:
            assert re.search(pattern, blob, re.I) is None, pattern
        for citation in _citations(payload):
            assert citation in codes.issued
        assert 'NBC(AE)' not in blob


def test_span_is_part4_and_cites_only_the_existing_division_c_rule():
    codes = codes_with_rules()
    issue = section_d_issues(Case(provisions=[BENCHMARK], facts=[fact('span_m', 18)]), codes)[0]
    assert issue.practice_of_engineering.value is True
    assert issue.practice_of_engineering.rule == '2.4.1.2.(1)'
    assert issue.practice_of_engineering.citation == 'fixture:C:2.4.1.2.(1)'
    assert issue.practice_of_engineering.citation in codes.issued
    assert '9.23.1.1' not in issue.model_dump_json()


def test_status_lists_evidence_only_after_a_confirmed_professional():
    codes = codes_with_rules()
    bare = section_d_issues(Case(provisions=[BENCHMARK], facts=[fact('part4_design', True)]), codes)[0]
    assert bare.status == 'needs_professional' and bare.practice_of_engineering.value is True
    assert bare.practice_of_engineering.question == PROFESSIONAL_REQUEST
    assert bare.practice_of_engineering.division == 'C' and bare.practice_of_engineering.citation in codes.issued
    file = Source(type='file', ref='applicant-report.pdf', quote='Applicant report metadata.')
    named = Case(provisions=[BENCHMARK], facts=[fact('part4_design', True)])
    named.facts += [fact(f'evidence.{bare.id}.file_ref', file.ref, source=file),
                    fact(f'evidence.{bare.id}.responsible_party', 'Named applicant professional', source=file),
                    fact(f'evidence.{bare.id}.professional_seal', 'stamp image on the pdf', source=file)]
    supplied = section_d_issues(named, codes)[0]
    assert supplied.status == 'needs_professional' and supplied.practice_of_engineering.value is True
    role_and_document_seal = Case(provisions=[BENCHMARK], facts=[
        fact('part4_design', True),
        fact('professional.role', 'engineer'),
        fact(f'evidence.{bare.id}.file_ref', file.ref, source=file),
        fact(f'evidence.{bare.id}.professional_seal', 'stamp image on the pdf', source=file),
        fact('professional.registration_number', 'from the pdf', source=file),
    ])
    assert section_d_issues(role_and_document_seal, codes)[0].status == 'needs_professional'
    confirmed = Case(provisions=[BENCHMARK], facts=[
        fact('part4_design', True),
        fact('professional.role', 'architect'),
        fact('professional.registration_number', 'AAA-000'),
        fact(f'evidence.{bare.id}.file_ref', file.ref, source=file),
    ])
    listed = section_d_issues(confirmed, codes)[0]
    assert professional_confirmed(confirmed) and listed.status == 'evidence_listed'
    house = section_d_issues(Case(provisions=[BENCHMARK], facts=_house_facts()), codes)[0]
    assert house.practice_of_engineering.value == 'unknown' and house.status == 'open'
    assert house.routed_to == 'officer'
    unsigned = Source(type='file', ref='unsigned-note.pdf', quote='Applicant file metadata.')
    unknown = section_d_issues(Case(provisions=[BENCHMARK]), codes)[0]
    unknown_case = Case(provisions=[BENCHMARK], facts=[
        fact(f'evidence.{unknown.id}.file_ref', unsigned.ref, source=unsigned)])
    still_open = section_d_issues(unknown_case, codes)[0]
    assert still_open.practice_of_engineering.value == 'unknown' and still_open.status == 'open'
    assert still_open.practice_of_engineering.question != PROFESSIONAL_REQUEST
    house_case = Case(provisions=[BENCHMARK], facts=_house_facts() + [
        fact(f'evidence.{house.id}.file_ref', unsigned.ref, source=unsigned)])
    supplied_house = section_d_issues(house_case, codes)[0]
    assert supplied_house.practice_of_engineering.value == 'unknown' and supplied_house.status == 'open'


def test_role_variants_confirm_only_with_an_applicant_number_or_seal():
    codes = codes_with_rules()
    bare = section_d_issues(Case(provisions=[BENCHMARK], facts=[fact('part4_design', True)]), codes)[0]
    file = Source(type='file', ref='applicant-report.pdf', quote='Applicant report metadata.')
    accepted = (
        'structural engineer', 'professional engineer', 'P.Eng.', 'P Eng', 'PEng',
        'registered professional engineer', 'ENGINEER', 'architect', 'registered architect',
        'Architect!',
    )
    rejected = ('sales', 'rep', 'supplier', 'manufacturer', 'salesperson', 'vendor', 'sales engineer')

    def listed(role: str, **extra):
        return Case(provisions=[BENCHMARK], facts=[
            fact('part4_design', True),
            fact('professional.role', role),
            fact(f'evidence.{bare.id}.file_ref', file.ref, source=file),
            *extra.get('facts', []),
        ])

    for role in accepted:
        numbered = listed(role, facts=[fact('professional.registration_number', 'APEGA-1')])
        assert professional_confirmed(numbered), role
        assert section_d_issues(numbered, codes)[0].status == 'evidence_listed', role
        role_only = listed(role)
        assert not professional_confirmed(role_only), role
        assert section_d_issues(role_only, codes)[0].status == 'needs_professional', role
    sealed = listed('P.Eng.', facts=[fact('professional.seal', 'applicant-confirmed seal')])
    assert professional_confirmed(sealed)
    assert section_d_issues(sealed, codes)[0].status == 'evidence_listed'
    for role in rejected:
        case = listed(role, facts=[fact('professional.registration_number', 'APEGA-1')])
        assert not professional_confirmed(case), role
        assert section_d_issues(case, codes)[0].status == 'needs_professional', role


def test_part3_sales_rep_email_stays_needs_professional():
    """Case B input: a Part 3 building plus the sales-rep email. The email is not a professional.

    The quote is the body of evals/demo-cases/b-contractor-firestop-nonconformance/input/
    manufacturer-ej-draft-EXAMPLE.md. Answer keys are not read. When that file is on the
    branch, the quote has to still be in it.
    """
    email = Path('evals/demo-cases/b-contractor-firestop-nonconformance/input/manufacturer-ej-draft-EXAMPLE.md')
    quote = ("Hi Carlos, FireSeal 200 performs great on plastic pipe too, we've seen it in lots of jobs. "
             "Treat this as our engineering judgment that it'll hold the rating. Thanks!")
    if email.exists():
        assert quote in email.read_text()
    codes = codes_with_rules()
    part3 = [fact('occupancy', 'mercantile'), fact('storeys', 5), fact('building_area_m2', 800.0)]
    bare = section_d_issues(Case(provisions=[BENCHMARK], facts=part3), codes)[0]
    assert bare.practice_of_engineering.value is True and bare.status == 'needs_professional'
    file = Source(type='file', ref='manufacturer-ej-draft-EXAMPLE.md', quote=quote)
    case = Case(provisions=[BENCHMARK], facts=list(part3) + [
        fact(f'evidence.{bare.id}.file_ref', file.ref, source=file),
        fact(f'evidence.{bare.id}.responsible_party', 'sales rep, Example Sealants Co.', source=file),
        fact(f'evidence.{bare.id}.professional_seal', 'stamp mentioned in the sales email', source=file),
    ])
    snapshot = [item.model_dump() for item in case.facts]
    issue = section_d_issues(case, codes)[0]
    assert [item.model_dump() for item in case.facts] == snapshot
    assert issue.status == 'needs_professional'
    assert issue.practice_of_engineering.question == PROFESSIONAL_REQUEST
    payload = issue.model_dump_json()
    assert 'FireSeal' not in payload and 'Example Sealants' not in payload and 'sales rep' not in payload


def _visible(payload) -> list[str]:
    found: list[str] = []

    def walk(node, skip: bool = False):
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, skip or key in ('required', 'general_required'))
        elif isinstance(node, list):
            for value in node:
                walk(value, skip)
        elif isinstance(node, str) and not skip:
            found.append(node)

    walk(payload)
    return found


def test_unresolved_item_names_what_decides_it_and_who():
    """An open Section D item names the deciding question and routed_to. It does not say depends."""
    codes = codes_with_rules()
    case = Case(provisions=[BENCHMARK])
    issue = section_d_issues(case, codes)[0]
    flag = issue.practice_of_engineering
    assert flag.value == 'unknown' and flag.routed_to in ('officer', 'professional', 'applicant')
    who = {'officer': 'officer', 'applicant': 'applicant', 'professional': 'professional'}[flag.routed_to]
    assert flag.question and flag.question in flag.reason
    assert who in flag.reason.casefold() and 'decides' in flag.reason.casefold()
    from engine.completeness import check_completeness
    from engine.professional import professional_involvement
    gap = next(item for item in check_completeness(case, codes) if item.field == 'professional_requirement')
    assert gap.routed_to == flag.routed_to
    assert who in gap.message.casefold() and 'decides' in gap.message.casefold()
    result = professional_involvement(case, codes)
    assert result.decision and who in result.decision.casefold() and 'decides' in result.decision.casefold()
    blobs = [flag.reason, flag.question or '', gap.message, gap.fix_hint, result.decision, result.general_decision]
    blobs += [prompt.text + ' ' + prompt.help for prompt in flag.prompts]
    blobs += [reason.message for reason in result.reasons if reason.required == 'depends']
    joined = '\n'.join(blobs)
    assert 'depends. depends' not in joined.casefold()
    assert re.search(r'\bdepends\b', joined, re.I) is None
    for piece in _visible(issue.model_dump()) + _visible(gap.model_dump()):
        assert piece.strip().casefold() not in {'depends', 'depends.'}
        assert 'depends. depends' not in piece.casefold()


def test_firestop_case_asks_about_the_penetration_not_wood_or_farm():
    from engine.human_review import MANDATORY_ORDER, mandatory_hits
    from engine.professional import ProfessionalFacts, professional_involvement
    codes = codes_with_rules()
    codes.add('B', '3.1.9.1.(1)')
    codes.add('B', '3.1.9.4.(4)')
    carlos = Case(
        title='Firestop at sprinkler-pipe penetrations',
        provisions=['3.1.9.1.(1)', '3.1.9.4.(4)'],
        facts=[
            fact('occupancy', 'mixed'), fact('storeys', 5), fact('building_area_m2', 1200.0),
            fact('part4_design', True),
        ],
    )
    farm = Case(
        title='Firestop at a fire separation',
        provisions=['3.1.9.1.(1)'],
        facts=[fact('occupancy', 'farm'), fact('part4_design', True), fact('storeys', 2)],
    )
    for case in (carlos, farm):
        result = professional_involvement(case, codes)
        asked = ' '.join(result.questions).casefold()
        assert 'preserved wood' not in asked
        assert 'roof truss' not in asked
        assert 'farm building' not in asked
        assert 'beams, connections or foundations' not in asked
        assert ('fire separation' in asked or 'penetration' in asked) and 'sprinkler' in asked
        assert sum('System presence or applicability' in reason.message for reason in result.reasons) <= 1
        issue = section_d_issues(case, codes)[0]
        prompts = ' '.join(prompt.text for prompt in issue.practice_of_engineering.prompts).casefold()
        assert 'preserved wood' not in prompts and 'roof truss' not in prompts and 'farm building' not in prompts
        assert ('fire separation' in prompts or 'penetration' in prompts) and 'sprinkler' in prompts
    screen = professional_involvement(ProfessionalFacts(
        occupancy='mercantile', storeys=5, building_area_m2=800.0), codes)
    assert sum('System presence or applicability' in reason.message for reason in screen.reasons) == 1
    assert any('fire suppression' in question for question in screen.questions)
    hits = mandatory_hits(carlos, codes)
    ids = [hit.trigger_id for hit in hits]
    assert MANDATORY_ORDER == (
        'HR-03', 'HR-01', 'HR-06', 'HR-07', 'HR-05', 'HR-04', 'HR-11', 'HR-14', 'HR-13', 'HR-12')
    assert ids == sorted(set(ids), key=MANDATORY_ORDER.index)
    assert ids[0] == 'HR-03' and 'HR-04' in ids
    assert hits[0].cite == codes.provision('2.4.1.2.(1)', 'C')['citation']
    hr04 = next(hit for hit in hits if hit.trigger_id == 'HR-04')
    assert hr04.cite == codes.provision('1.3.3.2.(1)', 'A')['citation']


def test_five_storey_firestop_does_not_ask_part9_questions():
    """Part 3 screening, including a 5-storey firestop, skips wood, truss, and farm questions."""
    from engine.human_review import MANDATORY_ORDER, mandatory_hits
    from engine.professional import _PART_QUESTION, professional_involvement
    codes = codes_with_rules()
    codes.add('B', '3.1.9.1.(1)')
    codes.add('B', '3.1.9.4.(4)')
    codes.add('B', '3.2.2.2.(1)')
    firestop = Case(
        title='Firestop at sprinkler-pipe penetrations',
        provisions=['3.1.9.1.(1)', '3.1.9.4.(4)'],
        facts=[
            fact('occupancy', 'mixed'), fact('storeys', 5), fact('building_area_m2', 1200.0),
            fact('part4_design', True),
        ],
    )
    by_storeys = Case(provisions=[BENCHMARK], facts=[
        fact('occupancy', 'mercantile'), fact('storeys', 5), fact('part4_design', True),
    ])
    by_area = Case(provisions=[BENCHMARK], facts=[
        fact('occupancy', 'mercantile'), fact('storeys', 2), fact('building_area_m2', 601.0),
        fact('part4_design', True),
    ])
    by_occupancy = Case(provisions=[BENCHMARK], facts=[
        fact('occupancy', 'assembly'), fact('storeys', 1), fact('part4_design', True),
    ])
    by_prefix = Case(provisions=['3.2.2.2.(1)'], facts=[
        fact('occupancy', 'mercantile'), fact('storeys', 2), fact('part4_design', True),
    ])
    for case in (firestop, by_storeys, by_area, by_occupancy, by_prefix):
        asked = ' '.join(professional_involvement(case, codes).questions).casefold()
        assert 'preserved wood' not in asked
        assert 'roof truss' not in asked
        assert 'farm building' not in asked
        assert _PART_QUESTION.casefold() not in asked
    issue = section_d_issues(firestop, codes)[0]
    prompts = ' '.join(prompt.text for prompt in issue.practice_of_engineering.prompts).casefold()
    assert 'preserved wood' not in prompts and 'roof truss' not in prompts and 'farm building' not in prompts
    assert 'fire separation' in prompts and 'sprinkler' in prompts
    ids = [hit.trigger_id for hit in mandatory_hits(firestop, codes)]
    assert ids == sorted(ids, key=MANDATORY_ORDER.index)
    assert 'HR-04' in ids and ids[0] == 'HR-03'
    unknown = Case(facts=[fact('occupancy', 'mixed'), fact('part4_design', True)])
    unknown_questions = professional_involvement(unknown, codes).questions
    folded = ' '.join(unknown_questions).casefold()
    assert 'preserved wood' not in folded and 'roof truss' not in folded and 'farm building' not in folded
    assert sum(question == _PART_QUESTION for question in unknown_questions) == 1
    part9 = Case(provisions=[BENCHMARK], facts=[
        fact('occupancy', 'single_family'), fact('storeys', 2), fact('part4_design', True),
    ])
    part9_asked = ' '.join(professional_involvement(part9, codes).questions).casefold()
    assert 'preserved wood' in part9_asked and 'roof truss' in part9_asked


def test_unsigned_vendor_email_is_not_professional_evidence():
    from engine.completeness import check_completeness, seal_is_professional_evidence
    from engine.section_d import supporting_documents
    codes = codes_with_rules()
    quote = ("Hi Carlos, FireSeal 200 performs great on plastic pipe too, we've seen it in lots of jobs. "
             "Treat this as our engineering judgment that it'll hold the rating. Thanks!")
    email = Path('evals/demo-cases/b-contractor-firestop-nonconformance/input/manufacturer-ej-draft-EXAMPLE.md')
    if email.exists():
        assert quote in email.read_text()
    bare = section_d_issues(Case(provisions=[BENCHMARK], facts=[fact('part4_design', True)]), codes)[0]
    file = Source(type='file', ref='vendor-email.eml', quote=quote)
    case = Case(provisions=[BENCHMARK], facts=[
        fact('part4_design', True),
        fact(f'evidence.{bare.id}.file_ref', file.ref, source=file),
        fact(f'evidence.{bare.id}.responsible_party', 'sales rep', source=file),
        fact(f'evidence.{bare.id}.issuer', 'vendor', source=file),
        fact(f'evidence.{bare.id}.professional_seal', 'stamp mentioned in the sales email', source=file),
    ])
    issue = section_d_issues(case, codes)[0]
    assert not professional_confirmed(case)
    assert issue.status == 'needs_professional'
    docs = supporting_documents(case)
    assert docs and all(not seal_is_professional_evidence(doc, quote=quote) for doc in docs)
    assert any(gap.field == 'professional_authentication' and gap.id.startswith('D12:')
               for gap in check_completeness(case, codes))
    # File-read metadata counts only when the quoted source text contains it.
    report = Source(type='file', ref='report.pdf', quote='Laboratory report by A. Engineer, stamp image on the pdf.')
    honest = Case(provisions=[BENCHMARK], facts=[
        fact('part4_design', True),
        fact(f'evidence.{bare.id}.file_ref', report.ref, source=report),
        fact(f'evidence.{bare.id}.responsible_party', 'A. Engineer', source=report),
        fact(f'evidence.{bare.id}.professional_seal', 'stamp image on the pdf', source=report),
    ])
    assert not any(gap.field == 'professional_authentication' for gap in check_completeness(honest, codes))


def test_missing_division_c_citation_is_unknown_and_the_route_does_not_500(tmp_path):
    codes = codes_with_rules()
    codes.rows[('C', '2.4.1.2.(1)')]['citation'] = ''
    issue = section_d_issues(Case(provisions=[BENCHMARK], facts=[fact('part4_design', True)]), codes)[0]
    assert issue.practice_of_engineering.value == 'unknown'
    assert issue.practice_of_engineering.reason
    assert issue.practice_of_engineering.question
    store = CaseStore(tmp_path / 'cases.sqlite')
    client = TestClient(create_app(store, codes), raise_server_exceptions=False)
    case = store.put(Case(provisions=[BENCHMARK], facts=[fact('part4_design', True)]))
    response = client.get(f'/cases/{case.id}/section-d/issues')
    assert response.status_code == 200
    flag = response.json()['items'][0]['practice_of_engineering']
    assert flag['value'] == 'unknown'
    assert flag['reason']
    assert flag['question']
    from engine.professional import ProfessionalReason, ProfessionalResult
    unmapped = ProfessionalResult(
        required='yes', general_required='yes',
        reasons=[ProfessionalReason(code='not_in_the_table', required='yes', message='Ask.',
                                    citation='fixture:C:2.4.1.1.(3)')],
        questions=[])
    flag = render_practice(unmapped, codes)
    assert flag.value == 'unknown'
    assert flag.reason
    assert flag.question


def test_acceptable_path_drops_variance_process_fields_and_extra_evidence_types():
    case = Case(provisions=[BENCHMARK], facts=[fact('pathway', 'acceptable')])
    issue = section_d_issues(case, codes_with_rules())[0]
    assert issue.empty_process_fields == ()
    assert issue.recommended_types == CONFIDENCE_LADDER


def test_no_benchmark_asks_and_does_not_invent_a_provision():
    issue = section_d_issues(Case(), codes_with_rules())[0]
    assert issue.provision is None and issue.question and issue.status == 'open'


def test_route_is_read_only_and_missing_case_is_404(tmp_path):
    store = CaseStore(tmp_path / 'cases.sqlite')
    client = TestClient(create_app(store, codes_with_rules()))
    assert client.get('/cases/missing/section-d/issues').status_code == 404
    case = store.put(Case(provisions=[BENCHMARK, UNKNOWN]))
    before = store.get(case.id).model_dump_json()
    response = client.get(f'/cases/{case.id}/section-d/issues')
    assert response.status_code == 200
    body = response.json()['items']
    assert body[0]['entered_reference'] == UNKNOWN and body[0]['provision'] is None
    assert body[1]['provision']['citation']
    assert store.get(case.id).model_dump_json() == before


def test_missing_codedb_returns_503_without_a_path(tmp_path, monkeypatch):
    monkeypatch.setenv('BATATIS_CODEDB', str(tmp_path / 'no-such.sqlite'))
    client = TestClient(create_app(CaseStore(tmp_path / 'cases.sqlite')))
    created = client.post('/cases', json={})
    assert created.status_code == 201
    response = client.get(f"/cases/{created.json()['id']}/section-d/issues")
    assert response.status_code == 503
    body = response.json()
    assert body['detail'] == 'code database not found'
    assert set(body) == {'detail', 'meta'}
    assert body['meta']['notice']
    assert 'no-such.sqlite' not in response.text
    assert str(tmp_path) not in response.text


def test_rule_table_uses_only_provisions_already_in_the_repo():
    professional = Path('engine/professional.py').read_text()
    process = Path('engine/process_fields.py').read_text()
    for _division, provision_id, source in (*PROFESSIONAL_RULES, *PROCESS_RULES):
        if source.startswith('engine/professional.py'):
            assert provision_id in professional, provision_id
        elif source.startswith('engine/process_fields.py'):
            assert provision_id in process, provision_id
        else:
            raise AssertionError(source)
    for path in ('engine/section_d_issues.py', 'engine/section_d_flag_eval.py', 'docs/api-contract.md'):
        assert '9.23.1.1' not in Path(path).read_text()


def test_eval_script_prints_in_sample_wilson_table(capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
    codes, _codedb = load_codes()
    dev = score(codes)
    held = score(codes, load_heldout())
    expected = headline(dev, held)
    shipped = winner(dev)
    assert shipped in expected
    assert f'shipped {shipped}:' in expected
    assert out.startswith(expected + '\n')
    disclosure = (
        'Part 4 on text-only cases is derived from stated facts. A wood-frame building inside '
        'Part 9 with no Part 4 trigger is part4_design false, so the screen can answer no. '
        'On this dev set (model-checked, in-sample) the shipped screen still emits 0 no labels.'
    )
    construction = (
        '(on the 60 text-only dev cases it answered only yes or ask, 0 no, '
        'so 0 under-flags is partly by design; since 4425089 it can answer no '
        'when stated facts clear every trigger)'
    )
    script = Path('engine/section_d_flag_eval.py').read_text()
    assert disclosure in script
    assert construction in script
    # The docs carry the pinned, measured receipt (124ef4d) instead of the live headline.
    receipt = ('At measured source `d479e82`, the shipped facts-only `rules_plus_unknown` agreed with '
               'model gold on 50/60 text-only dev cases (0 no outputs, 27 unknowns)')
    for path in ('docs/api-contract.md', 'README.md'):
        text = Path(path).read_text()
        assert receipt in text
        assert 'Unshipped `rules_only` had 55/60 dev agreement and 1 under-flag.' in text
    assert 'gold: model-checked' in out
    assert 'split: dev (in-sample; pending out-of-sample confirmation)' in out
    assert 'rules_plus_unknown on this dev table is in-sample and pending out-of-sample confirmation' in out
    assert 'out_of_sample: evals_dev/appeals (built on another branch; not scored here)' in out
    assert 'held-out: evals_dev/section_d_heldout' in out
    assert 'held-out gold: model-checked' in out
    assert 'held-out rules_plus_unknown: 7/8 [0.5291, 0.9776]' in out
    assert 'post-fix, no longer blind' in out
    assert 'rules_plus_unknown          8   4/8 [0.2152, 0.7848]' in out
    assert 'rules_plus_unknown_cf       8   4/8 [0.2152, 0.7848]' in out
    plus_misses = out.split('misses rules_plus_unknown:', 1)[1].split('rules_plus_unknown_cf', 1)[0]
    assert 'hold-004' not in plus_misses
    assert 'dev-050' in Path('engine/section_d_flag_eval.py').read_text()
    assert 'winner: rules_plus_unknown' in out
    assert 'under_flag_target: 0' in out
    assert 'note: rules_only abstains with depends; that label is counted in the unknown column' in out
    plus = next(line for line in out.splitlines() if line.startswith('rules_plus_unknown '))
    assert plus.split()[0] == 'rules_plus_unknown'
    assert '50/60 [' in plus
    cf = next(line for line in out.splitlines() if line.startswith('rules_plus_unknown_cf'))
    assert '50/60 [' in cf
    assert re.search(r'\]\s+0\s+27\s+0\s*$', cf)
    assert re.search(r'\]\s+0\s+27\s+0\s*$', plus)
    only = next(line for line in out.splitlines() if line.startswith('rules_only '))
    assert '55/60 [' in only
    assert re.search(r'\]\s+1\s+13\s+0\s*$', only)
    baseline = next(line for line in out.splitlines() if line.startswith('always_unknown'))
    assert '17/60 [' in baseline
    assert re.search(r'\]\s+0\s+60\s+0\s*$', baseline)
    assert 'unknown_rate rules_only: 13/60 [' in out
    assert 'unknown_rate rules_plus_unknown: 27/60 [' in out
    assert 'unknown_rate always_unknown: 60/60 [' in out and ', 1.0]' in out
    assert 'confident_wrong rules_only: 5/60 [' in out
    assert 'confident_wrong rules_plus_unknown: 0/60 [' in out
    assert 'confident_wrong always_unknown: 0/60 [' in out
    assert 'confusion rules_only  rows=gold  columns=system yes unknown no' in out
    assert 'confusion rules_plus_unknown  rows=gold  columns=system yes unknown no' in out
    assert 'confusion always_unknown  rows=gold  columns=system yes unknown no' in out
    assert re.search(r'confusion rules_only.*\n  yes\s+32\s+0\s+1\n  depends\s+0\s+13\s+4\n  no\s+0\s+0\s+10\n', out)
    assert re.search(
        r'confusion rules_plus_unknown.*\n  yes\s+33\s+0\s+0\n  depends\s+0\s+17\s+0\n  no\s+0\s+10\s+0\n', out)
    assert re.search(
        r'confusion always_unknown.*\n  yes\s+0\s+33\s+0\n  depends\s+0\s+17\s+0\n  no\s+0\s+10\s+0\n', out)
    assert 'gold_yes_as_unknown rules_plus_unknown: none' in out
    assert 'gold_yes_as_unknown rules_only: none' in out
    assert 'gold_yes_as_unknown always_unknown: dev-002' in out
    assert 'under_flag rules_only: dev-050:' in out
    assert 'span_m=18' in out
    assert 'under_flag rules_plus_unknown: none' in out
    assert 'under_flag rules_plus_unknown_cf: none' in out
    assert 'under_flag always_unknown: none' in out
    assert 'over_flag rules_only: 0 (gold no, system yes)' in out
    assert 'over_flag rules_plus_unknown: 0 (gold no, system yes)' in out
    assert 'over_flag rules_plus_unknown_cf: 0 (gold no, system yes)' in out
    assert 'over_flag always_unknown: 0 (gold no, system yes)' in out
    assert 'confusion rules_plus_unknown_cf  rows=gold  columns=system yes unknown no' in out
    assert 'unknown_rate rules_plus_unknown_cf: 27/60 [' in out
    assert 'confident_wrong rules_plus_unknown_cf: 0/60 [' in out


def test_heldout_gold_was_written_from_repo_limits():
    folder = Path('evals_dev/section_d_heldout')
    cases = [json.loads(path.read_text()) for path in sorted(folder.glob('hold-*.json'))]
    assert len(cases) == 8
    expected = {
        'hold-001': 'no', 'hold-002': 'yes', 'hold-003': 'no', 'hold-004': 'depends',
        'hold-005': 'yes', 'hold-006': 'yes', 'hold-007': 'no', 'hold-008': 'no',
    }
    for case in cases:
        assert case['gold']['engineering_required'] == expected[case['id']]
        source = case['gold']['limit_source']
        assert 'engine/professional.py' in source or 'PART9_MAX_SPAN_M' in source
        assert '9.23.1.1' not in json.dumps(case)
        assert case['authoring']['gold_written'] == 'before any system run'
        assert case['authoring']['label'] == 'model-checked'


def test_missing_deciding_fact_is_unknown_with_a_question():
    codes, _codedb = load_codes()
    missing_span = json.loads(Path('evals_dev/section_d_heldout/hold-004.json').read_text())
    assert flag_label(missing_span, codes, 'rules_plus_unknown') == 'unknown'
    question = flag_question(missing_span, codes, 'rules_plus_unknown')
    assert question and 'span' in question.casefold()
    assert flag_label(json.loads(Path('evals_dev/section_d_heldout/hold-002.json').read_text()), codes, 'rules_plus_unknown') == 'yes'
    assert flag_label(json.loads(Path('evals_dev/section_d_heldout/hold-005.json').read_text()), codes, 'rules_plus_unknown') == 'yes'
    assert flag_label(json.loads(Path('evals_dev/section_d_heldout/hold-006.json').read_text()), codes, 'rules_plus_unknown') == 'yes'
    issue = section_d_issues(Case(provisions=[BENCHMARK], facts=[fact('occupancy', 'single_family')]), codes_with_rules())[0]
    assert issue.practice_of_engineering.value == 'unknown'
    assert issue.practice_of_engineering.question
    dev = score(codes)
    assert dev['rules_plus_unknown'].scored == 60
    assert dev['rules_plus_unknown'].under_flag == 0


def test_counterfactual_stays_unknown_when_the_missing_span_flips():
    codes, _codedb = load_codes()
    missing_span = json.loads(Path('evals_dev/section_d_heldout/hold-004.json').read_text())
    assert flag_label(missing_span, codes, 'rules_plus_unknown_cf') == 'unknown'
    question = flag_question(missing_span, codes, 'rules_plus_unknown_cf')
    assert question and 'span' in question.casefold()


def test_counterfactual_returns_no_when_the_missing_area_cannot_flip():
    """Area is not a deciding input for single_family once Part 4 design is already false."""
    codes, _codedb = load_codes()
    facts = ProfessionalFacts(occupancy='single_family', storeys=1, part4_design=False)
    label, question = counterfactual(facts, Signals(span_m=10.0), codes)
    assert label == 'no'
    assert question is None


def test_shipped_winner_stays_rules_plus_unknown_when_the_counterfactual_agrees_more():
    totals = {
        'rules_only': VariantScore('rules_only', scored=60, matched=55, under_flag=1),
        'rules_plus_unknown': VariantScore('rules_plus_unknown', scored=60, matched=50, under_flag=0),
        'rules_plus_unknown_cf': VariantScore('rules_plus_unknown_cf', scored=60, matched=60, under_flag=0),
        'always_unknown': VariantScore('always_unknown', scored=60, matched=17, under_flag=0),
    }
    assert winner(totals) == 'rules_plus_unknown'
    assert totals['rules_plus_unknown'].under_flag == 0


def test_default_db_is_the_repo_codedb_build():
    source = Path('engine/codes.py').read_text()
    assert "_REPO = Path(__file__).resolve().parents[1]" in source
    assert "DEFAULT_DB = _REPO / 'codedb' / 'build' / 'codedb.sqlite'" in source
    assert '/Users/aamia' not in source
    assert 'class CodeDbMissing(Exception):' in source
    assert "super().__init__('code database not found')" in source


def test_generic_fallback_question_on_the_dev_set(caplog):
    import logging

    codes, _codedb = load_codes()
    cases = load_cases()
    assert len(cases) == 60
    with caplog.at_level(logging.INFO, logger='engine.section_d_issues'):
        fired = generic_fallback_on_dev(cases, codes)
    assert fired == 0
    assert 'generic fallback practice question fired 0 times on 60 dev cases' in caplog.text


def test_cases_jsonl_scores_only_the_shipped_variant(tmp_path, capsys):
    path = tmp_path / 'cases.jsonl'
    path.write_text(json.dumps({
        'id': 'cli-1',
        'description': 'A two-storey single detached house with a building area of 150 m2, wood frame.',
        'known_facts': ['single detached house'],
        'gold': {'engineering_required': 'no'},
    }) + '\n')
    assert main(['--cases', str(path)]) == 0
    out = capsys.readouterr().out
    assert 'shipped rules_plus_unknown:' in out
    assert 'variant: rules_plus_unknown' in out
    assert 'rules_plus_unknown_cf' not in out
    assert 'Engineer-needed flag' not in out


def test_eval_codedb_argument_marks_a_missing_database_not_final(capsys, tmp_path):
    assert main(['--codedb', str(tmp_path / 'absent.sqlite')]) == 0
    assert 'numbers: not final' in capsys.readouterr().out


def test_generic_fallback_counter_records_an_unusable_question():
    from engine.professional import ProfessionalReason, ProfessionalResult
    from engine.section_d_issues import _question

    result = ProfessionalResult(
        required='depends', general_required='depends',
        reasons=[ProfessionalReason(code='general_unresolved', required='depends', message='Ask.',
                                    citation='rule:C:2.4.1.1.(1)')],
        questions=['This design complies and is safe.'])
    assert _question(result) == GENERIC_FALLBACK_QUESTION
    assert 'generic_fallback_fires' not in Path('engine/section_d_issues.py').read_text()


def _pdf_text(pdf: bytes) -> str:
    import io

    from pypdf import PdfReader
    return ' '.join(' '.join((page.extract_text() or '').split()) for page in PdfReader(io.BytesIO(pdf)).pages)


def test_gc_not_engaged_never_waives_known_mandatory_professional_duties(monkeypatch):
    """Honest engagement answers do not remove mandatory identity/authentication/export gates."""
    from engine.completeness import professional_involvement_gaps
    from engine.export.scc import blockers, load_field_map
    from engine.models import Jurisdiction
    from engine.professional import professional_confirmed, professional_involvement
    from engine.section_c import section_c_rows

    monkeypatch.setattr('engine.completeness.validate_text', lambda *args, **kwargs: {'errors': []})
    codes = codes_with_rules()
    codes.db_path = Path('unused')
    row = section_c_rows([NO_ROW], codes)[0]
    shared = [
        fact('owner_name', 'Case General Contracting'),
        fact('request_date', '2026-10-20'),
        fact('mailing_address', '100 Site Office Road'),
        fact('municipal_address', '100 Site Office Road, Calgary'),
        fact('legal_description', 'Lot 1 Block 2 Plan 3'),
        fact('representative', 'The general contractor'),
        fact('alternative_description', 'A proposed firestop detail at sprinkler piping.'),
        fact('scope', 'site'),
        fact('rationale', 'The applicant wrote why this departure is proposed.'),
        fact('risk_assessment', 'The applicant wrote the risks of this departure.'),
        fact('mitigating_measures', 'The applicant wrote the measures for this departure.'),
        fact('assumptions_and_limits', 'The applicant wrote the assumptions and limits.'),
        fact('maintenance_operation', 'The applicant wrote the operation conditions.'),
        fact('qualifications', 'No registered professional is engaged yet.'),
        fact('occupancy', 'mercantile'),
        fact('storeys', 5),
        fact('part4_design', True),
    ]

    def build(status: str | None) -> Case:
        facts = list(shared)
        if status is not None:
            facts.append(fact('professional_status', status))
        return Case(
            title='GC firestop',
            jurisdiction=Jurisdiction(id='calgary', name='Calgary'),
            provisions=[NO_ROW],
            section_c=[row],
            facts=facts,
        )

    blocked = build(None)
    blocked_reasons = blockers(blocked, load_field_map(), codes)
    assert any('named registered professional' in reason for reason in blocked_reasons)
    assert_export_blocked_on_professional(blocked, codes)

    for status in ('not_engaged', 'No professional engaged yet'):
        case = build(status)
        before = case.model_dump()
        result = professional_involvement(case, codes)
        gaps = professional_involvement_gaps(case, codes, [])
        section_d_issues(case, codes)
        assert case.model_dump() == before
        assert result.professional_status == 'not_engaged'
        assert professional_confirmed(case) is False
        blob = case.model_dump_json().casefold()
        assert 'apega' not in blob and 'aaa-' not in blob
        assert not any(item.field in (
            'professional.registration_number', 'apega_number', 'aaa_number', 'professional.seal',
        ) for item in case.facts)
        assert result.required == 'yes'
        assert {'professional_confirmation', 'responsible_professional',
                'professional_authentication'} <= {gap.field for gap in gaps}
        assert all(gap.severity == 'blocking' and gap.submission_blocking
                   for gap in gaps if gap.id.startswith('D12:'))
        reasons = blockers(case, load_field_map(), codes)
        assert any('professional_confirmation' in reason for reason in reasons)
        assert_export_blocked_on_professional(case, codes)


def assert_export_blocked_on_professional(case, codes):
    from engine.export.scc import ExportBlocked, export_case
    try:
        export_case(case, draft=False, codes=codes)
    except ExportBlocked as blocked:
        assert any('named registered professional' in reason for reason in blocked.reasons)
        return blocked
    raise AssertionError('official export was allowed without a professional')


def test_no_path_confirms_a_professional_without_a_seal_or_number():
    from engine.professional import professional_confirmed
    codes = codes_with_rules()
    file = Source(type='file', ref='note.pdf', quote='A file is not an applicant statement.')
    officer = Source(type='officer', ref='ahj', quote='Officer note.')
    negative = [
        [fact('professional_status', 'not_engaged')],
        [fact('professional_status', 'No professional engaged yet')],
        [fact('professional_status', 'not_engaged'), fact('professional.role', 'engineer')],
        [fact('professional_status', 'not_engaged'), fact('professional_name', 'Ada GC')],
        [fact('professional.role', 'P.Eng.')],
        [fact('professional.role', 'architect'),
         fact('professional.registration_number', 'AAA-1', source=file)],
        [fact('professional.role', 'engineer'),
         fact('professional.seal', 'stamp image on the pdf', source=file)],
        [fact('professional.role', 'sales'), fact('professional.registration_number', 'APEGA-9')],
        [fact('professional_status', 'not_engaged', source=officer)],
        [fact('professional_status', 'not_engaged', source=file)],
        [],
    ]
    for extra in negative:
        case = Case(provisions=[BENCHMARK], facts=[fact('part4_design', True), *extra])
        before = case.model_dump()
        assert professional_confirmed(case) is False
        issue = section_d_issues(case, codes)[0]
        assert issue.status == 'needs_professional'
        assert case.model_dump() == before
        assert professional_involvement_status(case, codes) != 'not_engaged' or any(
            item.field == 'professional_status' and item.source.type == 'user_text' for item in case.facts)
    numbered = Case(provisions=[BENCHMARK], facts=[
        fact('part4_design', True),
        fact('professional.role', 'engineer'),
        fact('professional.registration_number', 'APEGA-1'),
    ])
    sealed = Case(provisions=[BENCHMARK], facts=[
        fact('part4_design', True),
        fact('professional.role', 'architect'),
        fact('professional.seal', 'applicant-confirmed seal'),
    ])
    assert professional_confirmed(numbered) and professional_confirmed(sealed)
    assert section_d_issues(numbered, codes)[0].status != 'needs_professional'
    assert section_d_issues(sealed, codes)[0].status != 'needs_professional'


def professional_involvement_status(case, codes):
    from engine.professional import professional_involvement
    return professional_involvement(case, codes).professional_status


def test_every_screening_question_offers_not_sure():
    """No yes/no question is offered without Not sure, including fire alarm and suppression."""
    from engine.professional import NOT_SURE_OPTION, ProfessionalFacts, professional_involvement
    codes = codes_with_rules()
    codes.add('B', '3.1.9.1.(1)')
    officer = Source(type='officer', ref='ahj', quote='authority answer')
    screens = [
        professional_involvement(Case(provisions=[BENCHMARK]), codes),
        professional_involvement(Case(provisions=[BENCHMARK], facts=[
            fact('occupancy', 'single_family'), fact('storeys', 2), fact('part4_design', True),
        ]), codes),
        professional_involvement(Case(
            title='Firestop at sprinkler-pipe penetrations',
            provisions=['3.1.9.1.(1)'],
            facts=[fact('occupancy', 'mercantile'), fact('storeys', 5)],
        ), codes),
        professional_involvement(ProfessionalFacts(occupancy='mercantile', storeys=5), codes),
        professional_involvement(ProfessionalFacts(), codes),
    ]
    alarm = Case(provisions=[BENCHMARK], facts=[
        fact('occupancy', 'mercantile'),
        fact('fire_suppression', False, source=officer),
    ])
    suppression = Case(provisions=[BENCHMARK], facts=[
        fact('occupancy', 'mercantile'),
        fact('fire_alarm', False, source=officer),
    ])
    screens.append(professional_involvement(alarm, codes))
    screens.append(professional_involvement(suppression, codes))
    for result in screens:
        assert [prompt.text for prompt in result.prompts] == list(dict.fromkeys(result.questions))
        assert result.prompts
        for prompt in result.prompts:
            assert prompt.not_sure == NOT_SURE_OPTION
            assert prompt.help
    alarm_result = screens[-2]
    suppression_result = screens[-1]
    assert any('fire alarm' in prompt.text and prompt.not_sure == NOT_SURE_OPTION for prompt in alarm_result.prompts)
    assert any('2.4.1.4.(1)' in reason.citation for reason in alarm_result.reasons)
    assert any('fire suppression' in prompt.text and prompt.not_sure == NOT_SURE_OPTION
               for prompt in suppression_result.prompts)
    assert any('2.4.1.3.(1)' in reason.citation for reason in suppression_result.reasons)
    issue = section_d_issues(alarm, codes)[0]
    assert issue.practice_of_engineering.prompts
    assert all(prompt.not_sure == NOT_SURE_OPTION for prompt in issue.practice_of_engineering.prompts)
    unsure = Case(provisions=[BENCHMARK], facts=[
        fact('occupancy', 'mercantile'),
        fact('fire_suppression', NOT_SURE_OPTION),
        fact('fire_alarm', NOT_SURE_OPTION),
    ])
    unsure_result = professional_involvement(unsure, codes)
    unsure_issue = section_d_issues(unsure, codes)[0]
    assert {'fire_suppression', 'fire_alarm'} <= set(unsure_result.not_sure_fields)
    assert unsure_issue.practice_of_engineering.value == 'unknown'
    assert unsure_issue.routed_to == 'officer'
    assert any('fire suppression' in prompt.text and 'fire alarm' in prompt.text
               and prompt.not_sure == NOT_SURE_OPTION for prompt in unsure_issue.practice_of_engineering.prompts)


def test_second_printing_citations_resolve_when_codedb_is_present():
    import pytest
    from engine.codes import CodeDbMissing, Codes
    from engine.section_d_issues import citation_resolution

    try:
        codes = Codes()
    except CodeDbMissing:
        pytest.skip('code database not built at codedb/build/codedb.sqlite')
    resolved, total = citation_resolution(load_cases(), codes)
    assert total > 0 and resolved == total


def test_claim_blocklist_matches_compliance_and_safety_claims():
    sample = 'The design complies, is safe, meets the code, and performance is achieved.'
    assert any(re.search(pattern, sample, re.I) for pattern in CLAIM_PHRASES)
    assert re.search(r'\bsafe\b', 'is safe', re.I) and re.search(r'\bcompliance\b', 'compliance', re.I)
