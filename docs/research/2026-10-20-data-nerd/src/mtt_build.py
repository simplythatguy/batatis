"""Build research/mandatory-triggers-tests.{json,md} (Karen rubric gap #5). Model-checked, not human-verified.
Every code quote is checked as an exact substring of codedb text (NBC(AE) 2023 2nd printing); SCA quotes against
pdftotext of research/src/leg/S01.pdf (whitespace-normalised). Quotes <= 25 words (pieces split on '…')."""
import json, re, sqlite3, subprocess, os, sys
R = os.path.dirname(os.path.abspath(__file__)) + '/..'
DB = '/workspace/batatis/codedb-snapshot/codedb.sqlite'
c = sqlite3.connect(DB)
ERR = []
NRC = 'https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en'
SCA_URL = 'https://kings-printer.alberta.ca/documents/Acts/S01.pdf'
sca_p31 = re.sub(r'\s+', ' ', subprocess.run(['pdftotext', '-f', '31', '-l', '31', R + '/src/leg/S01.pdf', '-'], capture_output=True, text=True).stdout)
def norm(s): return re.sub(r'\s+', ' ', s).strip()
def chk(q, text, tag):
    ps = [p.strip() for p in q.split('…') if p.strip()]
    if sum(len(p.split()) for p in ps) > 25: ERR.append(f'{tag}: quote > 25 words')
    for p in ps:
        if p not in text: ERR.append(f'{tag}: not exact substring: {p!r}')
def code(div, pid, q):
    r = c.execute('select pdf_page, text from provisions where division=? and id=?', (div, pid)).fetchone()
    if not r: ERR.append(f'missing {div} {pid}'); return {}
    chk(q, norm(r[1]), f'{div} {pid}')
    return {'kind': 'code', 'cite': f'Div {div} Sentence {pid}', 'source': 'NBC(AE) 2023, 2nd printing', 'pdf_page': r[0], 'url': NRC,
            'quote': q, 'verification': f'codedb-checked, 2nd printing, PDF p.{r[0]}'}
def sca(sec, q):
    chk(q, sca_p31, f'SCA {sec}')
    return {'kind': 'statute', 'cite': f'Safety Codes Act {sec}', 'source': 'Safety Codes Act, RSA 2000 c S-1 (King\'s Printer, current as of December 1, 2025)',
            'pdf_page': 31, 'url': SCA_URL, 'quote': q, 'verification': 'source-PDF-checked (pdftotext), page 31 of the Act PDF; not codedb (legislation)'}
P4 = code('C', '2.4.1.2.(1)', 'For design carried out in accordance with Part 4 … the designer shall be a registered professional skilled in the work concerned.')
MUST_NOT = ['state that the design complies, is compliant, or is approved',
            'state as a final ruling that a professional is or is not required (route instead)',
            'close needs_professional without the applicant confirming an engineer/architect role plus a seal or registration number (#26)',
            'close the gap because a document names a person or a seal (#26)',
            'state that a variance or relaxation is granted, will be granted, or is not needed',
            'answer yes or no on the officer\'s behalf']
T = []
def trig(id, name, call, call_basis, basis, fires, near, tests, notes=''):
    T.append(dict(id=id, name=name, mandatory_call=call, call_basis=call_basis, basis=basis, fires_when=fires, near_misses=near, tests=tests, notes=notes))
def test(id, kind, facts, expected, extra_must_not=()):
    return dict(id=id, kind=kind, input_facts=facts, expected=expected, must_not=MUST_NOT + list(extra_must_not),
                label='model-checked, not human-verified')

# HR-02
trig('HR-02', 'Coordinating registered professional, registered professionals of record, Schedules A and B',
     'mandatory (once the project is outside every Div C 2.4.1.1.(1) exception); plus a separate discretionary AHJ power in Div C 2.4.1.1.(4)',
     'Div C 2.4.1.1.(3) and 2.4.2.2.(1) use "shall"; Subsection 2.4.2. applies to every 2.4.1.1.(3) project (Div C 2.4.2.1.(1)). Div C 2.4.1.1.(4) is "may require" (discretionary).',
     [code('C', '2.4.1.1.(3)', 'For buildings other than those described in Sentence (1), the drawings and specifications shall be authenticated by one or more registered professionals'),
      code('C', '2.4.2.1.(1)', 'This Subsection applies to a project that falls within the scope of Sentence 2.4.1.1.(3).'),
      code('C', '2.4.2.2.(1)', 'Before applying for a permit, the owner shall a) retain a coordinating registered professional'),
      code('C', '2.4.2.2.(1)', 'c) provide the authority having jurisdiction with Schedules A and B'),
      code('C', '2.4.1.1.(1)', 'b) classified as a residential occupancy that is i) a single-family dwelling, or ii) a multiple-family dwelling that contains 4 dwelling units or less'),
      code('C', '2.4.1.1.(4)', 'the authority having jurisdiction may require the involvement of one or more registered professionals')],
     ['building outside every exception in Div C 2.4.1.1.(1), e.g. residential multiple-family dwelling with more than 4 dwelling units (secondary suites not counted, Div C 2.4.1.1.(2))'],
     ['single-family dwelling, or multiple-family dwelling with 4 dwelling units or less (exception (1)(b))',
      'a house with a secondary suite: the suite is not counted as a dwelling unit (Div C 2.4.1.1.(2))',
      'inside an exception but the AHJ invokes Div C 2.4.1.1.(4): discretionary, the officer decides'],
     [test('mtt-02a', 'fires', {'occupancy': 'residential, multiple-family dwelling', 'dwelling_units': 64, 'storeys': 5, 'uses': 'retail at grade', 'crp_name': None, 'schedule_a_provided': False, 'schedule_b_provided': False},
           {'route': 'human_review', 'human': 'coordinating registered professional and registered professionals of record (owner retains them)', 'gap': {'type': 'needs_professional', 'status': 'open'},
            'cite': ['Div C 2.4.1.1.(3)', 'Div C 2.4.2.2.(1)'], 'ask': 'Who is the coordinating registered professional, and have Schedules A and B been provided to the authority having jurisdiction?'}),
      test('mtt-02b', 'near_miss', {'occupancy': 'residential, single-family dwelling', 'dwelling_units': 1, 'secondary_suites_count': 1, 'storeys': 2},
           {'trigger_fires': False, 'route': 'none from HR-02; other triggers (HR-03 to HR-07) are still checked', 'note': 'Div C 2.4.1.1.(4): the officer may still require a professional; show this as possible, not as a ruling.'},
           ['say "no professional is needed"'])])
# HR-05
trig('HR-05', 'Part 9 sends sheathing fastening, anchorage or lumber roof sheathing to Part 4 because of wind or seismic hazard',
     'mandatory (when a threshold is met)',
     'The Part 9 Sentences say "shall conform to Part 4" / "shall be designed according to Part 4"; Div C 2.4.1.2.(1) then says the Part 4 designer "shall be a registered professional".',
     [code('B', '9.23.3.5.(4)', 'Fastening of sheathing shall conform to Part 4, a) where the 1-in-50 hourly wind pressure is equal to or greater than 1.2 kPa'),
      code('B', '9.23.6.1.(6)', 'Where … Sa(0.2), is greater than 1.8 or … wind pressure is equal to or greater than 1.2 kPa, anchorage shall be designed according to Part 4.'),
      code('B', '9.23.16.5.(3)', 'Lumber roof sheathing shall be designed according to Part 4, where a) the seismic spectral acceleration, Sa(0.2), is greater than 1.2'),
      P4],
     ['1-in-50 hourly wind pressure >= 1.2 kPa (sheathing fastening, anchorage; lumber roof sheathing at >= 1.20 kPa)', 'Sa(0.2) > 1.8 (anchorage; fastening of required braced wall panels)', 'Sa(0.2) > 1.2 (lumber roof sheathing)'],
     ['wind exactly below 1.2 kPa, e.g. 1.01 kPa (highest 1-in-50 value among the 147 Alberta rows of Div B Appendix C Table C-2, Cowley, page 667 of the PDF)',
      'Sa(0.2) exactly 1.8 (the test is "greater than")',
      'Edmonton: 1-in-50 0.45 kPa (Table C-2, page 667 of the PDF), Sa(0.2) 0.103 (Table C-3, page 672 of the PDF)'],
     [test('mtt-05a', 'fires', {'element': 'sheathing fastening', 'hourly_wind_pressure_1in50_kPa': 1.2, 'Sa_0_2': 0.1, 'climate_source': 'synthetic boundary value (no Table C-2 Alberta row reaches it)'},
           {'route': 'human_review', 'human': 'registered professional (structural) for the Part 4 design', 'gap': {'type': 'needs_professional', 'status': 'open'}, 'cite': ['Div B 9.23.3.5.(4)', 'Div C 2.4.1.2.(1)']}),
      test('mtt-05b', 'near_miss', {'element': 'sheathing fastening and anchorage', 'location': 'Edmonton', 'hourly_wind_pressure_1in50_kPa': 0.45, 'Sa_0_2': 0.103},
           {'trigger_fires': False, 'route': 'none from HR-05; show the threshold and the table value as facts', 'cite': ['Div B 9.23.3.5.(4)']}, ['say "no engineer needed"'])],
     notes='Finding: across the 147 Alberta locations in Table C-2/C-3, the highest 1-in-50 hourly wind pressure is 1.01 kPa (Cowley) and the highest Sa(0.2) is 0.287 (Jasper, page 673 of the PDF). So no listed Alberta location meets an HR-05 threshold; the firing test is a synthetic boundary case. Parsed from the official PDF text by script; model-checked, not human-verified.')
# HR-06
trig('HR-06', 'Part 9 sends footings, floor spans, floors-on-ground or permafrost foundations to Part 4',
     'mandatory (when a condition is met)',
     '"shall be designed in accordance with Section 4.2." / "Subsection 4.1.3." / "Part 4"; Div C 2.4.1.2.(1) then requires a registered professional for design under Part 4 (model-derived chain: Div B Section 4.2. and Div B Subsection 4.1.3. are in Part 4).',
     [code('B', '9.15.3.3.(2)', 'where the span of the supported joists exceeds 4.9 m, footings shall be designed in accordance with Section 4.2.'),
      code('B', '9.15.3.3.(3)', 'Where the specified live load exceeds 2.4 kPa, footings shall be designed in accordance with Section 4.2.'),
      code('B', '9.16.1.2.(1)', 'Floors-on-ground that support loads from the superstructure shall be designed in conformance with Part 4.'),
      code('B', '9.23.4.1.(2)', 'Spans for joists, beams and lintels supporting floors shall be determined according to Subsection 4.1.3. where the supported floors a) serve other than residential areas'),
      code('B', '9.15.1.2.(1)', 'Buildings erected on permafrost shall have foundations designed by a designer competent in this field in accordance with the appropriate requirements of Part 4.'),
      P4],
     ['supported joist span > 4.9 m (footings)', 'specified live load > 2.4 kPa (footings)', 'floor-on-ground carries superstructure loads', 'floors serving other than residential areas (spans)', 'permafrost'],
     ['joist span exactly 4.9 m ("exceeds")', 'live load exactly 2.4 kPa ("exceeds")', 'the exception in Div B 9.15.3.4.(2) referred to by 9.15.3.3.(2) (not assessed here)', 'slab-on-ground that carries no superstructure load'],
     [test('mtt-06a', 'fires', {'supported_joist_span_m': 5.2, 'specified_live_load_kPa': 1.9, 'occupancy': 'residential, single-family dwelling'},
           {'route': 'human_review', 'human': 'registered professional (structural/geotechnical) for the Section 4.2 footing design', 'gap': {'type': 'needs_professional', 'status': 'open'}, 'cite': ['Div B 9.15.3.3.(2)', 'Div C 2.4.1.2.(1)']}),
      test('mtt-06b', 'near_miss', {'supported_joist_span_m': 4.9, 'specified_live_load_kPa': 2.4, 'occupancy': 'residential, single-family dwelling'},
           {'trigger_fires': False, 'route': 'none from HR-06 on these facts'}, ['say "no engineer needed"'])])
# HR-07
trig('HR-07', 'Part 9 sends a material or element to Part 4',
     'mandatory (when the element is present); bowstring/arch trusses medium confidence',
     '"shall be designed to conform to the requirements of Part 4" / "in conformance with Part 4" / "Subsection 4.3.1."; Div C 2.4.1.2.(1). For Div B 9.4.2.2.(3) the text sends only the snow-load requirements of Subsection 4.1.6.; whether that is "design carried out in accordance with Part 4" is a model judgement.',
     [code('B', '9.3.1.1.(3)', 'Except as provided in Sentence (4), reinforced concrete shall be designed to conform to the requirements of Part 4.'),
      code('B', '9.3.1.1.(4)', 'For flat insulating concrete form walls not exceeding 2 storeys in building height and having a maximum floor to floor height of 3 m'),
      code('B', '9.24.1.1.(2)', 'Where loadbearing steel studs are used, they shall be designed in conformance with Part 4.'),
      code('B', '9.17.1.1.(2)', 'Columns for applications other than as described in Sentence (1) shall be designed in accordance with Part 4.'),
      code('B', '9.23.1.1.(2)', 'Where the conditions in Sentence (1) are exceeded for wood constructions, the design of the framing and fastening shall conform to Subsection 4.3.1.'),
      code('B', '9.4.2.2.(3)', 'Bow string, arch or semi-circular roof trusses having an unsupported span greater than 6 m shall be designed in conformance with the snow load requirements'),
      P4],
     ['reinforced concrete outside the flat-ICF permission', 'loadbearing steel studs', 'columns outside Div B 9.17.1.1.(1)', 'wood framing beyond Div B 9.23.1.1.(1) (e.g. a member span over 12.20 m)', 'bowstring/arch/semi-circular truss with unsupported span > 6 m'],
     ['flat ICF walls of 2 storeys or less with floor-to-floor 3 m or less (Div B 9.3.1.1.(4) gives a prescriptive route)', 'truss unsupported span exactly 6 m ("greater than")', 'non-loadbearing steel studs'],
     [test('mtt-07a', 'fires', {'structural_elements': ['loadbearing steel studs'], 'occupancy': 'residential, single-family dwelling', 'storeys': 2},
           {'route': 'human_review', 'human': 'registered professional (structural) for the Part 4 design', 'gap': {'type': 'needs_professional', 'status': 'open'}, 'cite': ['Div B 9.24.1.1.(2)', 'Div C 2.4.1.2.(1)']}),
      test('mtt-07b', 'near_miss', {'structural_elements': ['flat ICF foundation walls'], 'storeys': 2, 'floor_to_floor_m': 3.0, 'truss_type': 'bowstring', 'truss_unsupported_span_m': 6.0},
           {'trigger_fires': False, 'route': 'none from HR-07 on these facts; the Div B 9.3.1.1.(4) prescriptive route is shown with its conditions'}, ['say "no engineer needed"'])])
# HR-30
trig('HR-30', 'Any variance (alternative solution) request goes to a safety codes officer or Administrator',
     'discretionary decision; routing is required (only an Administrator or safety codes officer holds the power)',
     'SCA s.38(1) "may issue" and "is of the opinion": the grant is discretionary. The power is given only to "An Administrator or a safety codes officer", so the app can only route. s.38(3) "shall notify" binds the officer after issuing, not the applicant. This is officer routing, not professional design.',
     [sca('s.38(1)', 'An Administrator or a safety codes officer may issue a written variance'),
      sca('s.38(1)', 'if the Administrator or officer is of the opinion that the variance provides approximately equivalent or greater safety performance'),
      sca('s.38(3)', 'A safety codes officer on issuing a variance shall notify an Administrator.'),
      code('A', '1.2.1.1.(1)', 'b) using alternative solutions that will achieve at least the minimum level of performance required by Division B'),
      code('C', '2.2.1.2.(1)', 'A written request for a variance may be submitted to the Provincial Building Administrator.')],
     ['the applicant asks to depart from an acceptable solution (alternative solution / variance request), site-specific'],
     ['the design follows the acceptable solution as written (no variance requested)', 'a province-wide request: written request to the Provincial Building Administrator (Div C 2.2.1.2.(1)), a different route', 'a Div B Section 3.8. barrier-free relaxation: HR-32 route'],
     [test('mtt-30a', 'fires', {'intake_action': 'variance_request', 'variance_requested': True, 'scope': 'one site', 'jurisdiction': 'Calgary (confirmed)'},
           {'route': 'human_review', 'human': 'safety codes officer of the reviewing authority (or an Administrator)', 'gap': {'type': 'officer_decision', 'status': 'open'}, 'cite': ['Safety Codes Act s.38(1)'],
            'say': 'The officer decides; Batatis prepares the request and cannot say it will be accepted.'}),
      test('mtt-30b', 'near_miss', {'intake_action': 'variance_request', 'variance_requested': True, 'scope': 'province-wide'},
           {'trigger_fires': 'different route', 'route': 'human_review', 'human': 'Provincial Building Administrator (written request)', 'cite': ['Div C 2.2.1.2.(1)']})],
     notes='The HRT json had mandatory=null for HR-30 (not codedb-only). This file classifies it as discretionary (decision) with required routing.')
# HR-32
trig('HR-32', 'Barrier-free (Div B Section 3.8.) relaxation',
     'discretionary (the Administrator "may grant"); routing to the Provincial Barrier-Free Administrator or Provincial Building Administrator',
     'Div C 2.2.1.4.(1) "may grant relaxation" and only "if an owner can demonstrate" one of two grounds. Whether a local safety codes officer may also vary Div B Section 3.8. under SCA s.38 is not settled by this text (UNSOURCED).',
     [code('C', '2.2.1.4.(1)', 'The Provincial Barrier-Free Administrator or Provincial Building Administrator may grant relaxation of one or more of the requirements of Section 3.8. of Division B'),
      code('C', '2.2.1.4.(1)', 'a) the specific requirements are unnecessary, or b) extraordinary circumstances prevent conformance.'),
      code('B', '3.8.1.1.(1)', 'This Section is concerned with the barrier-free design of buildings.')],
     ['the applicant asks to relax a requirement in Div B Section 3.8. (barrier-free design)'],
     ['the departure is from a requirement outside Section 3.8.: HR-30 route (safety codes officer)', 'barrier-free requirement met as written: no relaxation requested'],
     [test('mtt-32a', 'fires', {'provisions_varied': ['Div B Section 3.8. requirement (barrier-free path of travel)'], 'request': 'relaxation', 'owner_grounds': 'extraordinary circumstances (applicant-stated)'},
           {'route': 'human_review', 'human': 'Provincial Barrier-Free Administrator or Provincial Building Administrator', 'gap': {'type': 'administrator_decision', 'status': 'open'}, 'cite': ['Div C 2.2.1.4.(1)'],
            'ask': 'Which ground does the owner rely on (unnecessary, or extraordinary circumstances), and what shows it?'}),
      test('mtt-32b', 'near_miss', {'provisions_varied': ['Div B 3.1.9.1.(1)'], 'request': 'variance'},
           {'trigger_fires': False, 'route': 'HR-30 (safety codes officer)', 'cite': ['Safety Codes Act s.38(1)']})],
     notes='The HRT json typed HR-32 as "mandatory" (routing rule) with mandatory=false; the text supports discretionary.')

if ERR:
    print('\n'.join(ERR)); sys.exit(1)
out = {'generated': '2026-10-20 (America/Edmonton)', 'label': 'model-checked, not human-verified', 'purpose': "Karen rubric gap #5 (Recommendations): mandatory-trigger sourcing and drop-in tests for Backy's #26/#30",
       'codedb': 'NBC(AE) 2023 2nd printing snapshot', 'guardrails': 'no compliance verdicts; no answer-key sources (README, expected/, keys/); route to a named professional or officer',
       'common_must_not': MUST_NOT, 'triggers': T}
json.dump(out, open(R + '/mandatory-triggers-tests.json', 'w'), ensure_ascii=False, indent=2)
# markdown
L = ['# Mandatory human-review triggers: sourcing and drop-in tests', '',
     'Label: **model-checked, not human-verified**. Built 2026-10-20 (America/Edmonton) by `research/src/mtt_build.py`. Machine-readable: `mandatory-triggers-tests.json`.', '',
     "Purpose: Karen's rubric gap #5 (Recommendations). For triggers HR-02, HR-05, HR-06, HR-07, HR-30 and HR-32 of `human-review-triggers.json`: the exact basis, whether the text makes it mandatory, the facts that fire it and the near-misses that don't, and drop-in tests for Backy's #26/#30.", '',
     '**Checks:** every code quote is an exact substring of codedb text (NBC(AE) 2023 2nd printing) with its PDF page. Safety Codes Act quotes are checked against page 31 of the Act PDF. Every quote is 25 words or fewer.', '',
     '**Guardrails in every test:** the expected route is human review by the named professional or officer. No test expects a compliance verdict. No README, expected/ or keys/ content was used.', '',
     '| Trigger | Call | Test ids |', '|---|---|---|']
for t in T: L.append(f"| {t['id']} | {t['mandatory_call']} | {', '.join(x['id'] for x in t['tests'])} |")
L.append('')
for t in T:
    L += [f"## {t['id']}: {t['name']}", '', f"**Call:** {t['mandatory_call']}.", '', f"**Why:** {t['call_basis']}", '', '**Basis:**', '']
    for b in t['basis']:
        pg = f"PDF p.{b['pdf_page']}" if b['kind'] == 'code' else 'page 31 of the Act PDF'
        L.append(f"- {b['cite'].replace(' Sentence ', ' ')}, {pg}: \"{b['quote']}\"")
    L += ['', '**Fires when:**', ''] + [f'- {x}' for x in t['fires_when']] + ['', '**Near-misses (does not fire):**', ''] + [f'- {x}' for x in t['near_misses']] + ['']
    if t['notes']: L += [f"**Note:** {t['notes']}", '']
    L += ['**Tests:**', '']
    for x in t['tests']:
        L.append(f"- `{x['id']}` ({x['kind']}). Input: `{json.dumps(x['input_facts'], ensure_ascii=False)}`. Expected: `{json.dumps(x['expected'], ensure_ascii=False)}`.")
    L.append('')
L += ['## must_not (every test)', ''] + [f'- {m}' for m in MUST_NOT] + ['', 'Near-miss tests also add: never say "no professional/engineer needed" as a ruling.', '']
open(R + '/mandatory-triggers-tests.md', 'w').write('\n'.join(L))
print('OK', len(T), 'triggers', sum(len(t['tests']) for t in T), 'tests')
