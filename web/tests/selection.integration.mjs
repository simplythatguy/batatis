// Code-check selections survive switching applications and reloading (docs/api/selected-articles.md).
// The actual CaseProvider (tests/provider.html) against a disposable engine with a code database:
// reducer → save queue → PUT /cases/{id}/selected-articles → GET /cases/{id} → reopen. Synthetic data only.
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { chromium } from 'playwright-core';

const base = process.env.SYNC_TEST_BASE;
const web = process.env.SYNC_WEB_BASE;
const db = process.env.SYNC_TEST_DB;
assert.match(base ?? '', /^http:\/\/(127\.0\.0\.1|localhost):\d+/);
assert.match(web ?? '', /^http:\/\/(127\.0\.0\.1|localhost):\d+/);
assert.ok(db, 'Set SYNC_TEST_DB to the disposable engine store.');
const browser = await chromium.launch({ ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}), headless: true });
let passed = 0;
let failed = 0;

const remote = async id => (await fetch(base + '/cases/' + id)).json();
const card = provision => ({
  id: `search-${provision}`, topic: provision, provision, part: 9, benchmark: false, identified: true, suggestion: 'search',
  quote: { text: 'SYNTHETIC added from the code library', citation: '', source: 'code' },
  departure: 'do something other than what this sentence requires', clarifyingQuestion: 'Which part of this sentence does the design not follow?', answer: null,
});
const pick = (id, provision, answer = null, pending = false) => ({ id, provision, answer, pending });
/** Sign in as a fixed synthetic account on the test engine, creating it once (signups are rate limited). */
const account = (p, email, name) => p.evaluate(async ({ base, email, name }) => {
  const send = (path, body) => fetch(base + path, { method: 'POST', credentials: 'include', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  const login = await send('/auth/login', { email, password: 'SYNTHETIC-password-1' });
  if (login.status === 200) return 200;
  return (await send('/auth/signup', { email, password: 'SYNTHETIC-password-1', name })).status;
}, { base, email, name });

/**
 * Only the harness page and the test engine are reachable; anything else is aborted and fails the scenario.
 * So is /api on the harness origin: Vite would proxy it to its own target (by default :8000), not the test engine.
 */
const owned = new Set([new URL(web).host, new URL(base).host]);
const proxied = (u) => u.host === new URL(web).host && u.pathname.startsWith('/api/');
async function page() {
  const ctx = await browser.newContext();
  const offsite = [];
  await ctx.route('**/*', route => {
    const u = new URL(route.request().url());
    if (['http:', 'https:'].includes(u.protocol) && (!owned.has(u.host) || proxied(u))) { offsite.push(`${route.request().method()} ${u.href}`); return route.abort(); }
    return route.continue();
  });
  const p = await ctx.newPage();
  p.errors = [];
  p.offsite = offsite;
  p.on('pageerror', e => p.errors.push(e.message));
  await p.addInitScript(({ base }) => {
    const original = window.fetch;
    window.requests = [];
    window.fetch = async (input, init) => {
      const url = new URL(String(input), location.href);
      const target = url.pathname.startsWith('/api/') ? base + url.pathname.slice(4) + url.search : url.origin === location.origin ? base + url.pathname + url.search : String(input);
      window.requests.push(`${init?.method ?? 'GET'} ${target.replace(base, '')}`);
      const hold = window.hold;
      const match = hold && !hold.used && target.replace(base, '').match(hold.path) && (init?.method ?? 'GET') === hold.method;
      if (match) {
        hold.used = true;
        hold.wait = new Promise(resolve => { window.release = resolve; });
        if (!hold.after) { hold.ready = true; await hold.wait; }
        if (hold.fail) return new Response(JSON.stringify({ detail: 'synthetic outage' }), { status: 503, headers: { 'content-type': 'application/json' } });
      }
      const response = await original(target, { ...init, credentials: 'include' });
      if (match && hold.after) { hold.ready = true; await hold.wait; }
      return response;
    };
  }, { base });
  await p.goto(web + '/tests/provider.html');
  await p.waitForFunction(() => !!window.caseStore);
  return p;
}

async function scenario(name, run) {
  const pages = [];
  const open = async () => { const p = await page(); pages.push(p); return p; };
  try {
    await run(open);
    for (const p of pages) assert.deepEqual(p.errors, []);
    for (const p of pages) assert.deepEqual(p.offsite, [], 'no request leaves the harness and the test engine');
    passed++;
    console.log('PASS', name);
  } catch (e) {
    failed++;
    console.log('FAIL', name, '\n ', String(e?.message ?? e).split('\n').slice(0, 12).join('\n  '));
  } finally { for (const p of pages) await p.context().close(); }
}

const settle = p => p.evaluate(() => new Promise(r => setTimeout(r, 50)));
const dispatch = async (p, action) => { await p.evaluate(a => window.caseStore.dispatch(a), action); await settle(p); };
/** Wait until the deterministic Section C lookup has settled the cards (as the screen would). */
const looked = p => p.waitForFunction(() => window.caseStore.sectionCLookup.source !== 'loading');
const begin = async p => { await p.evaluate(() => window.caseStore.beginEmpty('homebuilder')); await p.waitForFunction(() => window.caseStore.phase === 'case'); };
const save = async p => { await looked(p); await settle(p); return p.evaluate(() => window.caseStore.saveDraft()); };
const openCase = (p, id) => p.evaluate(id => window.caseStore.openCase(id, 'homebuilder'), id);
const cards = p => p.evaluate(() => window.caseStore.c.candidates.filter(a => /^\d/.test(a.provision)).map(a => [a.id, a.provision, a.answer, Boolean(a.pending), a.benchmark]));
const status = p => p.evaluate(() => ({ save: window.caseStore.saveStatus, note: window.caseStore.savedNote, detail: window.caseStore.saveDetail }));
const puts = p => p.evaluate(() => window.requests.filter(r => r.startsWith('PUT') && r.includes('/selected-articles')));
const hold = (p, path, method, { after = true, fail = false } = {}) => p.evaluate(h => { window.hold = { ...h, path: new RegExp(h.path) }; }, { path, method, after, fail });
const waitHeld = p => p.waitForFunction(() => window.hold?.ready);

/** Application A: three sentences, unanswered / No / Not sure. Application B: another sentence unanswered and a pending Yes. */
async function twoApplications(p) {
  await begin(p);
  await dispatch(p, { type: 'setDetail', field: 'owner', value: 'SYNTHETIC owner A', section: 'A' });
  for (const s of ['9.25.2.2.(1)', '9.27.3.4.(1)', '9.10.9.16.(1)']) await dispatch(p, { type: 'addCandidate', candidate: card(s) });
  await dispatch(p, { type: 'answerCandidate', id: 'search-9.27.3.4.(1)', answer: 'no' });
  await dispatch(p, { type: 'answerCandidate', id: 'search-9.10.9.16.(1)', answer: 'not-sure' });
  const a = await save(p);
  assert.ok(a);
  await begin(p);
  await dispatch(p, { type: 'setDetail', field: 'owner', value: 'SYNTHETIC owner B', section: 'A' });
  for (const s of ['9.36.2.6.(1)', '9.27.3.4.(2)']) await dispatch(p, { type: 'addCandidate', candidate: card(s) });
  await dispatch(p, { type: 'answerCandidate', id: 'search-9.27.3.4.(2)', answer: 'yes' });
  await dispatch(p, { type: 'markDecisionPending', id: 'search-9.27.3.4.(2)', pending: true });
  const b = await save(p);
  assert.ok(b && b !== a);
  return { a, b };
}

const A = [['search-9.25.2.2.(1)', '9.25.2.2.(1)', null, false, false], ['search-9.27.3.4.(1)', '9.27.3.4.(1)', 'no', false, false], ['search-9.10.9.16.(1)', '9.10.9.16.(1)', 'not-sure', false, false]];
const B = [['search-9.36.2.6.(1)', '9.36.2.6.(1)', null, false, false], ['search-9.27.3.4.(2)', '9.27.3.4.(2)', 'yes', true, false]];

try {
  await scenario('two applications keep disjoint selections across switching and a reload, with no benchmark promotion', async open => {
    const p = await open();
    const { a, b } = await twoApplications(p);
    assert.deepEqual((await remote(a)).selected_articles, [pick('search-9.25.2.2.(1)', '9.25.2.2.(1)'), pick('search-9.27.3.4.(1)', '9.27.3.4.(1)', 'no'), pick('search-9.10.9.16.(1)', '9.10.9.16.(1)', 'not-sure')]);
    assert.deepEqual((await remote(b)).selected_articles, [pick('search-9.36.2.6.(1)', '9.36.2.6.(1)'), pick('search-9.27.3.4.(2)', '9.27.3.4.(2)', 'yes', true)]);
    for (const id of [a, b]) assert.deepEqual((await remote(id)).provisions, [], 'a selection never confirms a reference');
    assert.equal(await openCase(p, a), null);
    await looked(p);
    assert.deepEqual(await cards(p), A);
    assert.ok(await p.evaluate(() => window.caseStore.c.questions.some(q => q.cardId === 'search-9.10.9.16.(1)')), 'Not sure keeps its open question');
    assert.equal(await openCase(p, b), null);
    await looked(p);
    assert.deepEqual(await cards(p), B, 'the pending Yes stays pending and is not a benchmark');
    // A reload has no memory: the cards come from the saved case only.
    const fresh = await open();
    assert.equal(await openCase(fresh, a), null);
    await looked(fresh);
    assert.deepEqual(await cards(fresh), A);
    await save(fresh);
    assert.deepEqual(await puts(fresh), [], 'reopening and saving at once sends no selection write');
    assert.equal(await openCase(fresh, b), null);
    await looked(fresh);
    assert.deepEqual(await cards(fresh), B);
    assert.deepEqual((await remote(b)).provisions, []);
  });

  await scenario('removing and clearing cards stay removed; an article expanded to sentences reopens without duplicates or reset answers', async open => {
    const p = await open();
    const { a } = await twoApplications(p);
    assert.equal(await openCase(p, a), null);
    await looked(p);
    await dispatch(p, { type: 'removeCandidate', id: 'search-9.27.3.4.(1)' });
    await dispatch(p, { type: 'addCandidate', candidate: card('9.25.2.2.') });
    await looked(p);
    // The overlapping article adds the sentences the applicant had not selected yet, each unanswered.
    await p.waitForFunction(() => window.caseStore.c.candidates.some(x => x.id === 'provision-9.25.2.2.(2)'));
    await dispatch(p, { type: 'answerCandidate', id: 'provision-9.25.2.2.(3)', answer: 'yes' });
    await save(p);
    const expected = await cards(p);
    assert.deepEqual(expected.map(x => x[0]).sort(), ['provision-9.25.2.2.(2)', 'provision-9.25.2.2.(3)', 'search-9.10.9.16.(1)', 'search-9.25.2.2.(1)']);
    const fresh = await open();
    assert.equal(await openCase(fresh, a), null);
    await looked(fresh);
    await settle(fresh);
    assert.deepEqual(await cards(fresh), expected, 'same cards, ids, order and answers; 9.27.3.4.(1) stays removed');
    assert.equal(new Set((await cards(fresh)).map(x => x[1])).size, expected.length, 'one card per provision');
    for (const [id] of expected) await dispatch(fresh, { type: 'removeCandidate', id });
    await save(fresh);
    assert.deepEqual((await remote(a)).selected_articles, [], 'clearing saves an explicit empty list');
    const again = await open();
    assert.equal(await openCase(again, a), null);
    await looked(again);
    assert.deepEqual(await cards(again), []);
  });

  await scenario('a legacy case keeps its confirmed-reference fallback; an explicit empty list never refills it', async open => {
    const p = await open();
    const created = await (await fetch(base + '/cases', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ title: 'SYNTHETIC legacy' }) })).json();
    const confirmed = await (await fetch(base + `/cases/${created.id}/identify/confirm`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ provisions: ['9.27.3.4.(1)'], expected_version: created.version }) })).json();
    assert.equal(confirmed.selected_articles, null);
    assert.equal(await openCase(p, created.id), null);
    await looked(p);
    assert.deepEqual((await cards(p)).map(x => [x[0], x[2]]), [['search-9.27.3.4.(1)', 'yes']]);
    await dispatch(p, { type: 'setDetail', field: 'owner', value: 'SYNTHETIC legacy owner', section: 'A' });
    await save(p);
    assert.deepEqual(await puts(p), [], 'an unchanged legacy selection is not rewritten');
    assert.equal((await remote(created.id)).selected_articles, null);
    await dispatch(p, { type: 'removeCandidate', id: 'search-9.27.3.4.(1)' });
    await save(p);
    const saved = await remote(created.id);
    assert.deepEqual(saved.selected_articles, []);
    assert.deepEqual(saved.provisions, ['9.27.3.4.(1)'], 'the selection route leaves confirmed references to their own routes');
    const fresh = await open();
    assert.equal(await openCase(fresh, created.id), null);
    await looked(fresh);
    assert.deepEqual(await cards(fresh), [], 'the removed reference is not refilled from the older confirmed list');
  });

  await scenario('a delayed selection save never lands on the application opened meanwhile', async open => {
    const p = await open();
    const { a, b } = await twoApplications(p);
    assert.equal(await openCase(p, a), null);
    await looked(p);
    await dispatch(p, { type: 'addCandidate', candidate: card('9.36.2.6.(1)') });
    await looked(p);
    await hold(p, '/selected-articles$', 'PUT');
    await p.evaluate(() => { window.pending = window.caseStore.saveDraft(); });
    await waitHeld(p);
    assert.equal(await openCase(p, b), null);
    await looked(p);
    await p.evaluate(async () => { window.release(); await window.pending; });
    await settle(p);
    assert.deepEqual(await cards(p), B, 'the late reply for A changes nothing in B');
    assert.equal((await status(p)).save, 'saved');
    await dispatch(p, { type: 'answerCandidate', id: 'search-9.36.2.6.(1)', answer: 'no' });
    await save(p);
    assert.equal((await status(p)).save, 'saved', 'B keeps its own acknowledged version');
    assert.deepEqual((await remote(b)).selected_articles.map(x => x.answer), ['no', 'yes']);
    assert.ok((await remote(a)).selected_articles.some(x => x.provision === '9.36.2.6.(1)'), 'the request that reached the engine is A\'s');
  });

  await scenario('a delayed read while opening shows only the application that finished opening', async open => {
    const p = await open();
    const { a, b } = await twoApplications(p);
    assert.equal(await openCase(p, b), null);
    await hold(p, `/cases/${a}$`, 'GET', { after: true });
    await p.evaluate(id => { window.pending = window.caseStore.openCase(id, 'homebuilder'); }, a);
    await waitHeld(p);
    assert.deepEqual(await cards(p), B, 'B stays as it was while A is still being read');
    await p.evaluate(async () => { window.release(); await window.pending; });
    await looked(p);
    assert.deepEqual(await cards(p), A);
  });

  for (const [what, path] of [['the case read', '$'], ['the stored intake read', '/intake$']]) {
    await scenario(`starting over while ${what} of an opening application is held keeps the new draft`, async open => {
      const p = await open();
      const { a } = await twoApplications(p);
      const before = await remote(a);
      await begin(p);
      await hold(p, `/cases/${a}${path}`, 'GET');
      await p.evaluate(id => { window.opening = window.caseStore.openCase(id, 'homebuilder'); }, a);
      await waitHeld(p);
      await begin(p);                                                    // Start over / New application
      await dispatch(p, { type: 'setDetail', field: 'owner', value: 'SYNTHETIC new draft owner', section: 'A' });
      await dispatch(p, { type: 'addCandidate', candidate: card('9.36.2.6.(1)') });
      const result = await p.evaluate(async () => { window.release(); return await window.opening; });
      await settle(p);
      assert.equal(result, null, 'a superseded open reports nothing to its caller');
      const state = await p.evaluate(() => ({ engineId: window.caseStore.engineId, phase: window.caseStore.phase, owner: window.caseStore.c.facts.find(f => f.field === 'owner')?.value }));
      assert.notEqual(state.engineId, a, 'the old application is not reattached');
      assert.equal(state.owner, 'SYNTHETIC new draft owner');
      assert.deepEqual((await cards(p)).map(x => x[0]), ['search-9.36.2.6.(1)'], 'the old cards never replace the new draft');
      const id = await save(p);
      assert.ok(id && id !== a, 'the new draft saves as its own application');
      assert.deepEqual((await remote(id)).selected_articles, [pick('search-9.36.2.6.(1)', '9.36.2.6.(1)')]);
      const after = await remote(a);
      assert.deepEqual([after.version, after.selected_articles], [before.version, before.selected_articles], 'nothing was written to the old application');
    });
  }

  await scenario('a newer open wins over an older one still reading', async open => {
    const p = await open();
    const { a, b } = await twoApplications(p);
    await hold(p, `/cases/${a}/intake$`, 'GET');
    await p.evaluate(id => { window.older = window.caseStore.openCase(id, 'homebuilder'); }, a);
    await waitHeld(p);
    assert.equal(await openCase(p, b), null);
    await looked(p);
    assert.equal(await p.evaluate(async () => { window.release(); return await window.older; }), null);
    await settle(p);
    assert.equal(await p.evaluate(() => window.caseStore.engineId), b);
    assert.deepEqual(await cards(p), B, 'B stays open with its own cards');
    await dispatch(p, { type: 'answerCandidate', id: 'search-9.36.2.6.(1)', answer: 'no' });
    await save(p);
    assert.equal((await status(p)).save, 'saved', 'B keeps its own acknowledged version');
  });

  await scenario('opening Section D never confirms a pending Yes; an acknowledged Yes is confirmed', async open => {
    const p = await open();
    const make = async (selected) => {
      const created = await (await fetch(base + '/cases', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ title: 'SYNTHETIC Section D' }) })).json();
      const r = await fetch(base + `/cases/${created.id}/selected-articles`, { method: 'PUT', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ expected_version: created.version, selected_articles: selected }) });
      assert.equal(r.status, 200);
      return created.id;
    };
    const sectionD = () => p.evaluate(() => window.caseStore.loadSectionD().then(() => null, e => e.message));
    const waiting = await make([pick('search-9.27.3.4.(1)', '9.27.3.4.(1)', 'yes', true)]);
    assert.equal(await openCase(p, waiting), null);
    await p.waitForFunction(() => window.caseStore.sectionCLookup.source === 'live');
    await settle(p);
    await sectionD(p);
    const held = await remote(waiting);
    assert.deepEqual(held.provisions, [], 'the pending Yes is not a confirmed reference');
    assert.deepEqual(held.selected_articles, [pick('search-9.27.3.4.(1)', '9.27.3.4.(1)', 'yes', true)], 'its saved answer and pending state stay');
    assert.deepEqual(await cards(p), [['search-9.27.3.4.(1)', '9.27.3.4.(1)', 'yes', true, false]]);
    const acked = await make([pick('search-9.27.3.4.(1)', '9.27.3.4.(1)', 'yes')]);
    assert.equal(await openCase(p, acked), null);
    await p.waitForFunction(() => window.caseStore.sectionCLookup.source === 'live');
    await settle(p);
    assert.equal(await sectionD(p), null);
    assert.deepEqual((await remote(acked)).provisions, ['9.27.3.4.(1)'], 'an acknowledged Yes still becomes a confirmed reference');
  });

  await scenario('a read-only application holding an unexpanded article reopens without writing and can be left', async open => {
    const p = await open();
    const call = (path, method = 'GET', body) => p.evaluate(async ({ base, path, method, body }) => { const r = await fetch(base + path, { method, credentials: 'include', headers: { 'content-type': 'application/json' }, ...(body ? { body: JSON.stringify(body) } : {}) }); return { status: r.status, body: await r.json().catch(() => null) }; }, { base, path, method, body });
    assert.ok([200, 201].includes(await account(p, 'selection-readonly@example.test', 'SYNTHETIC Owner')));
    const seed = async (title, status) => {
      const c = (await call('/cases', 'POST', { title })).body;
      assert.equal((await call(`/cases/${c.id}/selected-articles`, 'PUT', { expected_version: c.version, selected_articles: [pick('search-9.25.2.2.', '9.25.2.2.')] })).status, 200);
      if (status) {                                                    // as the submit route would leave it (owned test store)
        const sql = new DatabaseSync(db);
        const row = sql.prepare('SELECT json FROM cases WHERE id=?').get(c.id);
        sql.prepare('UPDATE cases SET json=? WHERE id=?').run(JSON.stringify({ ...JSON.parse(row.json), status }), c.id);
        sql.close();
      }
      return c.id;
    };
    const sent = id => p.evaluate(id => window.requests.filter(r => !r.startsWith('GET') && r.includes(`/cases/${id}`)), id);
    const sentId = await seed('SYNTHETIC submitted', 'submitted');
    const other = await seed('SYNTHETIC other draft');
    await p.evaluate(() => { window.requests.length = 0; });           // the seeding writes above are not the app's
    assert.equal(await openCase(p, sentId), null);
    await looked(p);
    await p.waitForFunction(() => window.caseStore.c.candidates.some(a => a.id === 'provision-9.25.2.2.(2)'));
    await p.evaluate(() => new Promise(r => setTimeout(r, 1200)));     // past the 500 ms automatic save
    assert.deepEqual(await sent(sentId), [], 'nothing is written to a read-only application');
    assert.equal((await status(p)).save, 'saved', 'the expansion is not an unsaved change');
    // Card changes the applicant could still reach (the legacy references screen's Remove) are refused, not
    // applied and then silently dropped: the screen keeps showing what is saved.
    const shown = await cards(p);
    await dispatch(p, { type: 'removeCandidate', id: 'provision-9.25.2.2.(2)' });
    await dispatch(p, { type: 'answerCandidate', id: 'provision-9.25.2.2.(1)', answer: 'no' });
    await dispatch(p, { type: 'answerCandidate', id: 'provision-9.25.2.2.(3)', answer: 'not-sure' });
    await dispatch(p, { type: 'addCandidate', candidate: card('9.36.2.6.(1)') });
    await p.evaluate(() => new Promise(r => setTimeout(r, 900)));
    assert.deepEqual(await cards(p), shown, 'a read-only application\'s cards do not change on screen');
    assert.equal(await p.evaluate(() => window.caseStore.saveDraft()), sentId, 'an explicit save has nothing to send');
    assert.deepEqual(await sent(sentId), [], 'still nothing written');
    assert.equal((await status(p)).save, 'saved');
    const switched = await p.evaluate(async other => {
      const { switchApplication } = await import('/src/calm/libraryContext.ts');
      const s = window.caseStore;
      return switchApplication(other, { inCase: s.phase === 'case', saveStatus: s.saveStatus, saveDraft: s.saveDraft, openCase: id => s.openCase(id, 'homebuilder'), settle: () => {} });
    }, other);
    assert.equal(switched, null, 'the guarded switch leaves the read-only application');
    assert.equal(await p.evaluate(() => window.caseStore.engineId), other);
    assert.deepEqual((await call(`/cases/${sentId}`)).body.selected_articles, [pick('search-9.25.2.2.', '9.25.2.2.')], 'its saved selection is unchanged');
    // The editable application expands the same article and saves the sentence cards.
    await looked(p);
    await p.waitForFunction(() => window.caseStore.c.candidates.some(a => a.id === 'provision-9.25.2.2.(2)'));
    await save(p);
    assert.equal((await status(p)).save, 'saved');
    assert.deepEqual((await call(`/cases/${other}`)).body.selected_articles.map(x => x.id), ['provision-9.25.2.2.(1)', 'provision-9.25.2.2.(2)', 'provision-9.25.2.2.(3)']);
  });

  await scenario('an answer on a draft that is sent elsewhere meanwhile is never reported saved', async open => {
    const p = await open();
    assert.ok([200, 201].includes(await account(p, 'selection-flip@example.test', 'SYNTHETIC Owner')));
    await begin(p);
    await dispatch(p, { type: 'setDetail', field: 'owner', value: 'SYNTHETIC flipped', section: 'A' });
    await dispatch(p, { type: 'addCandidate', candidate: card('9.27.3.4.(1)') });
    const id = await save(p);
    assert.ok(id);
    const remoteNow = async () => (await p.evaluate(async ({ base, id }) => (await fetch(base + '/cases/' + id, { credentials: 'include' })).json(), { base, id })).selected_articles;
    assert.deepEqual(await remoteNow(), [pick('search-9.27.3.4.(1)', '9.27.3.4.(1)')]);
    // Sent elsewhere (as the submit route would leave it; owned test store), then the applicant answers here.
    const sql = new DatabaseSync(db);
    const row = sql.prepare('SELECT json FROM cases WHERE id=?').get(id);
    sql.prepare('UPDATE cases SET json=? WHERE id=?').run(JSON.stringify({ ...JSON.parse(row.json), status: 'submitted' }), id);
    sql.close();
    await dispatch(p, { type: 'answerCandidate', id: 'search-9.27.3.4.(1)', answer: 'no' });
    await p.evaluate(() => new Promise(r => setTimeout(r, 900)));     // the automatic save meets the real 409
    const first = await status(p);
    assert.equal(first.save, 'failed', 'the refused save is not saved');
    assert.ok((await p.evaluate(() => window.requests)).some(r => r === `PUT /cases/${id}/selected-articles`));
    assert.equal(await p.evaluate(() => window.caseStore.saveDraft()), null, 'the explicit save (which reads the case first) is not acknowledged');
    const second = await status(p);
    assert.notEqual(second.save, 'saved', 'never reported saved while the server keeps the old answer');
    assert.match(second.detail, /read-only/i, 'and it says why');
    assert.deepEqual(await remoteNow(), [pick('search-9.27.3.4.(1)', '9.27.3.4.(1)')], 'the server keeps the old selection');
    assert.deepEqual((await cards(p)).map(x => [x[0], x[2]]), [['search-9.27.3.4.(1)', 'no']], 'the applicant\'s answer stays on screen');
  });

  await scenario('rejected selection writes keep the cards and store nothing', async open => {
    const p = await open();
    const { a } = await twoApplications(p);
    assert.equal(await openCase(p, a), null);
    await looked(p);
    const before = (await remote(a)).selected_articles;
    await dispatch(p, { type: 'addCandidate', candidate: card('9.36.2.6.(1)') });
    await looked(p);
    await hold(p, '/selected-articles$', 'PUT', { after: false, fail: true });
    await p.evaluate(() => { window.pending = window.caseStore.saveDraft(); });
    await waitHeld(p);
    await p.evaluate(async () => { window.release(); await window.pending; });
    assert.equal((await status(p)).save, 'failed');
    assert.deepEqual((await remote(a)).selected_articles, before);
    assert.ok((await cards(p)).some(x => x[1] === '9.36.2.6.(1)'), 'the card stays on screen');
    await save(p);
    assert.equal((await status(p)).save, 'saved', 'the next save sends it');
    assert.ok((await remote(a)).selected_articles.some(x => x.provision === '9.36.2.6.(1)'));
    // A provision the code database does not have: the whole list is refused, never partly stored.
    const stored = (await remote(a)).selected_articles;
    await dispatch(p, { type: 'addCandidate', candidate: card('9.99.99.99.(1)') });
    await save(p);
    const refused = await status(p);
    assert.equal(refused.save, 'failed', 'not gone: the case still exists');
    assert.match(refused.detail, /code reference wasn’t found/);
    assert.deepEqual((await remote(a)).selected_articles, stored);
    await dispatch(p, { type: 'removeCandidate', id: 'search-9.99.99.99.(1)' });
    await save(p);
    assert.equal((await status(p)).save, 'saved');
  });

  await scenario('another write wins: the selection is not overwritten until an explicit reconcile', async open => {
    const p = await open();
    const { b } = await twoApplications(p);
    assert.equal(await openCase(p, b), null);
    await looked(p);
    const elsewhere = await remote(b);
    const other = await fetch(base + `/cases/${b}/selected-articles`, { method: 'PUT', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ selected_articles: [pick('search-9.10.9.16.(1)', '9.10.9.16.(1)', 'no')], expected_version: elsewhere.version }) });
    assert.equal(other.status, 200);
    await dispatch(p, { type: 'answerCandidate', id: 'search-9.36.2.6.(1)', answer: 'not-sure' });
    await looked(p);
    await settle(p);
    await p.evaluate(() => new Promise(r => setTimeout(r, 700)));     // the automatic save runs and is refused
    const conflicted = await status(p);
    assert.equal(conflicted.save, 'failed');
    assert.match(conflicted.note, /changed somewhere else/);
    assert.deepEqual((await remote(b)).selected_articles, [pick('search-9.10.9.16.(1)', '9.10.9.16.(1)', 'no')], 'the newer selection is not overwritten');
    assert.ok((await cards(p)).some(x => x[0] === 'search-9.36.2.6.(1)' && x[2] === 'not-sure'), 'the local answer stays');
    await save(p);                                                     // "Try saving again" reads the case first
    assert.equal((await status(p)).save, 'saved');
    assert.deepEqual((await remote(b)).selected_articles.map(x => x.id), ['search-9.36.2.6.(1)', 'search-9.27.3.4.(2)']);
  });

  await scenario('a deleted application is reported gone and never recreated', async open => {
    const p = await open();
    const { a } = await twoApplications(p);
    assert.equal(await openCase(p, a), null);
    await looked(p);
    assert.equal((await fetch(base + '/cases/' + a, { method: 'DELETE' })).status, 204);
    const sent = (await p.evaluate(() => window.requests)).length;
    await dispatch(p, { type: 'addCandidate', candidate: card('9.36.2.6.(1)') });
    await save(p);
    assert.equal((await status(p)).save, 'gone');
    assert.ok(!(await p.evaluate(() => window.requests)).slice(sent).some(r => r === 'POST /cases'), 'no replacement case');
    assert.ok((await cards(p)).some(x => x[1] === '9.36.2.6.(1)'), 'the answers stay here');
    const fresh = await open();
    assert.match(await openCase(fresh, a), /deleted or has expired/);
  });

  await scenario('owned accounts: a read-only application refuses the write, and another account cannot read or write it', async open => {
    const p = await open();
    assert.ok([200, 201].includes(await account(p, 'selection-owner@example.test', 'SYNTHETIC Owner')));
    await begin(p);
    await dispatch(p, { type: 'setDetail', field: 'owner', value: 'SYNTHETIC owned', section: 'A' });
    await dispatch(p, { type: 'addCandidate', candidate: card('9.25.2.2.(1)') });
    const id = await save(p);
    assert.ok(id);
    const owned = await p.evaluate(async ({ base, id }) => (await fetch(base + '/cases/' + id, { credentials: 'include' })).json(), { base, id });
    assert.ok(owned.owner_id, 'the case belongs to the signed-in synthetic owner');
    assert.deepEqual(owned.selected_articles, [pick('search-9.25.2.2.(1)', '9.25.2.2.(1)')]);
    // Read-only: the owned store marks it submitted (as the submit route would after a complete check).
    const sql = new DatabaseSync(db);
    const row = sql.prepare('SELECT json FROM cases WHERE id=?').get(id);
    sql.prepare('UPDATE cases SET json=? WHERE id=?').run(JSON.stringify({ ...JSON.parse(row.json), status: 'submitted' }), id);
    sql.close();
    await dispatch(p, { type: 'answerCandidate', id: 'search-9.25.2.2.(1)', answer: 'no' });
    await save(p);
    assert.equal((await status(p)).save, 'failed');
    const after = await p.evaluate(async ({ base, id }) => (await fetch(base + '/cases/' + id, { credentials: 'include' })).json(), { base, id });
    assert.deepEqual(after.selected_articles, [pick('search-9.25.2.2.(1)', '9.25.2.2.(1)')], 'read-only: nothing changed');
    // Another account: the application is inaccessible and nothing of it leaks.
    await p.evaluate(async base => { await fetch(base + '/auth/logout', { method: 'POST', credentials: 'include' }); }, base);
    assert.ok([200, 201].includes(await account(p, 'selection-other@example.test', 'SYNTHETIC Other')));
    const other = await open();
    await other.context().addCookies(await p.context().cookies());
    assert.match(await openCase(other, id), /deleted or has expired/);
    assert.deepEqual(await cards(other), []);
    const sent = (await p.evaluate(() => window.requests)).length;
    await save(p);
    assert.equal((await status(p)).save, 'gone', 'revoked access is terminal');
    assert.ok(!(await p.evaluate(() => window.requests)).slice(sent).some(r => r === 'POST /cases'), 'never recreated');
  });
} finally {
  await browser.close();
}
console.log(`${passed} selection scenarios passed, ${failed} failed`);
process.exitCode = failed ? 1 : 0;
