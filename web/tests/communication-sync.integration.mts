// J04: real accounts -> sync -> HTTP -> disposable SQLite regressions. No browser/provider.
// Run with the same SYNC_TEST_BASE / SYNC_TEST_DB environment as sync.integration.mts.
import assert from 'node:assert/strict';
import { createHash, randomUUID } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import { accounts, review } from '../src/api/accounts.ts';
import { createEngine, EngineError } from '../src/api/client.ts';
import * as sync from '../src/api/sync.ts';
import { caseFromEngine } from '../src/calm/openCase.ts';
import { reducer } from '../src/model.ts';

const base = process.env.SYNC_TEST_BASE;
assert.match(base ?? '', /^http:\/\/(127\.0\.0\.1|localhost):\d+$/);
const path = process.env.SYNC_TEST_DB;
assert.ok(path, 'SYNC_TEST_DB must name a disposable SQLite store, never a user database');
const db = new DatabaseSync(path);
const now = new Date().toISOString();
// Seed real cookie sessions, avoiding reviewer provisioning and password hashing in a sync test.
const sessions = Object.fromEntries(['owner', 'officer', 'stranger'].map((name) => {
  const user = {
    id: `j04-${randomUUID()}`, email: `${name}-${randomUUID()}@example.test`, name: `Synthetic ${name}`,
    role: name === 'officer' ? 'reviewer' : 'applicant', onboarded: true, created_at: now,
    authority: name === 'officer' ? 'edmonton' : null,
    applicant_type: name === 'officer' ? null : 'contractor', notifications_seen_at: null,
  };
  const token = randomUUID().replaceAll('-', '').padEnd(43, '_');
  db.prepare('INSERT INTO account_users(id,email,data) VALUES (?,?,?)').run(user.id, user.email, JSON.stringify({ user, password: null }));
  db.prepare('INSERT INTO account_sessions(digest,user_id,expires_at) VALUES (?,?,?)')
    .run(createHash('sha256').update(token).digest('hex'), user.id, Date.now() / 1000 + 3600);
  return [name, { user, token }];
}));
globalThis.sessionStorage = {
  data: new Map(), getItem(k) { return this.data.get(k) ?? null; }, setItem(k, v) { this.data.set(k, String(v)); },
  removeItem(k) { this.data.delete(k); }, clear() { this.data.clear(); },
} as unknown as Storage;
const originalFetch = globalThis.fetch;
let actor = 'owner';
const requests: { path: string; method: string; actor: string; status: number }[] = [];
globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = String(input).replace(/^\/api/, base!);
  assert.equal(new URL(url).origin, base, 'only the disposable engine is reachable');
  const headers = new Headers(init?.headers);
  headers.set('Cookie', `batatis_session=${sessions[actor].token}`);
  const response = await originalFetch(url, { ...init, headers });
  requests.push({ path: new URL(url).pathname, method: init?.method ?? 'GET', actor, status: response.status });
  return response;
}) as typeof fetch;
const engine = createEngine(base!);
async function as<T>(name: string, work: () => Promise<T>): Promise<T> {
  const previous = actor;
  actor = name;
  try { return await work(); } finally { actor = previous; }
}
const results: { name: string; status: string; error?: string }[] = [];
async function check(name: string, work: () => Promise<void>) {
  try { await work(); results.push({ name, status: 'PASS' }); }
  catch (e) { results.push({ name, status: 'FAIL', error: e instanceof Error ? e.stack ?? e.message : String(e) }); }
}
let id: string;
let local: ReturnType<typeof caseFromEngine>;
let task: string;

try {
  await check('open returned case, mark its banner read, correct a fact and explicitly check with the acknowledged version', async () => {
    const created = await engine.createCase({ title: 'SYNTHETIC J04 returned application', jurisdiction: { id: 'edmonton', name: 'Edmonton' } });
    id = created.id;
    // An incomplete submitted fixture lets the real officer claim/return routes produce the decision.
    const submitted = { ...created, status: 'submitted', submitted_at: now };
    db.prepare('UPDATE cases SET json=?, version=version+1 WHERE id=?').run(JSON.stringify(submitted), id);
    await as('officer', async () => {
      await review.claim(id);
      await review.decide(id, { outcome: 'return', message: 'Please correct the synthetic legal description.', items: [] });
    });
    const opened = await engine.getCase(id);
    sync.clearEngineSession();
    sync.adoptEngineCase(opened);
    local = caseFromEngine(opened, 'contractor');
    assert.equal((await accounts.messages(id)).at(-1)?.read_by_me, false);
    assert.equal(await accounts.markRead(id), undefined, 'receipt remains an empty 204');
    assert.equal(sync.acknowledgedVersion(id), opened.version);
    assert.equal((await engine.getCase(id)).version, opened.version);
    local = reducer(local, { type: 'setDetail', field: 'legalDescription', value: 'SYNTHETIC Lot 2 Block 3 Plan 4', section: 'B' });
    assert.equal(await sync.pushFacts(id, local.facts), null);
    assert.equal(sync.acknowledgedVersion(id), opened.version + 1);
    const identified = await engine.identify(id, 'Synthetic proposed exterior insulation board.', [], undefined, undefined, sync.acknowledgedVersion(id)!);
    sync.acknowledgeWrite(id, identified.case_version);
    assert.equal(sync.acknowledgedVersion(id), (await engine.getCase(id)).version);
    assert.equal(identified.trace.usd, 0, 'offline fallback spends nothing');
  });

  await check('owner reply rejects; officer notices and applicant receipts leave the real evidence sync writable', async () => {
    const known = sync.acknowledgedVersion(id);
    const before = await engine.getCase(id);
    await assert.rejects(accounts.postMessage(id, 'Synthetic applicant correction reply.'), e => e instanceof EngineError && e.status === 403);
    assert.deepEqual(await engine.getCase(id), before);
    const notice = await as('officer', () => accounts.postMessage(id, 'Synthetic officer correction notice.'));
    assert.equal(notice.read_by_me, true);
    await as('officer', async () => {
      await accounts.markRead(id);
      await accounts.postMessage(id, 'Synthetic officer follow-up.');
    });
    await accounts.markRead(id);
    assert.equal(sync.acknowledgedVersion(id), known);
    assert.equal((await engine.getCase(id)).version, known);
    const plan = await engine.sectionD(id, { provisions: ['3.1.9.1.(1)'], expected_version: known! });
    sync.acknowledgeWrite(id, plan.case_version);
    task = plan.items[0].id;
    local = reducer(local, { type: 'saveEvidence', itemId: task, document: 'SYNTHETIC applicant listing', responsible: 'SYNTHETIC author', date: '', evidenceType: 'evaluation', provisionId: '3.1.9.1.(1)' });
    const out = await sync.pushListedEvidence(id, local.listedEvidence ?? []);
    assert.equal(out.error, null);
    assert.equal(out.acked.length, 1);
    assert.equal(out.rejected.length, 0);
    local = reducer(local, { type: 'ackEvidence', ...out });
    const saved = await engine.getCase(id);
    assert.equal(sync.acknowledgedVersion(id), saved.version);
    assert.ok(saved.evidence.some(item => item.id === task));
    assert.ok(saved.messages.some(message => message.id === notice.id && message.read_by.includes(sessions.owner.user.id)));
    assert.ok((await accounts.messages(id)).every(message => message.read_by_me));
  });

  await check('a thread response cannot adopt or conceal an external content edit; stale check and evidence saves reject', async () => {
    const known = sync.acknowledgedVersion(id)!;
    await engine.addFact(id, { field: 'process.maintenance_operation', value: 'SYNTHETIC other-session content', kind: 'pointed', status: 'confirmed', source: { type: 'user_text', ref: 'Synthetic second session', quote: 'SYNTHETIC other-session content' } });
    await as('officer', () => accounts.postMessage(id, 'Synthetic message after external content edit.'));
    await accounts.markRead(id);
    await assert.rejects(accounts.postMessage(id, 'Synthetic reply after external content edit.'), e => e instanceof EngineError && e.status === 403);
    assert.equal(sync.acknowledgedVersion(id), known);
    assert.equal((await engine.getCase(id)).version, known + 1);
    await assert.rejects(engine.identify(id, 'Synthetic insulation proposal.', [], undefined, undefined, known), e => e instanceof EngineError && e.status === 409);
    local = reducer(local, { type: 'saveEvidence', itemId: task, document: 'SYNTHETIC stale listing', responsible: '', date: '', evidenceType: 'evaluation', provisionId: '3.1.9.1.(1)' });
    const out = await sync.pushListedEvidence(id, local.listedEvidence ?? []);
    assert.equal(out.error, sync.CONFLICT_TEXT);
    assert.deepEqual(out.acked, []);
    assert.equal(sync.needsReconcile(id), true);
    assert.equal(sync.acknowledgedVersion(id), known);
    const stored = await engine.getCase(id);
    assert.equal(stored.evidence.length, 1);
    assert.ok(stored.facts.some(fact => fact.value === 'SYNTHETIC other-session content'));
  });

  await check('only an explicit reconcile clears the conflict and allows the pending listing to save', async () => {
    const current = await sync.reconcileEngineCase(id);
    assert.equal(sync.acknowledgedVersion(id), current.version);
    assert.equal(sync.needsReconcile(id), false);
    const out = await sync.pushListedEvidence(id, local.listedEvidence ?? []);
    assert.equal(out.error, null);
    assert.equal(out.acked.length, 1);
    assert.equal((await engine.getCase(id)).evidence.length, 2);
  });

  await check('authoritative return and displayed-message receipts survive later follow-ups and reload', async () => {
    const opened = await accounts.conversation(id);
    assert.equal(opened.decision?.outcome, 'return');
    const version = sync.acknowledgedVersion(id);
    const later = await as('officer', () => accounts.postMessage(id, 'Synthetic later unseen officer notice.'));
    await accounts.markRead(id, opened.messages.map(message => message.id));
    const reopened = await accounts.conversation(id);
    assert.deepEqual(reopened.decision, opened.decision, 'follow-up must retain decision timestamp/body/items');
    assert.equal(reopened.messages.find(message => message.id === later.id)?.read_by_me, false, 'unseen concurrent notice remains unread');
    assert.equal((await engine.getCase(id)).version, version);
    await accounts.markRead(id, [later.id]);
    assert.equal((await accounts.conversation(id)).messages.find(message => message.id === later.id)?.read_by_me, true);
  });

  await check('thread-only mutations retain owner/authority authorization', async () => {
    const before = await engine.getCase(id);
    await as('stranger', async () => {
      await assert.rejects(accounts.markRead(id), e => e instanceof EngineError && e.status === 404);
      await assert.rejects(accounts.postMessage(id, 'Synthetic unauthorized message.'), e => e instanceof EngineError && e.status === 404);
    });
    assert.deepEqual(await engine.getCase(id), before);
    assert.equal(sync.acknowledgedVersion(id), before.version);
  });
} finally {
  globalThis.fetch = originalFetch;
  sync.clearEngineSession();
  db.close();
}
console.log(JSON.stringify({ results, requests, passed: results.filter(result => result.status === 'PASS').length, failed: results.filter(result => result.status === 'FAIL').length }, null, 2));
process.exitCode = results.some(result => result.status === 'FAIL') ? 1 : 0;
