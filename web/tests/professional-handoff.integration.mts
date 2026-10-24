/** J02: actual applicant actions -> production sync -> public API -> claimed officer resolution. */
import assert from 'node:assert/strict';
import { accounts, auth, review, AccountsError } from '../src/api/accounts.ts';
import { createEngine } from '../src/api/client.ts';
import * as sync from '../src/api/sync.ts';
import { emptyCase } from '../src/intake.ts';
import { reducer } from '../src/model.ts';
import { professionalConfirmed } from '../src/professional.ts';

const base = process.env.SYNC_TEST_BASE;
assert.match(base ?? '', /^http:\/\/(127\.0\.0\.1|localhost):\d+$/);
const originalFetch = globalThis.fetch;
const cookies: Record<string, string> = {};
let actor = 'owner';
const requests: { path: string; body: any; actor: string }[] = [];
globalThis.sessionStorage = { data: new Map(), getItem(k) { return this.data.get(k) ?? null; },
  setItem(k, v) { this.data.set(k, String(v)); }, removeItem(k) { this.data.delete(k); }, clear() { this.data.clear(); } };
globalThis.fetch = async (input, init = {}) => {
  const url = typeof input === 'string' && input.startsWith('/api') ? base + input.slice(4) : String(input);
  assert.equal(new URL(url).origin, base, 'No provider or external network is permitted');
  const headers = new Headers(init.headers);
  if (cookies[actor]) headers.set('cookie', cookies[actor]);
  requests.push({ path: new URL(url).pathname, actor, body: typeof init.body === 'string' ? JSON.parse(init.body) : null });
  const response = await originalFetch(url, { ...init, headers });
  const cookie = response.headers.getSetCookie().at(-1);
  if (cookie) cookies[actor] = cookie.split(';')[0];
  return response;
};
const engine = createEngine(base!);
const raw = async (path, data) => {
  const r = await fetch(base + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
  return { status: r.status, body: await r.json() };
};
const denied = async (work, status = 409) => assert.rejects(work, e => e instanceof AccountsError && e.status === status);
const body = (version, required = false) => ({ expected_version: version, required,
  scope: 'SYNTHETIC submitted insulation alternative, including component and professional-law scope',
  basis: 'SYNTHETIC authority determination after scope review. No technical approval is asserted.',
  reference: 'SYNTHETIC authority review record J02' });

async function prepare(choice = 'not_engaged_yet', mandatory = false, attach = true, deferredCredentials = false) {
  actor = 'owner';
  sync.clearEngineSession();
  let local = reducer(emptyCase('contractor'), { type: 'setDescription',
    text: 'SYNTHETIC insulation alternative for this administrative workflow regression.' });
  for (const [field, value, section] of [
    ['owner', 'SYNTHETIC owner', 'A'], ['representative', 'SYNTHETIC applicant', 'A'],
    ['mailingAddress', '123 Synthetic Street', 'A'], ['date', '2026-10-22', 'A'],
    ['scope', 'site', 'B'], ['municipalAddress', '123 Synthetic Street', 'B'],
    ['legalDescription', 'SYNTHETIC Lot 1 Block 2 Plan 3', 'B'],
    ['alternative', 'SYNTHETIC insulation proposal for administrative regression only.', 'B'],
  ]) local = reducer(local, { type: 'setDetail', field, value, section });
  for (const field of ['rationale', 'risk', 'mitigation', 'assumptions', 'maintenance', 'qualifications']) {
    local = reducer(local, { type: 'setProcess', field, value: `SYNTHETIC applicant-authored ${field}. No professional opinion.` });
  }
  // Exactly the action dispatched by the applicant Section D select. No legacy professional_status field.
  local = reducer(local, { type: 'deferProfessional', field: 'role', choice, label: 'Who is the registered professional?' });
  if (mandatory) local = reducer(local, { type: 'answerScope', field: 'part4_design', answer: 'yes' });
  if (deferredCredentials) {
    local = reducer(local, { type: 'setProfessionalFact', field: 'role', value: 'engineer' });
    for (const field of ['registration_number', 'seal']) {
      local = reducer(local, { type: 'deferProfessional', field, choice, label: `SYNTHETIC ${field} answer` });
    }
  }
  const id = await sync.ensureEngineCase('SYNTHETIC J02 public journey', 'edmonton');
  assert.equal(await sync.pushFacts(id, local.facts), null);
  const plan = await engine.sectionD(id, { provisions: ['9.25.2.2.(1)'], expected_version: (await engine.getCase(id)).version });
  assert.ok(plan.items.length);
  // Attachment handling belongs to J03. Bind real, explicitly synthetic bytes through the existing public routes.
  const upload = await fetch(base + `/cases/${id}/files?name=SYNTHETIC.pdf`, {
    method: 'POST', headers: { 'Content-Type': 'application/pdf' }, body: new TextEncoder().encode('%PDF-1.4\nSYNTHETIC storage-only evidence; no test or professional opinion.\n'),
  });
  assert.equal(upload.status, 201);
  const file = await upload.json();
  const fields = { title: 'SYNTHETIC storage-only attachment', responsible_party: 'SYNTHETIC applicant', date: '2026-10-22' };
  for (const [field, value] of Object.entries(fields)) {
    assert.equal((await raw(`/cases/${id}/facts`, { field: `evidence.synthetic.${field}`, value, kind: 'pointed',
      status: 'confirmed', source: { type: 'user_text', ref: 'SYNTHETIC applicant listing', quote: value } })).status, 200);
  }
  if (attach) {
    assert.equal((await raw(`/cases/${id}/facts`, { field: 'evidence.synthetic.file_ref', value: file.id, kind: 'pointed',
      status: 'confirmed', source: { type: 'file', ref: file.id, quote: 'SYNTHETIC storage binding only' } })).status, 200);
  }
  for (const item of plan.items) {
    assert.equal((await raw(`/cases/${id}/facts`, { field: `evidence.synthetic.covers.${item.id}`, value: true,
      kind: 'pointed', status: 'confirmed', source: { type: 'user_click', ref: 'SYNTHETIC applicant scope', quote: item.id } })).status, 200);
  }
  const saved = await engine.getCase(id);
  assert.equal(saved.facts.some(f => f.field === 'professional_status'), false);
  assert.equal(saved.facts.find(f => f.field === 'professional.role')?.value, deferredCredentials ? 'engineer' : choice);
  assert.equal(professionalConfirmed(saved.facts), false);
  assert.equal(saved.facts.some(f => ['officer', 'professional', 'code'].includes(f.source.type)), false);
  return id;
}

try {
  for (const [name, role, authority] of [['owner', 'applicant', 'edmonton'], ['officer', 'reviewer', 'edmonton'],
    ['other', 'reviewer', 'edmonton'], ['foreign', 'reviewer', 'calgary']]) {
    actor = name;
    await auth.signup({ email: `j02-${name}@example.test`, name: `SYNTHETIC ${name}`, password: 'a long test password' });
    await auth.onboarding(role === 'applicant' ? { role, applicant_type: 'contractor' }
      : { role, authority, access_code: authority === 'calgary' ? 'calgary-secret' : 'officer-secret' });
  }

  for (const choice of ['not_engaged_yet', 'not_sure']) {
    const id = await prepare(choice);
    const gaps = await engine.gaps(id);
    const handoff = gaps.find(g => g.field === 'professional_requirement');
    assert.equal(handoff?.severity, 'blocking'); assert.equal(handoff?.routed_to, 'officer');
    assert.equal(handoff?.submission_blocking, false);
    assert.deepEqual(gaps.filter(g => g.severity === 'blocking').map(g => g.field), ['professional_requirement']);
    const pending = await accounts.submit(id, (await engine.getCase(id)).version);
    assert.equal(pending.status, 'submitted');
    actor = 'officer'; await review.claim(id);
    await denied(() => review.decide(id, { outcome: 'accept' }));
    const oldVersion = (await engine.getCase(id)).version;
    const preResolutionFacts = (await engine.getCase(id)).facts;
    await denied(() => review.resolveProfessional(id, body(oldVersion - 1)));
    for (const who of ['owner', 'other', 'foreign']) {
      actor = who;
      await denied(() => review.resolveProfessional(id, body(oldVersion)), who === 'other' ? 409 : 404);
    }
    actor = 'officer';
    await denied(() => review.resolveProfessional(id, { ...body(oldVersion), basis: ' ' }), 422);
    const saved = await review.resolveProfessional(id, body(oldVersion));
    assert.equal(saved.professional_resolutions.length, 1);
    const resolution = saved.professional_resolutions[0];
    assert.equal(resolution.by_name, 'SYNTHETIC officer'); assert.ok(resolution.by_id && resolution.at);
    assert.equal(resolution.required, false); assert.match(resolution.reference, /J02/);
    assert.deepEqual(saved.facts, preResolutionFacts, 'A requirement record must not fabricate facts, credentials or evidence');
    assert.equal((await engine.professional(id)).resolution?.id, resolution.id);
    assert.equal((await engine.gaps(id)).some(g => g.severity === 'blocking'), false);
    // Communication/read receipts do not invalidate the reviewed applicant content.
    await accounts.postMessage(id, 'SYNTHETIC administrative explanation.');
    await accounts.markRead(id);
    assert.equal((await engine.professional(id)).resolution?.id, resolution.id);
    await review.decide(id, { outcome: 'accept' });
    assert.equal((await engine.getCase(id)).status, 'accepted');
    console.log(`PASS J02 ${choice}: public applicant sync -> submitted handoff -> unresolved acceptance gate -> provenance-backed resolution -> administrative acceptance`);
  }

  const requiredId = await prepare();
  await accounts.submit(requiredId, (await engine.getCase(requiredId)).version);
  actor = 'officer'; await review.claim(requiredId);
  await review.resolveProfessional(requiredId, body((await engine.getCase(requiredId)).version, true));
  const mandatoryFields = (await engine.gaps(requiredId)).filter(g => g.severity === 'blocking').map(g => g.field);
  assert.ok(mandatoryFields.includes('professional_confirmation')); assert.ok(mandatoryFields.includes('responsible_professional'));
  assert.ok(mandatoryFields.includes('professional_authentication'));
  await denied(() => review.decide(requiredId, { outcome: 'accept' }));
  console.log('PASS J02 officer requires professional: applicant identity/confirmation/authentication still gate acceptance');

  const mandatoryId = await prepare('not_engaged_yet', true);
  const mandatory = await engine.gaps(mandatoryId);
  assert.ok(mandatory.some(g => g.field === 'professional_confirmation' && g.submission_blocking));
  const mandatoryVersion = (await engine.getCase(mandatoryId)).version;
  await denied(() => accounts.submit(mandatoryId, mandatoryVersion));
  assert.equal((await engine.getCase(mandatoryId)).status, 'draft');
  console.log('PASS J02 applicant Part 4 duty plus Not engaged yet cannot bypass submission');

  const credentialId = await prepare('not_sure', true, true, true);
  const credentialGaps = await engine.gaps(credentialId);
  assert.ok(credentialGaps.some(g => g.field === 'professional_confirmation'));
  assert.ok(credentialGaps.some(g => g.field === 'professional_authentication'));
  const credentialVersion = (await engine.getCase(credentialId)).version;
  await denied(() => accounts.submit(credentialId, credentialVersion));
  console.log('PASS J02 uncertainty answers in registration/seal controls never become credentials or authenticated work');

  const missingId = await prepare('not_engaged_yet', false, false);
  const missing = (await engine.gaps(missingId)).filter(g => g.severity === 'blocking' && g.submission_blocking);
  assert.ok(missing.some(g => g.field.startsWith('evidence.')));
  const missingVersion = (await engine.getCase(missingId)).version;
  await denied(() => accounts.submit(missingId, missingVersion));
  console.log('PASS J02 unresolved handoff never bypasses missing attachment evidence');
  assert.ok(requests.filter(r => r.path.endsWith('/facts')).every(r => !['officer', 'professional', 'code'].includes(r.body.source.type)));
  console.log('Professional handoff integration: 6 passed, 0 failed; no provider I/O');
} finally {
  globalThis.fetch = originalFetch;
}
