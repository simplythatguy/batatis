// R8 atomic evidence contract against the real engine (POST /cases/{id}/evidence and versioned
// DELETE) with a disposable SQLite store. Each listing is one acknowledged write with its real ID,
// version, separate metadata and explicit scope. Test data is labelled SYNTHETIC.
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { createEngine, isCaseGone } from '../src/api/client.ts';
import * as sync from '../src/api/sync.ts';
import { readSectionD } from '../src/api/sectionD.ts';
import { evidenceDocuments, keptDocuments, reducer } from '../src/model.ts';
import { canonicalRows } from '../src/api/sectionC.ts';
import { reconcileSectionC } from '../src/provisions.ts';
import { emptyCase } from '../src/intake.ts';
import type { Case } from '../src/types.ts';

const base = process.env.SYNC_TEST_BASE;
assert.match(base ?? '', /^http:\/\/(127\.0\.0\.1|localhost):\d+/);
const db = process.env.SYNC_TEST_DB;
globalThis.sessionStorage = { data: new Map(), getItem(k) { return this.data.get(k) ?? null; }, setItem(k, v) { this.data.set(k, String(v)); }, removeItem(k) { this.data.delete(k); }, clear() { this.data.clear(); } } as unknown as Storage;
const realFetch = globalThis.fetch;
type Seen = { path: string; method: string; body: any; status: number };
const requests: Seen[] = [];
/** When set, the next matching request reaches the engine but its answer is lost on the way back. */
let loseNext: { method: string; suffix: string } | null = null;
globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = String(input).replace(/^\/api/, base!);
  assert.equal(new URL(url).origin, base, 'only the disposable engine is reachable');
  const response = await realFetch(url, init);
  const path = new URL(url).pathname;
  const method = init?.method ?? 'GET';
  requests.push({ path, method, body: typeof init?.body === 'string' ? JSON.parse(init.body) : null, status: response.status });
  if (loseNext && loseNext.method === method && path.endsWith(loseNext.suffix)) {
    loseNext = null;
    throw new TypeError('SYNTHETIC lost acknowledgement');
  }
  return response;
}) as typeof fetch;
const plain = createEngine(base!);
const raw = async (method: string, path: string, body?: unknown) => {
  const res = await realFetch(base + path, { method, headers: body === undefined ? undefined : { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) });
  return { status: res.status, body: res.status === 204 ? null : await res.json() };
};
const results: { name: string; status: string; error?: string }[] = [];
async function check(name: string, work: () => Promise<void>) {
  try { await work(); results.push({ name, status: 'PASS' }); }
  catch (e) { results.push({ name, status: 'FAIL', error: e instanceof Error ? e.stack ?? e.message : String(e) }); }
}
const candidate = (provision: string, answer: string | null = 'yes') => ({ id: `r8-${provision}`, provision, answer, identified: true, suggestion: 'search', part: 3, benchmark: answer === 'yes', topic: 'Firestops', quote: { text: '', citation: 'CodeDB' }, departure: 'depart from this sentence', clarifyingQuestion: 'Which part changes?' });
const foreignFact = (value: string) => ({ field: 'process.maintenance_operation', value, kind: 'pointed', status: 'confirmed', source: { type: 'user_text', ref: 'SYNTHETIC second writer', quote: value } });
const evidencePosts = () => requests.filter(r => r.method === 'POST' && /\/evidence$/.test(r.path));
const latest = (saved: { facts: { field: string; value: unknown }[] }, field: string) => [...saved.facts].reverse().find(f => f.field === field);

/** A saved case with one confirmed sentence and its acknowledged Section D plan. */
async function planned(title: string) {
  sync.clearEngineSession();
  const id = await sync.ensureEngineCase(title, 'edmonton');
  let c = reducer(emptyCase('contractor'), { type: 'setDescription', text: 'SYNTHETIC firestop review.' });
  c = reducer(c, { type: 'addCandidate', candidate: candidate('3.1.9.1.(1)') });
  c = reconcileSectionC(c, canonicalRows(await plain.sectionC(['3.1.9.1.(1)']), c.candidates.map(a => ({ candidateId: a.id, provision: a.provision }))));
  assert.equal(await sync.pushFacts(id, c.facts), null);
  const read = await readSectionD(id, c, () => true);
  assert.ok(read && read.plan.items.length > 1, 'a real plan with several tasks');
  return { id, c, tasks: read.plan.items.map(item => item.id) };
}

const add = (c: Case, itemId: string, document: string, extra: Partial<{ responsible: string; date: string; evidenceType: string; slot: string }> = {}) =>
  reducer(c, { type: 'saveEvidence', itemId, document, responsible: extra.responsible ?? '', date: extra.date ?? '', evidenceType: extra.evidenceType ?? 'evaluation', provisionId: '3.1.9.1.(1)', ...(extra.slot ? { slot: extra.slot } : {}) });

/** What the provider does after a save: listings first, then removals, each acknowledged by the engine. */
async function flush(id: string, c: Case) {
  const listed = await sync.pushListedEvidence(id, c.listedEvidence ?? []);
  c = reducer(c, { type: 'ackEvidence', ...listed });
  if (listed.error) return { c, error: listed.error };
  const removed = await sync.pushDeletedEvidence(id, c.deletedEvidence ?? []);
  c = reducer(c, { type: 'ackEvidence', ...removed });
  return { c, error: removed.error };
}

await check('create sends one atomic POST with the real ID, version, separate metadata and explicit task scope', async () => {
  const { id, c: start, tasks } = await planned('SYNTHETIC R8 create');
  const task = tasks[0];
  let c = add(start, task, 'SYNTHETIC firestop listing', { responsible: 'SYNTHETIC designer', date: 'Rev B' });
  assert.equal(c.facts.some(f => f.field.startsWith('evidence.')), false, 'nothing counts as saved before the engine answers');
  assert.equal(await sync.pushFacts(id, c.facts), null);
  assert.equal(requests.some(r => r.path.endsWith('/facts') && String(r.body?.field).startsWith('evidence.')), false, 'listings never go through the fact route');
  const known = sync.acknowledgedVersion(id)!;
  requests.length = 0;
  const out = await flush(id, c);
  c = out.c;
  assert.equal(out.error, null);
  const posts = evidencePosts();
  assert.equal(posts.length, 1);
  assert.deepEqual(posts[0].body, {
    operation: 'create', evidence_id: task, expected_version: known,
    title: 'SYNTHETIC firestop listing', description: 'SYNTHETIC firestop listing', evidence_type: 'evaluation',
    responsible_party: 'SYNTHETIC designer', date: 'Rev B', scope: { item_id: task },
  });
  assert.equal(posts[0].status, 200);
  assert.equal(sync.acknowledgedVersion(id), known + 1);
  assert.deepEqual(c.listedEvidence ?? [], [], 'acknowledged, so no longer staged');
  const stored = await plain.getCase(id);
  assert.equal(stored.version, known + 1);
  const item = stored.evidence.find(e => e.id === task)!;
  assert.equal(item.kind, 'text');
  assert.equal(item.status, 'evidence_listed');
  for (const [field, value] of [['title', 'SYNTHETIC firestop listing'], ['responsible_party', 'SYNTHETIC designer'], ['date', 'Rev B'], ['evidence_type', 'evaluation'], ['item_id', task]] as const)
    assert.equal(latest(stored, `evidence.${task}.${field}`)?.value, value, field);
  assert.equal(stored.facts.some(f => f.field.endsWith('.file_ref')), false, 'a listing never claims a file');
  // The browser mirrors exactly what the engine stored.
  assert.deepEqual(c.facts.filter(f => f.field.startsWith('evidence.')).map(f => f.field), stored.facts.filter(f => f.field.startsWith('evidence.')).map(f => f.field));
  assert.deepEqual(evidenceDocuments(c, task), [{ id: task, title: 'SYNTHETIC firestop listing' }]);
});

await check('blank optional details are omitted on create; an edit sends update without scope and null only for a cleared value', async () => {
  const { id, c: start, tasks } = await planned('SYNTHETIC R8 update');
  const task = tasks[1];
  let c = add(start, task, 'SYNTHETIC first title', { date: 'Rev A' });
  requests.length = 0;
  c = (await flush(id, c)).c;
  const created = evidencePosts()[0].body;
  assert.equal('responsible_party' in created, false, 'nothing invented for a blank answer');
  assert.equal(created.date, 'Rev A');
  const known = sync.acknowledgedVersion(id)!;
  requests.length = 0;
  c = add(c, task, 'SYNTHETIC renamed title', { slot: task, responsible: 'SYNTHETIC reviewer', evidenceType: 'engineering review' });
  assert.equal(c.listedEvidence?.[0]?.operation, 'update');
  const out = await flush(id, c);
  c = out.c;
  assert.equal(out.error, null);
  const update = evidencePosts()[0].body;
  assert.deepEqual(update, {
    operation: 'update', evidence_id: task, expected_version: known,
    title: 'SYNTHETIC renamed title', description: 'SYNTHETIC renamed title', evidence_type: 'engineering review',
    responsible_party: 'SYNTHETIC reviewer', date: null,
  });
  const stored = await plain.getCase(id);
  assert.equal(latest(stored, `evidence.${task}.title`)?.value, 'SYNTHETIC renamed title');
  assert.equal(latest(stored, `evidence.${task}.date`)?.value, null, 'explicit withdrawal recorded');
  assert.equal(latest(stored, `evidence.${task}.item_id`)?.value, task, 'scope retained by omission');
  assert.ok(stored.facts.some(f => f.field === `evidence.${task}.title` && f.value === 'SYNTHETIC first title'), 'earlier revision kept');
  assert.equal(stored.evidence.filter(e => e.id === task).length, 1);
  // Reload reads the same saved listing.
  const reread = await plain.getCase(id);
  assert.equal(reread.version, sync.acknowledgedVersion(id));
  assert.deepEqual(evidenceDocuments(c, task), [{ id: task, title: 'SYNTHETIC renamed title' }]);
});

await check('pushing the same staged listing twice writes once; a second document gets its own ID', async () => {
  const { id, c: start, tasks } = await planned('SYNTHETIC R8 repeat');
  const task = tasks[0];
  let c = add(start, task, 'SYNTHETIC same title');
  requests.length = 0;
  const first = await sync.pushListedEvidence(id, c.listedEvidence ?? []);
  const again = await sync.pushListedEvidence(id, c.listedEvidence ?? []);
  assert.equal(evidencePosts().length, 1, 'an acknowledged listing is not sent again');
  assert.deepEqual(again.acked, first.acked);
  c = reducer(c, { type: 'ackEvidence', ...first });
  c = add(c, task, 'SYNTHETIC same title');
  assert.equal(c.listedEvidence?.[0]?.id, `${task}~2`);
  c = (await flush(id, c)).c;
  const stored = await plain.getCase(id);
  assert.deepEqual(stored.evidence.map(e => e.id).sort(), [task, `${task}~2`].sort(), 'same title, two distinct IDs');
});

await check('removal sends a versioned DELETE for that exact ID and keeps the other document', async () => {
  const { id, c: start, tasks } = await planned('SYNTHETIC R8 delete');
  const task = tasks[0];
  let c = add(add(start, task, 'SYNTHETIC first'), task, 'SYNTHETIC second');
  c = (await flush(id, c)).c;
  const known = sync.acknowledgedVersion(id)!;
  c = reducer(c, { type: 'removeEvidence', id: task });
  assert.equal(evidenceDocuments(c, task).length, 2, 'still shown until the engine confirms removal');
  requests.length = 0;
  const out = await flush(id, c);
  c = out.c;
  assert.equal(out.error, null);
  const del = requests.find(r => r.method === 'DELETE')!;
  assert.equal(del.path, `/cases/${id}/evidence/${task}`);
  assert.deepEqual(del.body, { expected_version: known });
  assert.equal(sync.acknowledgedVersion(id), known + 1);
  assert.deepEqual(c.deletedEvidence, []);
  const stored = await plain.getCase(id);
  assert.deepEqual(stored.evidence.map(e => e.id), [`${task}~2`]);
  assert.deepEqual(evidenceDocuments(c, task), [{ id: `${task}~2`, title: 'SYNTHETIC second' }]);
});

await check('removing a listing that never reached the engine sends no request and leaves nothing queued', async () => {
  const { id, c: start, tasks } = await planned('SYNTHETIC R8 unsent');
  let c = add(start, tasks[0], 'SYNTHETIC never sent');
  c = reducer(c, { type: 'removeEvidence', id: tasks[0] });
  assert.deepEqual(c.listedEvidence ?? [], []);
  requests.length = 0;
  const out = await flush(id, c);
  assert.equal(out.error, null);
  assert.equal(requests.length, 0);
  assert.deepEqual(out.c.deletedEvidence ?? [], []);
});

await check('a lost acknowledgement is never reported as saved; an explicit refresh finds the real listing and does not duplicate it', async () => {
  const { id, c: start, tasks } = await planned('SYNTHETIC R8 lost ack');
  const task = tasks[0];
  let c = add(start, task, 'SYNTHETIC lost answer', { responsible: 'SYNTHETIC designer' });
  loseNext = { method: 'POST', suffix: '/evidence' };
  let out = await flush(id, c);
  c = out.c;
  assert.notEqual(out.error, null, 'unacknowledged');
  assert.equal(c.listedEvidence?.length, 1, 'still staged');
  assert.equal(c.facts.some(f => f.field.startsWith('evidence.')), false, 'not shown as saved');
  requests.length = 0;
  out = await flush(id, c);
  c = out.c;
  assert.equal(evidencePosts()[0]?.status, 409, 'the engine reports the version moved; no blind overwrite');
  assert.equal(sync.needsReconcile(id), true);
  assert.equal(c.listedEvidence?.length, 1);
  requests.length = 0;
  out = await flush(id, c);
  assert.equal(evidencePosts().length, 0, 'no automatic retry while a conflict waits');
  const saved = await sync.reconcileEngineCase(id);
  c = reducer(c, { type: 'ackEvidence', facts: sync.evidenceFacts(saved), refreshed: true });
  assert.deepEqual(c.listedEvidence ?? [], [], 'the saved listing matches exactly, so it is acknowledged by the fresh read');
  requests.length = 0;
  out = await flush(id, c);
  assert.equal(evidencePosts().length, 0);
  const stored = await plain.getCase(id);
  assert.equal(stored.evidence.length, 1, 'no duplicate');
  assert.deepEqual(evidenceDocuments(out.c, task), [{ id: task, title: 'SYNTHETIC lost answer' }]);
});

await check('a second writer causes a real 409: nothing overwritten, local listing kept, saved only after an explicit refresh', async () => {
  const { id, c: start, tasks } = await planned('SYNTHETIC R8 second writer');
  assert.equal((await raw('POST', `/cases/${id}/facts`, foreignFact('SYNTHETIC other writer'))).status, 200);
  let c = add(start, tasks[0], 'SYNTHETIC kept through conflict');
  const before = (await plain.getCase(id)).version;
  requests.length = 0;
  let out = await flush(id, c);
  c = out.c;
  assert.equal(evidencePosts()[0].status, 409);
  assert.equal(out.error, sync.CONFLICT_TEXT);
  assert.equal((await plain.getCase(id)).version, before, 'nothing written');
  assert.equal(c.listedEvidence?.[0]?.description, 'SYNTHETIC kept through conflict');
  const saved = await sync.reconcileEngineCase(id);
  c = reducer(c, { type: 'ackEvidence', facts: sync.evidenceFacts(saved), refreshed: true });
  requests.length = 0;
  out = await flush(id, c);
  assert.equal(out.error, null);
  assert.equal(evidencePosts()[0].body.expected_version, before);
  const stored = await plain.getCase(id);
  assert.ok(stored.facts.some(f => f.value === 'SYNTHETIC other writer'), 'other writer preserved');
  assert.equal(latest(stored, `evidence.${tasks[0]}.title`)?.value, 'SYNTHETIC kept through conflict');
});

async function terminal(id: string, c: Case) {
  c = add(c, 'ev_gone', 'SYNTHETIC listing after removal');
  requests.length = 0;
  const out = await flush(id, c);
  assert.match(out.error ?? '', /case not found/);
  assert.equal(out.c.listedEvidence?.[0]?.description, 'SYNTHETIC listing after removal', 'kept locally');
  assert.equal(out.c.facts.some(f => f.field.startsWith('evidence.')), false, 'never marked saved');
  assert.equal(requests.some(r => r.path === '/cases' && r.method === 'POST'), false, 'never recreated');
  await assert.rejects(sync.reconcileEngineCase(id), (e: unknown) => isCaseGone(e));
  assert.equal((await raw('GET', `/cases/${id}`)).status, 404);
}

await check('deleted case: the listing save is a terminal 404, kept locally, never recreated', async () => {
  const { id, c } = await planned('SYNTHETIC R8 deleted');
  assert.equal((await raw('DELETE', `/cases/${id}`)).status, 204);
  await terminal(id, c);
});

await check('expired case: the same terminal 404', async () => {
  assert.ok(db);
  const { id, c } = await planned('SYNTHETIC R8 expired');
  const store = new DatabaseSync(db!);
  store.prepare("UPDATE cases SET json=json_set(json,'$.created_at','2020-01-01T00:00:00+00:00') WHERE id=?").run(id);
  store.close();
  await terminal(id, c);
});

await check('an ambiguous legacy slot is not deleted, is not retried in a loop, and stays visible with a plain note', async () => {
  const { id, c: start } = await planned('SYNTHETIC R8 prefix');
  const legacy = (field: string, value: string) => ({ field, value, kind: 'pointed', status: 'confirmed', source: { type: 'user_text', ref: 'SYNTHETIC legacy', quote: value } });
  assert.equal((await raw('POST', `/cases/${id}/facts`, legacy('evidence.legacy.title', 'SYNTHETIC legacy parent'))).status, 200);
  assert.equal((await raw('POST', `/cases/${id}/facts`, legacy('evidence.legacy.child.title', 'SYNTHETIC legacy child'))).status, 200);
  let c = reducer(start, { type: 'ackEvidence', facts: sync.evidenceFacts(await sync.reconcileEngineCase(id)), refreshed: true });
  const before = await plain.getCase(id);
  c = reducer(c, { type: 'removeEvidence', id: 'legacy' });
  requests.length = 0;
  const out = await flush(id, c);
  c = out.c;
  assert.equal(requests.find(r => r.method === 'DELETE')?.status, 422);
  assert.deepEqual(c.deletedEvidence, [], 'not queued again');
  assert.match(c.evidenceIssues?.legacy ?? '', /couldn’t remove/i);
  assert.deepEqual((await plain.getCase(id)).facts.length, before.facts.length, 'nothing changed');
  requests.length = 0;
  await flush(id, c);
  assert.equal(requests.filter(r => r.method === 'DELETE').length, 0, 'no retry loop');
});

await check('a scope the current plan does not have is rejected without a write; the text returns to the form', async () => {
  const { id, c: start } = await planned('SYNTHETIC R8 bad scope');
  let c = add(start, 'ev_0000000000000000', 'SYNTHETIC wrong task');
  const before = (await plain.getCase(id)).version;
  const out = await flush(id, c);
  c = out.c;
  assert.equal(evidencePosts().at(-1)?.status, 422);
  assert.equal((await plain.getCase(id)).version, before);
  assert.deepEqual(c.listedEvidence ?? [], []);
  assert.equal(c.evidenceDrafts?.['ev_0000000000000000']?.document, 'SYNTHETIC wrong task', 'nothing typed is lost');
  assert.notEqual(c.evidenceDrafts?.['ev_0000000000000000']?.note ?? '', '');
});

await check('withdrawing the reference keeps the document unlinked; reselecting does not relink or send a scope', async () => {
  const { id, c: start, tasks } = await planned('SYNTHETIC R8 kept');
  const task = tasks[0];
  let c = (await flush(id, add(start, task, 'SYNTHETIC kept listing'))).c;
  c = reducer(c, { type: 'answerCandidate', id: 'r8-3.1.9.1.(1)', answer: null });
  const cleared = await readSectionD(id, c, () => true);
  assert.ok(cleared);
  c = reducer(c, { type: 'noteUnscopedEvidence', ids: [task] });
  const stored = await plain.getCase(id);
  assert.equal(latest(stored, `evidence.${task}.item_id`), undefined, 'engine removed the old link');
  assert.equal(latest(stored, `evidence.${task}.title`)?.value, 'SYNTHETIC kept listing', 'metadata kept');
  assert.deepEqual(keptDocuments(c), [{ id: task, title: 'SYNTHETIC kept listing' }]);
  c = reducer(c, { type: 'answerCandidate', id: 'r8-3.1.9.1.(1)', answer: 'yes' });
  requests.length = 0;
  assert.ok(await readSectionD(id, c, () => true));
  await flush(id, c);
  assert.equal(evidencePosts().length, 0, 'no relink request');
  assert.deepEqual(evidenceDocuments(c, task), [], 'not shown as linked to the task');
  assert.equal(latest(await plain.getCase(id), `evidence.${task}.item_id`), undefined);
});

console.log(JSON.stringify(results, null, 2));
const failed = results.filter(r => r.status === 'FAIL').length;
console.log(`R8 evidence real API: ${results.length - failed} passed, ${failed} failed`);
process.exitCode = failed ? 1 : 0;
