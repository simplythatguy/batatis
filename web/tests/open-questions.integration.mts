/** J12: public applicant actions -> real sync/API -> read-only officer sheet -> structured return. */
import assert from 'node:assert/strict';
import { accounts, auth, review } from '../src/api/accounts.ts';
import { createEngine, EngineError } from '../src/api/client.ts';
import * as sync from '../src/api/sync.ts';
import { emptyCase } from '../src/intake.ts';
import { reducer } from '../src/model.ts';
import { sheetFromEngine } from '../src/calm/reviewer/sheet.ts';
import { caseFromEngine } from '../src/calm/openCase.ts';
import { requestedUncertaintyRow } from '../src/calm/uncertainty.ts';
import { buildDeck } from '../src/calm/deck.ts';
import * as decision from '../src/calm/reviewer/decision.ts';

const base = process.env.SYNC_TEST_BASE;
assert.match(base ?? '', /^http:\/\/(127\.0\.0\.1|localhost):\d+$/);
const originalFetch = globalThis.fetch;
const cookies: Record<string, string> = {};
let actor = 'owner';
const requests: { path: string; method: string; actor: string }[] = [];
globalThis.sessionStorage = { data: new Map(), getItem(k) { return this.data.get(k) ?? null; },
  setItem(k, v) { this.data.set(k, String(v)); }, removeItem(k) { this.data.delete(k); }, clear() { this.data.clear(); } };
globalThis.fetch = async (input, init = {}) => {
  const url = String(input).replace(/^\/api/, base!);
  assert.equal(new URL(url).origin, base, 'No provider or external network is permitted');
  const headers = new Headers(init.headers);
  if (cookies[actor]) headers.set('cookie', cookies[actor]);
  requests.push({ path: new URL(url).pathname, actor, method: init.method ?? 'GET' });
  const response = await originalFetch(url, { ...init, headers });
  const cookie = response.headers.getSetCookie().at(-1);
  if (cookie) cookies[actor] = cookie.split(';')[0];
  return response;
};
const engine = createEngine(base!);
const raw = async (path, data, contentType = 'application/json') => {
  const response = await fetch(base + path, { method: 'POST', headers: { 'Content-Type': contentType },
    body: contentType === 'application/json' ? JSON.stringify(data) : data });
  assert.ok(response.ok, `${response.status}: ${await response.clone().text()}`);
  return response.json();
};

try {
  for (const [name, role, authority] of [['owner', 'applicant', 'edmonton'], ['officer', 'reviewer', 'edmonton'],
    ['foreign', 'reviewer', 'calgary']]) {
    actor = name;
    await auth.signup({ email: `j12-${name}@example.test`, name: `SYNTHETIC ${name}`, password: 'a long test password' });
    await auth.onboarding(role === 'applicant' ? { role, applicant_type: 'contractor' }
      : { role, authority, access_code: authority === 'calgary' ? 'calgary-secret' : 'officer-secret' });
  }
  actor = 'owner';
  let local = reducer(emptyCase('contractor'), { type: 'setDescription',
    text: 'SYNTHETIC proposed exterior insulation alternative, differing from the usual wall assembly.' });
  for (const [field, value, section] of [
    ['owner', 'SYNTHETIC owner', 'A'], ['representative', 'SYNTHETIC applicant', 'A'],
    ['mailingAddress', '123 Synthetic Street', 'A'], ['date', '2026-10-22', 'A'], ['scope', 'site', 'B'],
    ['municipalAddress', '123 Synthetic Street', 'B'], ['legalDescription', 'SYNTHETIC Lot 1 Block 2 Plan 3', 'B'],
    ['alternative', 'SYNTHETIC exterior insulation alternative.', 'B'],
  ]) local = reducer(local, { type: 'setDetail', field, value, section });
  for (const field of ['rationale', 'risk', 'mitigation', 'assumptions', 'maintenance', 'qualifications'])
    local = reducer(local, { type: 'setProcess', field, value: `SYNTHETIC applicant-authored ${field}.` });
  local = reducer(local, { type: 'deferProfessional', field: 'role', choice: 'not_sure', label: 'Who is the registered professional?' });
  // Older description cards remain valid saved inputs. Use their actual answer caller and sync.
  local = { ...local, candidates: [{ id: 'desc-synthetic-wall', topic: 'Wall assembly', provision: 'description', part: 9,
    benchmark: false, quote: { text: 'SYNTHETIC wall assembly', citation: 'Your description', source: 'applicant' },
    departure: 'replace the usual wall assembly', clarifyingQuestion: 'Which layers replace the usual wall assembly?', answer: null }] };
  local = reducer(local, { type: 'answerCandidate', id: 'desc-synthetic-wall', answer: 'not-sure' });
  const id = await sync.ensureEngineCase('SYNTHETIC J12 uncertainty handoff', 'edmonton');
  assert.equal(await sync.pushFacts(id, local.facts), null);
  let saved = await engine.getCase(id);
  let intake = await engine.intake(id, { text: local.description, model: false, expected_version: saved.version });
  const question = intake.record.plan.questions.find(q => q.field === 'storeys');
  assert.ok(question, 'a real planner question is required');
  intake = await engine.intakeAnswers(id, [{ question_id: question.id, answer: 'Not sure' }], intake.case_version);
  assert.ok(intake.record.plan.not_sure.includes(question.id));
  assert.ok(!intake.record.plan.questions.some(q => q.id === question.id), 'planner removed the question after abstention');
  let identified = await engine.identify(id, local.description, [], undefined, undefined, intake.case_version);
  assert.equal(identified.trace.usd, 0);
  assert.ok(identified.articles.length >= 2);
  const article = identified.articles[0].provision;
  const yesArticle = identified.articles[1].provision;
  identified = await engine.decide(id, article, 'not_sure', undefined, identified.case_version);
  identified = await engine.decide(id, yesArticle, 'yes', undefined, identified.case_version);
  const plan = await engine.sectionD(id, { provisions: [yesArticle], expected_version: identified.case_version });
  const file = await raw(`/cases/${id}/files?name=SYNTHETIC.pdf`,
    new TextEncoder().encode('%PDF-1.4\nSYNTHETIC storage-only evidence; no professional opinion.\n'), 'application/pdf');
  for (const [field, value] of Object.entries({ title: 'SYNTHETIC storage-only listing', responsible_party: 'SYNTHETIC applicant', date: '2026-10-22' }))
    await raw(`/cases/${id}/facts`, { field: `evidence.synthetic.${field}`, value, kind: 'pointed', status: 'confirmed', source: { type: 'user_text', ref: 'Applicant listing', quote: value } });
  await raw(`/cases/${id}/facts`, { field: 'evidence.synthetic.file_ref', value: file.id, kind: 'pointed', status: 'confirmed', source: { type: 'file', ref: file.id, quote: 'SYNTHETIC.pdf' } });
  for (const item of plan.items)
    await raw(`/cases/${id}/facts`, { field: `evidence.synthetic.covers.${item.id}`, value: true, kind: 'pointed', status: 'confirmed', source: { type: 'user_click', ref: 'Applicant scope', quote: item.id } });
  await accounts.submit(id, (await engine.getCase(id)).version);
  actor = 'officer';
  const before = await engine.getCase(id);
  const info = await engine.informationRequest(id);
  // This is the same projection the real officer detail sheet uses, without an editable applicant store.
  const sheet = sheetFromEngine(before, info);
  assert.ok(sheet.questions?.some(q => q.field === 'codecheck.desc-synthetic-wall'), 'saved applicant Not sure is absent from officer sheet');
  const unknown = sheet.questions.find(q => q.field === `identify.${article}`);
  assert.equal(unknown?.answer, 'Not sure');
  assert.equal(unknown?.state, 'not_sure');
  assert.equal(unknown?.provision_id, identified.articles.find(a => a.provision === article)?.provision_id ?? article);
  assert.ok(unknown?.text && unknown.source);
  const intakeUnknown = sheet.questions.find(q => q.id === question.id);
  assert.equal(intakeUnknown?.text, question.text, 'the removed planner question retains meaningful wording');
  assert.equal(intakeUnknown?.state, 'not_sure');
  assert.equal(sheet.questions.find(q => q.field === `identify.${yesArticle}`)?.answer, 'Yes');
  assert.ok(sheet.questions.every(q => !q.text.includes('desc-synthetic-wall')));
  assert.deepEqual(await engine.getCase(id), before, 'officer review reads cannot change answers, Section C or versions');
  actor = 'foreign';
  await assert.rejects(engine.informationRequest(id), e => e instanceof EngineError && e.status === 404);
  actor = 'officer';
  await review.claim(id);
  const choices = decision.returnChoices(await engine.gaps(id), sheet.questions);
  const selected = decision.decisionItems(choices, new Set([unknown.id, intakeUnknown.id, 'codecheck.desc-synthetic-wall']));
  assert.equal(selected.length, 3, 'uncertainties absent from gaps are selectable clarification requests');
  await review.decide(id, { outcome: 'return', message: 'Please clarify these saved open questions or record what remains unknown.', items: selected });
  actor = 'owner';
  const returned = await engine.getCase(id);
  assert.deepEqual(returned.decision.items, selected);
  assert.equal(returned.identify.decisions[article].decision, 'not_sure', 'returning a question does not rule on code applicability');
  const thread = await accounts.conversation(id);
  assert.deepEqual(thread.decision.items, selected);
  local = caseFromEngine(returned, 'contractor');
  const request = selected.find(item => item.gap_id === unknown.id);
  assert.ok(request.field.startsWith('clarification.'));
  const response = local.questions.find(q => q.field === request.field);
  assert.ok(response, 'returned clarification has its own exact applicant question card');
  const requested = requestedUncertaintyRow(local, request, true);
  assert.equal(requested.state, 'open');
  const focus = new URLSearchParams(requested.href.split('?')[1]).get('focus');
  assert.ok(buildDeck(local, [], { includeDone: true }).some(card => card.key === focus), 'fix link opens the actual requested card with no canonical gap');
  sync.clearEngineSession();
  sync.adoptEngineCase(returned);
  local = reducer(local, { type: 'answerQuestion', id: response.id, answer: 'Not sure' });
  assert.equal(await sync.pushFacts(id, local.facts), null);
  assert.equal(requestedUncertaintyRow(local, request, true).state, 'open', 'confirmed saved abstention does not answer the request');
  local = reducer(local, { type: 'answerQuestion', id: response.id, answer: 'SYNTHETIC applicant clarification: the west wall uses the proposed assembly.' });
  assert.equal(requestedUncertaintyRow(local, request, false).state, 'unsaved');
  assert.equal(await sync.pushFacts(id, local.facts), null);
  saved = await engine.getCase(id);
  const revised = sheetFromEngine(saved, await engine.informationRequest(id));
  assert.equal(revised.questions.find(q => q.id === unknown.id)?.answer, 'Not sure', 'original manual decision is retained beside the clarification');
  assert.equal(revised.questions.find(q => q.id === unknown.id)?.clarification?.state, 'answered');
  assert.equal(revised.questions.find(q => q.id === question.id)?.state, 'not_sure', 'unanswered clarification remains open');
  assert.equal(requestedUncertaintyRow(caseFromEngine(saved, 'contractor'), request, true).state, 'pending', 'a saved response awaits officer confirmation, never auto resolution');
  assert.deepEqual(saved.decision.items, selected, 'request identity and history survive the saved answer');
  await engine.decide(id, article, 'no', undefined, saved.version);
  const manuallyChanged = sheetFromEngine(await engine.getCase(id), await engine.informationRequest(id));
  assert.equal(manuallyChanged.questions.find(q => q.id === unknown.id)?.answer, 'No', 'only the applicant explicitly changes the manual decision');
  assert.equal(manuallyChanged.questions.find(q => q.id === unknown.id)?.clarification?.state, 'answered', 'question identity and clarification survive an explicit manual decision change');
  assert.ok(requests.filter(r => r.actor === 'officer' && r.path.includes('/identify')).every(r => r.method === 'GET'));
  console.log('PASS J12 saved public applicant Not sure -> sync -> submitted read-only officer sheet -> optional structured return -> saved clarification; no provider I/O');
} finally {
  globalThis.fetch = originalFetch;
  sync.clearEngineSession();
}
