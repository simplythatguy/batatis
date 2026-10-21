// R7 versioned reference contract against the real engine and a disposable SQLite store.
// Envelopes, acknowledged versions, explicit clear, real stale 409, deleted/expired 404,
// retained unscoped documents and the jurisdiction PUT body. No provider route is called.
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { createEngine, EngineError, isCaseGone } from '../src/api/client.ts';
import * as sync from '../src/api/sync.ts';
import { readSectionD } from '../src/api/sectionD.ts';
import { reducer } from '../src/model.ts';
import { canonicalRows } from '../src/api/sectionC.ts';
import { confirmedProvisions, reconcileSectionC } from '../src/provisions.ts';
import { emptyCase } from '../src/intake.ts';

const base = process.env.SYNC_TEST_BASE;
assert.match(base ?? '', /^http:\/\/(127\.0\.0\.1|localhost):\d+/);
const db = process.env.SYNC_TEST_DB;
globalThis.sessionStorage = { data: new Map(), getItem(k) { return this.data.get(k) ?? null; }, setItem(k, v) { this.data.set(k, String(v)); }, removeItem(k) { this.data.delete(k); }, clear() { this.data.clear(); } } as unknown as Storage;
const realFetch = globalThis.fetch;
const requests: { path: string; method: string; body: unknown; status: number }[] = [];
globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = String(input).replace(/^\/api/, base!);
  assert.equal(new URL(url).origin, base, 'only the disposable engine is reachable');
  const response = await realFetch(url, init);
  requests.push({ path: new URL(url).pathname, method: init?.method ?? 'GET', body: typeof init?.body === 'string' ? JSON.parse(init.body) : null, status: response.status });
  return response;
}) as typeof fetch;
const plain = createEngine(base!);
const raw = async (method: string, path: string, body?: unknown) => {
  const res = await realFetch(base + path, { method, headers: body === undefined ? undefined : { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) });
  return { status: res.status, body: res.status === 204 ? null : await res.json() };
};
const candidate = (provision: string, answer: string | null = null) => ({ id: `r7-${provision}`, provision, answer, identified: true, suggestion: 'search', part: 3, benchmark: answer === 'yes', topic: 'Firestops', quote: { text: '', citation: 'CodeDB' }, departure: 'depart from this sentence', clarifyingQuestion: 'Which part changes?' });
const results: { name: string; status: string; error?: string }[] = [];
async function check(name: string, work: () => Promise<void>) {
  try { await work(); results.push({ name, status: 'PASS' }); }
  catch (e) { results.push({ name, status: 'FAIL', error: e instanceof Error ? e.stack ?? e.message : String(e) }); }
}
const foreignFact = (value: string) => ({ field: 'process.maintenance_operation', value, kind: 'pointed', status: 'confirmed', source: { type: 'user_text', ref: 'SYNTHETIC second writer', quote: value } });
async function caseWithSentence(title: string) {
  sync.clearEngineSession();
  const id = await sync.ensureEngineCase(title, 'edmonton');
  let c = reducer(emptyCase('contractor'), { type: 'setDescription', text: 'SYNTHETIC firestop review.' });
  c = reducer(c, { type: 'addCandidate', candidate: candidate('3.1.9.1.(1)', 'yes') });
  c = reconcileSectionC(c, canonicalRows(await plain.sectionC(['3.1.9.1.(1)']), c.candidates.map(a => ({ candidateId: a.id, provision: a.provision }))));
  assert.deepEqual(confirmedProvisions(c), ['3.1.9.1.(1)']);
  assert.equal(await sync.pushFacts(id, c.facts), null);
  return { id, c };
}

await check('every list route is unwrapped from { items, meta } into a plain array', async () => {
  const id = await sync.ensureEngineCase('SYNTHETIC R7 envelope case', 'edmonton');
  for (const rows of [await plain.search('firestop', { limit: 3 }), await plain.sectionC(['3.1.9.1.(1)']), await plain.gaps(id), await plain.processFields(id), await plain.sectionDIssues(id)]) {
    assert.ok(Array.isArray(rows));
    assert.equal(Object.prototype.hasOwnProperty.call(rows, 'meta'), false);
  }
  const head = await realFetch(base + '/cases/' + id);
  assert.match(head.headers.get('x-batatis-notice') ?? '', /7 days/);
});

await check('create, fact writes and evidence delete advance the acknowledged version one step each', async () => {
  sync.clearEngineSession();
  const id = await sync.ensureEngineCase('SYNTHETIC R7 version case', 'edmonton');
  assert.equal(sync.acknowledgedVersion(id), (await plain.getCase(id)).version);
  let c = reducer(emptyCase('contractor'), { type: 'setProcess', field: 'risk', value: 'SYNTHETIC risk' });
  const before = sync.acknowledgedVersion(id)!;
  assert.equal(await sync.pushFacts(id, c.facts), null);
  const afterFacts = (await plain.getCase(id)).version;
  assert.equal(afterFacts, before + c.facts.length);
  assert.equal(sync.acknowledgedVersion(id), afterFacts);
  c = reducer(c, { type: 'saveEvidence', itemId: 'slot-r7', document: 'SYNTHETIC listed report', responsible: 'SYNTHETIC author', date: '', evidenceType: 'evaluation', provisionId: '' });
  assert.equal(await sync.pushFacts(id, c.facts), null);
  assert.equal(await sync.pushListedEvidence(id, c.listedEvidence ?? []), null, 'acknowledged by its fact writes');
  c = reducer(c, { type: 'removeEvidence', id: 'slot-r7' });
  const beforeDelete = sync.acknowledgedVersion(id);
  requests.length = 0;
  const deleted = await sync.pushDeletedEvidence(id, c.deletedEvidence ?? []);
  assert.deepEqual(deleted, { acked: ['slot-r7'], error: null });
  assert.deepEqual(requests.find(r => r.method === 'DELETE')!.body, { expected_version: beforeDelete }, 'DELETE carries the acknowledged version');
  assert.equal(sync.acknowledgedVersion(id), (await plain.getCase(id)).version);
  assert.equal(sync.needsReconcile(id), false);
});

await check('explicit selection sends the acknowledged expected_version and acknowledges case_version', async () => {
  const { id, c } = await caseWithSentence('SYNTHETIC R7 selection');
  requests.length = 0;
  const known = sync.acknowledgedVersion(id);
  const read = await readSectionD(id, c, () => true);
  assert.ok(read && read.plan.items.length > 0);
  const post = requests.find(r => r.path.endsWith('/section-d') && r.method === 'POST')!;
  assert.deepEqual(post.body, { provisions: ['3.1.9.1.(1)'], expected_version: known });
  assert.equal(read.plan.case_version, known! + 1);
  assert.equal(sync.acknowledgedVersion(id), read.plan.case_version);
  assert.equal((await plain.getCase(id)).version, read.plan.case_version);
});

await check('final withdrawal persists [] with empty C/D, keeps the listed document unscoped and does not relink it on reselect', async () => {
  const { id, c } = await caseWithSentence('SYNTHETIC R7 clear');
  const first = await readSectionD(id, c, () => true);
  const task = first!.plan.items[0].id;
  let draft = reducer(c, { type: 'saveEvidence', itemId: task, document: 'SYNTHETIC firestop listing', responsible: 'SYNTHETIC designer', date: '2026-10-01', evidenceType: 'evaluation', provisionId: '3.1.9.1.(1)' });
  assert.equal(await sync.pushFacts(id, draft.facts), null);
  draft = reducer(draft, { type: 'answerCandidate', id: 'r7-3.1.9.1.(1)', answer: null });
  requests.length = 0;
  const known = sync.acknowledgedVersion(id);
  const cleared = await readSectionD(id, draft, () => true);
  const post = requests.find(r => r.path.endsWith('/section-d') && r.method === 'POST')!;
  assert.deepEqual(post.body, { provisions: [], expected_version: known });
  assert.deepEqual(cleared!.plan.items, []);
  assert.deepEqual(cleared!.issues!.map(i => [i.id, i.provision]), [['benchmark-unconfirmed', null]], 'only the engine\'s no-benchmark state remains');
  assert.ok(cleared!.plan.notices.some(n => /Confirm the benchmark/.test(n)));
  const stored = await plain.getCase(id);
  assert.deepEqual([stored.provisions, stored.section_c, stored.gaps], [[], [], []]);
  assert.equal(stored.version, cleared!.plan.case_version);
  assert.ok(stored.facts.some(f => f.field === `evidence.${task}.title` && f.value === 'SYNTHETIC firestop listing'));
  assert.ok(stored.facts.some(f => f.field === `evidence.${task}.date`));
  assert.ok(stored.facts.some(f => f.field === `evidence.${task}.auto_link` && f.value === false));
  draft = reducer(draft, { type: 'answerCandidate', id: 'r7-3.1.9.1.(1)', answer: 'yes' });
  const reselected = await readSectionD(id, draft, () => true);
  assert.ok(reselected!.plan.items.some(item => item.id === task), 'stable plan id returns');
  assert.ok(reselected!.plan.items.every(item => item.status === 'needed' && item.attachments.length === 0));
  const after = await plain.getCase(id);
  assert.ok(after.facts.some(f => f.field === `evidence.${task}.auto_link` && f.value === false), 'reselect does not silently restore scope');
  assert.ok(after.evidence.every(item => item.kind === 'text'), 'typed listing never becomes an attachment');
});

await check('a second writer makes the next explicit plan a real 409; local draft survives; explicit reconcile then succeeds', async () => {
  const { id, c } = await caseWithSentence('SYNTHETIC R7 conflict');
  const other = await raw('POST', `/cases/${id}/facts`, foreignFact('SYNTHETIC second writer answer'));
  assert.equal(other.status, 200);
  const draft = reducer(c, { type: 'setProcess', field: 'risk', value: 'SYNTHETIC local draft after the other write' });
  assert.equal(await sync.pushFacts(id, draft.facts), null);
  assert.ok(sync.acknowledgedVersion(id)! < (await plain.getCase(id)).version, 'a foreign revision is not silently acknowledged');
  requests.length = 0;
  await assert.rejects(readSectionD(id, draft, () => true), (e: unknown) => e instanceof EngineError && e.status === 409);
  assert.equal(requests.filter(r => r.path.endsWith('/section-d') && r.method === 'POST').length, 1, 'no automatic retry');
  assert.equal(sync.needsReconcile(id), true);
  assert.equal(draft.process.risk, 'SYNTHETIC local draft after the other write');
  const reconciled = await sync.reconcileEngineCase(id);
  assert.equal(sync.acknowledgedVersion(id), reconciled.version);
  assert.equal(sync.needsReconcile(id), false);
  assert.equal(await sync.pushFacts(id, draft.facts), null);
  const read = await readSectionD(id, draft, () => true);
  assert.ok(read && read.plan.items.length > 0);
  const stored = await plain.getCase(id);
  assert.ok(stored.facts.some(f => f.value === 'SYNTHETIC second writer answer'), 'the other writer is preserved');
  assert.ok(stored.facts.some(f => f.value === 'SYNTHETIC local draft after the other write'));
});

await check('the engine rejects null provisions and an unversioned explicit list; the client never sends either', async () => {
  const { id } = await caseWithSentence('SYNTHETIC R7 wire');
  assert.equal((await raw('POST', `/cases/${id}/section-d`, { provisions: null, expected_version: sync.acknowledgedVersion(id) })).status, 422);
  assert.equal((await raw('POST', `/cases/${id}/section-d`, { provisions: [] })).status, 422);
  assert.equal((await raw('POST', `/cases/${id}/section-d`, { provisions: [], expected_version: 0 })).status, 422);
  assert.ok(requests.filter(r => r.path.endsWith('/section-d') && r.method === 'POST').every(r => {
    const body = r.body as { provisions?: unknown; expected_version?: unknown };
    return body.provisions !== null && (body.provisions === undefined || (Number.isInteger(body.expected_version) && (body.expected_version as number) > 0));
  }));
});

async function terminal(id: string, c: ReturnType<typeof emptyCase>) {
  requests.length = 0;
  let draft = reducer(c, { type: 'setProcess', field: 'risk', value: 'SYNTHETIC answer kept after removal' });
  draft = reducer(draft, { type: 'saveEvidence', itemId: 'gone-slot', document: 'SYNTHETIC listing after removal', responsible: 'SYNTHETIC author', date: '', evidenceType: 'evaluation', provisionId: '' });
  const error = await sync.pushFacts(id, draft.facts);
  assert.match(error ?? '', /case not found/);
  assert.notEqual(await sync.pushListedEvidence(id, draft.listedEvidence ?? []), null, 'an unsaved listing is never reported as saved');
  assert.equal(requests.some(r => r.path.endsWith('/evidence') && r.method === 'POST'), false, 'no request to a route this engine does not serve');
  assert.equal(draft.listedEvidence?.[0]?.description, 'SYNTHETIC listing after removal');
  await assert.rejects(readSectionD(id, draft, () => true), (e: unknown) => isCaseGone(e));
  assert.equal(await sync.ensureEngineCase('SYNTHETIC must not recreate', 'edmonton'), id);
  assert.equal(requests.some(r => r.path === '/cases' && r.method === 'POST'), false, 'never creates a replacement case');
  await assert.rejects(sync.reconcileEngineCase(id), (e: unknown) => isCaseGone(e));
  assert.equal((await raw('GET', `/cases/${id}`)).status, 404, 'remains absent');
  assert.equal(draft.process.risk, 'SYNTHETIC answer kept after removal');
}

await check('a deleted case is terminal: 404 everywhere, no resurrection or new case, local answers retained', async () => {
  const { id, c } = await caseWithSentence('SYNTHETIC R7 deleted');
  assert.equal((await raw('DELETE', `/cases/${id}`)).status, 204);
  await terminal(id, c);
});

await check('an expired case (created over 7 days ago) is terminal in the same way', async () => {
  assert.ok(db, 'SYNC_TEST_DB names the disposable store');
  const { id, c } = await caseWithSentence('SYNTHETIC R7 expired');
  const store = new DatabaseSync(db!);
  store.prepare("UPDATE cases SET json=json_set(json,'$.created_at','2020-01-01T00:00:00+00:00') WHERE id=?").run(id);
  store.close();
  await terminal(id, c);
});

await check('jurisdiction: unchanged authority sends nothing; a change sends exactly { jurisdiction, expected_version }; only a real acknowledgement counts', async () => {
  sync.clearEngineSession();
  const id = await sync.ensureEngineCase('SYNTHETIC R7 jurisdiction', 'edmonton');
  requests.length = 0;
  assert.equal(await sync.syncJurisdiction(id, 'edmonton', ''), id);
  assert.equal(requests.length, 0);
  const known = sync.acknowledgedVersion(id)!;
  const outcome = await sync.syncJurisdiction(id, 'calgary', '').then(() => 'saved', (e: unknown) => e);
  const put = requests.find(r => r.method === 'PUT')!;
  assert.equal(put.path, `/cases/${id}/jurisdiction`);
  assert.deepEqual(Object.keys(put.body as object).sort(), ['expected_version', 'jurisdiction']);
  const sent = put.body as { jurisdiction: { id: string; name: string; authority: null }; expected_version: number };
  assert.deepEqual(sent.jurisdiction, { id: 'calgary', name: sent.jurisdiction.name, authority: null });
  assert.equal(sent.expected_version, known);
  if (put.status === 200) {
    // Real route (root common 56de73b and later).
    assert.equal(outcome, 'saved');
    const stored = await plain.getCase(id);
    assert.equal(stored.jurisdiction?.id, 'calgary');
    assert.equal(sync.acknowledgedVersion(id), known + 1);
    assert.equal(stored.version, known + 1);
    requests.length = 0;
    assert.equal(await sync.syncJurisdiction(id, '', ''), id);
    assert.deepEqual(requests.find(r => r.method === 'PUT')!.body, { jurisdiction: null, expected_version: known + 1 });
    assert.equal((await plain.getCase(id)).jurisdiction, null);
    // A second writer, then this visit's next authority change: the engine rejects the stale version.
    assert.equal((await raw('POST', `/cases/${id}/facts`, foreignFact('SYNTHETIC jurisdiction second writer'))).status, 200);
    const draft = reducer(emptyCase('contractor'), { type: 'setProcess', field: 'risk', value: 'SYNTHETIC kept' });
    assert.equal(await sync.pushFacts(id, draft.facts), null);
    requests.length = 0;
    await assert.rejects(sync.syncJurisdiction(id, 'edmonton', ''), (e: unknown) => e instanceof EngineError && e.status === 409);
    assert.equal(requests.filter(r => r.method === 'PUT').length, 1);
    assert.equal(requests.find(r => r.method === 'PUT')!.status, 409, 'the engine reported the conflict');
    assert.equal(sync.needsReconcile(id), true);
    assert.equal((await plain.getCase(id)).jurisdiction, null, 'nothing overwritten');
    await sync.reconcileEngineCase(id);
    assert.equal(await sync.syncJurisdiction(id, 'edmonton', ''), id);
    assert.equal((await plain.getCase(id)).jurisdiction?.id, 'edmonton');
  } else {
    // Route absent on this engine: never reported as saved.
    assert.ok([404, 405].includes(put.status));
    assert.match(String(outcome), /could not be saved/);
    assert.equal((await plain.getCase(id)).jurisdiction?.id, 'edmonton', 'stored value unchanged; no false acknowledgement');
    requests.length = 0;
    await assert.rejects(sync.syncJurisdiction(id, '', ''), /could not be saved/);
    assert.deepEqual(requests.find(r => r.method === 'PUT')!.body, { jurisdiction: null, expected_version: known });
  }
  console.log('jurisdiction route status', put.status);
});

// Contract stub for the root-owned PUT route (not on this base). Labelled stub, not engine evidence.
await check('STUB jurisdiction route: 200 acknowledges its version; 409 needs explicit reconcile; 404 case not found is terminal', async () => {
  sync.clearEngineSession();
  const id = await sync.ensureEngineCase('SYNTHETIC R7 jurisdiction stub', 'edmonton');
  const known = sync.acknowledgedVersion(id)!;
  const live = globalThis.fetch;
  const seen: string[] = [];
  let reply: () => Response = () => new Response('{}');
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    seen.push(`${init?.method ?? 'GET'} ${new URL(String(input).replace(/^\/api/, base!)).pathname}`);
    return init?.method === 'PUT' ? reply() : live(input, init);
  }) as typeof fetch;
  try {
    const saved = await plain.getCase(id);
    reply = () => new Response(JSON.stringify({ ...saved, jurisdiction: { id: 'calgary', name: 'Calgary', authority: null }, version: known + 1, meta: {} }), { status: 200, headers: { 'content-type': 'application/json' } });
    assert.equal(await sync.syncJurisdiction(id, 'calgary', ''), id);
    assert.equal(sync.acknowledgedVersion(id), known + 1);
    seen.length = 0;
    assert.equal(await sync.syncJurisdiction(id, 'calgary', ''), id);
    assert.deepEqual(seen, []);
    reply = () => new Response(JSON.stringify({ detail: 'case was updated concurrently', meta: {} }), { status: 409, headers: { 'content-type': 'application/json' } });
    await assert.rejects(sync.syncJurisdiction(id, 'edmonton', ''), (e: unknown) => e instanceof EngineError && e.status === 409);
    assert.equal(sync.needsReconcile(id), true);
    seen.length = 0;
    await assert.rejects(sync.syncJurisdiction(id, 'edmonton', ''), (e: unknown) => e instanceof EngineError && e.status === 409);
    assert.deepEqual(seen, [], 'no automatic retry while a reconcile is pending');
    sync.clearEngineSession();
    const second = await sync.ensureEngineCase('SYNTHETIC R7 jurisdiction stub gone', 'edmonton');
    reply = () => new Response(JSON.stringify({ detail: 'case not found', meta: {} }), { status: 404, headers: { 'content-type': 'application/json' } });
    seen.length = 0;
    await assert.rejects(sync.syncJurisdiction(second, 'calgary', ''), (e: unknown) => isCaseGone(e));
    assert.deepEqual(seen, [`PUT /cases/${second}/jurisdiction`], 'no fallback read or new case after case not found');
  } finally {
    globalThis.fetch = live;
  }
});

console.log(JSON.stringify({ results }, null, 1));
const failed = results.filter(r => r.status !== 'PASS');
console.log(`R7 contract real API: ${results.length - failed.length} passed, ${failed.length} failed`);
process.exit(failed.length ? 1 : 0);
