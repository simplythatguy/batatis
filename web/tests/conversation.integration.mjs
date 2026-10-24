// Real applicant Shell -> conversation/receipt client -> HTTP -> disposable SQLite.
// No screenshots or whole-journey claim; the integrating parent owns visual capture.
import assert from 'node:assert/strict';
import { createHash, randomUUID } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import { pathToFileURL } from 'node:url';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE ? pathToFileURL(process.env.PLAYWRIGHT_MODULE).href : 'playwright-core');
const web = process.env.SYNC_WEB_BASE, base = process.env.SYNC_TEST_BASE;
for (const url of [web, base]) assert.match(url ?? '', /^http:\/\/127\.0\.0\.1:\d+$/);
assert.ok(process.env.SYNC_TEST_DB, 'A disposable SQLite store is required');
const db = new DatabaseSync(process.env.SYNC_TEST_DB);
db.exec('PRAGMA busy_timeout = 5000'); // Let an engine receipt finish before editing the next fixture.
const now = new Date().toISOString();
const actors = Object.fromEntries(['owner', 'officer', 'replacement'].map(name => {
  const user = { id: `j06-${randomUUID()}`, email: `${randomUUID()}@example.test`, name: `SYNTHETIC ${name}`,
    role: name === 'officer' ? 'reviewer' : 'applicant', authority: name === 'officer' ? 'edmonton' : null,
    applicant_type: name === 'officer' ? null : 'contractor', onboarded: true, created_at: now, notifications_seen_at: null };
  const token = randomUUID().replaceAll('-', '').padEnd(43, '_');
  db.prepare('INSERT INTO account_users(id,email,data) VALUES (?,?,?)').run(user.id, user.email, JSON.stringify({ user, password: null }));
  db.prepare('INSERT INTO account_sessions(digest,user_id,expires_at) VALUES (?,?,?)')
    .run(createHash('sha256').update(token).digest('hex'), user.id, Date.now() / 1000 + 3600);
  return [name, { user, token }];
}));
actors.ownerAgain = { user: { ...actors.owner.user }, token: randomUUID().replaceAll('-', '').padEnd(43, '_') };
db.prepare('INSERT INTO account_sessions(digest,user_id,expires_at) VALUES (?,?,?)')
  .run(createHash('sha256').update(actors.ownerAgain.token).digest('hex'), actors.owner.user.id, Date.now() / 1000 + 3600);

async function api(actor, path, body, expected = 200) {
  const response = await fetch(base + path, { method: body === undefined ? 'GET' : 'POST',
    headers: { Cookie: `batatis_session=${actors[actor].token}`, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
    body: body === undefined ? undefined : JSON.stringify(body) });
  const data = response.status === 204 ? null : await response.json();
  assert.equal(response.status, expected, JSON.stringify(data));
  return data;
}

function editFixture(id, edit) {
  const row = db.prepare('SELECT json,version FROM cases WHERE id=?').get(id);
  const c = JSON.parse(row.json);
  edit(c);
  db.prepare('UPDATE cases SET json=?,version=? WHERE id=?').run(JSON.stringify(c), row.version + 1, id);
}

async function fixture(status) {
  const c = await api('owner', '/cases', { title: `SYNTHETIC J06 ${status}`, authority: 'edmonton', jurisdiction: { id: 'edmonton', name: 'Edmonton' } }, 201);
  editFixture(c.id, c => { c.status = 'submitted'; c.submitted_at = now; });
  await api('officer', `/review/${c.id}/claim`, {});
  const returned = await api('officer', `/review/${c.id}/decision`, { outcome: 'return',
    message: 'SYNTHETIC original correction: please correct the legal description.',
    items: [{ field: 'legal_description', note: 'SYNTHETIC correct the legal description.' }] });
  const originalAt = new Date(Date.now() - 3600_000).toISOString();
  editFixture(c.id, c => {
    c.decision.at = originalAt;
    c.messages.find(m => m.kind === 'decision').created_at = originalAt;
    c.messages.push({ id: `historical-${randomUUID()}`, author: { id: actors.owner.user.id, name: actors.owner.user.name, role: 'applicant' },
      body: 'SYNTHETIC readable historical applicant reply.', items: [], kind: 'message',
      created_at: new Date(Date.now() - 1800_000).toISOString(), read_by: [actors.owner.user.id] });
    if (status !== 'returned') { c.status = status; c.decision = null; }
    if (status === 'accepted') {
      c.decision = { ...returned.decision, outcome: 'accept', at: now, items: [], message: 'Accepted as administratively complete. SYNTHETIC final decision note.' };
      c.messages.push({ id: `accepted-${randomUUID()}`, author: { id: actors.officer.user.id, name: actors.officer.user.name, role: 'reviewer' },
        body: c.decision.message, items: [], kind: 'decision', created_at: now, read_by: [actors.officer.user.id] });
    }
  });
  const followup = await api('officer', `/cases/${c.id}/messages`, { body: 'SYNTHETIC follow-up: keep the owner unchanged. <script>window.j06Injected=true</script>' }, 201);
  return { id: c.id, originalAt, followup, decisionId: returned.messages.find(m => m.kind === 'decision').id };
}

const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
let passed = 0, failed = 0;
async function scenario(name, status, work, options = {}) {
  if (process.env.CONVERSATION_FILTER && !name.includes(process.env.CONVERSATION_FILTER)) return;
  const scene = await fixture(status);
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' });
  await context.addCookies([{ name: 'batatis_session', value: actors[options.actor ?? 'owner'].token, url: base, httpOnly: true, sameSite: 'Lax' }]);
  const page = await context.newPage();
  page.setDefaultTimeout(10000);
  const errors = [], requests = [], gates = [], canceled = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('requestfailed', req => canceled.push(new URL(req.url()).pathname.replace(/^\/api/, '')));
  function hold(path, method) {
    let entered, release, finished;
    const ready = new Promise(resolve => { entered = resolve; });
    const wait = new Promise(resolve => { release = resolve; });
    const done = new Promise(resolve => { finished = resolve; });
    const gate = { path, method, used: false, entered, wait, finished, release };
    gates.push(gate);
    return { ready, release, done };
  }
  await page.route('**/*', async route => {
    const req = route.request(), url = new URL(req.url());
    if (url.origin !== web) return route.abort();
    if (!url.pathname.startsWith('/api/')) return route.continue();
    const path = url.pathname.replace(/^\/api/, '') + url.search;
    requests.push({ path, method: req.method(), body: req.postData() ? req.postDataJSON() : null });
    const gate = gates.find(g => !g.used && g.path === path && g.method === req.method());
    if (gate) gate.used = true;
    try {
      const response = await route.fetch({ url: base + path });
      if (gate) { gate.entered(); await gate.wait; }
      await route.fulfill({ response });
    } catch (e) {
      if (!req.failure()) throw e;
    } finally { gate?.finished(); }
  });
  try {
    await page.goto(web + '/tests/check.html' + (options.actor === 'officer' ? `#/review/${scene.id}` : ''));
    await page.waitForFunction(() => !!window.caseStore);
    await page.locator('.cf-app').waitFor(); // Session restore/reset must finish before opening.
    if (options.actor === 'officer') {
      await page.getByRole('textbox', { name: 'Message to the applicant' }).waitFor();
    } else {
      assert.equal(await page.evaluate(id => window.caseStore.openCase(id, 'contractor'), scene.id), null);
      await page.evaluate(() => { location.hash = '#/application'; });
      await page.getByRole('heading', { name: 'Messages and application history' }).waitFor({ state: 'attached' });
    }
    await work({ page, context, scene, requests, hold, canceled });
    assert.deepEqual(errors, []);
    if (options.history !== false) {
      const instants = await page.locator('.cf-conversation .ac-thread time').evaluateAll(nodes => nodes.map(node => Date.parse(node.dateTime)));
      const savedThread = await api('owner', `/cases/${scene.id}/messages`);
      const inBanner = status === 'returned' ? 1 : 0;
      assert.equal(instants.length, savedThread.messages.length - inBanner, 'History retains every message except the current decision already displayed in full');
      assert.deepEqual(instants, [...instants].sort((a, b) => a - b), 'displayed history is chronological');
    }
    assert.equal(await page.evaluate(() => window.j06Injected), undefined, 'message bodies render as plain text');
    assert.equal(requests.some(r => r.method === 'POST' && /\/(identify|intake|completeness)(\/|$)/.test(r.path)), false);
    passed++; console.log('PASS', name);
  } catch (e) { failed++; console.error('FAIL', name, e.stack); }
  finally {
    for (const gate of gates) gate.release();
    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await context.close();
  }
}

async function replaceAccount(page, context, name = 'replacement') {
  await context.addCookies([{ name: 'batatis_session', value: actors[name].token, url: base, httpOnly: true, sameSite: 'Lax' }]);
  // Keep the same case/row mounted deliberately: cancellation cannot rely on navigation alone.
  await page.evaluate(async user => {
    const account = await import('/src/calm/account.ts');
    account.setAccountState({ phase: 'signed-in', user, applications: account.getAccountState().applications });
  }, actors[name].user);
  await page.evaluate(() => new Promise(requestAnimationFrame));
}

async function assertReplacementSession(page, context, name = 'replacement') {
  await page.waitForTimeout(150);
  const cookie = (await context.cookies(base)).find(c => c.name === 'batatis_session');
  assert.equal(cookie?.value, actors[name].token, 'a delayed authenticated response restored the old session cookie');
  const me = await context.request.get(base + '/auth/me');
  assert.equal(me.status(), 200);
  assert.equal((await me.json()).user.id, actors[name].user.id, 'the actual server must see the replacement account');
  assert.equal(await page.evaluate(async () => (await import('/src/calm/account.ts')).getAccountState().user.id), actors[name].user.id);
}

try {
  await scenario('follow-up preserves original return body, timestamp/items; collapsed history only reads the visible decision', 'returned', async ({ page, scene, requests }) => {
    const banner = page.locator('.cf-returned');
    await banner.getByText(/SYNTHETIC original correction/).waitFor();
    assert.equal(await banner.locator('time').getAttribute('datetime'), scene.originalAt);
    assert.equal(await banner.getByText('SYNTHETIC correct the legal description.', { exact: true }).count(), 1);
    assert.equal(await banner.getByText(/keep the owner unchanged/).count(), 0);
    assert.equal(await page.getByRole('button', { name: 'Reply', exact: true }).count(), 0);
    assert.equal(await page.locator('.cf-correspondence textarea').count(), 0);
    await page.waitForFunction(() => document.querySelector('.cf-conversation summary')?.textContent?.includes('1 unread'));
    let stored = await api('owner', `/cases/${scene.id}/messages`);
    assert.equal(stored.messages.find(m => m.id === scene.followup.id).read_by_me, false);
    const reads = requests.filter(r => r.path.endsWith('/messages/read'));
    assert.ok(reads.length > 0);
    assert.ok(reads.every(r => r.body.message_ids.every(id => id === scene.decisionId)), 'hidden history must not be acknowledged');
    await page.locator('.cf-conversation summary').click();
    await page.locator('.ac-thread').getByText('SYNTHETIC readable historical applicant reply.', { exact: true }).waitFor();
    await page.locator('.ac-thread').getByText(/keep the owner unchanged/).waitFor();
    await page.waitForFunction(() => !document.querySelector('.cf-conversation summary')?.textContent?.includes('unread'));
    stored = await api('owner', `/cases/${scene.id}/messages`);
    assert.ok(stored.messages.every(m => m.read_by_me));
    const original = stored.decision;
    const before = await api('owner', `/cases/${scene.id}`);
    await page.evaluate(() => window.caseStore.dispatch({ type: 'setDetail', field: 'legalDescription', value: 'SYNTHETIC corrected lot 2', section: 'B' }));
    assert.equal(await page.evaluate(() => window.caseStore.saveDraft()), scene.id, 'displayed receipts must leave actual save acknowledgement writable');
    assert.equal((await api('owner', `/cases/${scene.id}`)).version, before.version + 1);
    assert.deepEqual((await api('owner', `/cases/${scene.id}/messages`)).decision, original);
    await page.reload();
    await page.waitForFunction(() => !!window.caseStore);
    await page.locator('.cf-app').waitFor();
    await page.waitForFunction(id => window.caseStore.engineId === id, scene.id); // Shell restores this tab; do not race it with a second open.
    await banner.getByText(/SYNTHETIC original correction/).waitFor();
    assert.equal(await banner.locator('time').getAttribute('datetime'), scene.originalAt);
    await page.locator('.cf-conversation summary').click();
    await page.locator('.ac-thread').getByText('SYNTHETIC readable historical applicant reply.', { exact: true }).waitFor();
  });

  for (const status of ['submitted', 'in_review', 'accepted']) {
    await scenario(`${status} keeps all notices and historical replies readable after reload`, status, async ({ page, scene }) => {
      await page.locator('.ac-thread').getByText(/keep the owner unchanged/).waitFor();
      await page.locator('.ac-thread').getByText('SYNTHETIC readable historical applicant reply.', { exact: true }).waitFor();
      assert.equal(await page.locator('.cf-returned').count(), 0);
      if (status === 'accepted') await page.locator('.ac-thread').getByText('Accepted as administratively complete. SYNTHETIC final decision note.', { exact: true }).waitFor();
      const before = await api('owner', `/cases/${scene.id}`);
      await api('owner', `/cases/${scene.id}/messages`, { body: 'SYNTHETIC unauthorized new reply.' }, 403);
      const after = await api('owner', `/cases/${scene.id}`);
      assert.deepEqual(after.decision, before.decision);
      assert.deepEqual(after.messages.map(m => m.body), before.messages.map(m => m.body));
      await page.reload();
      await page.waitForFunction(() => !!window.caseStore);
      await page.locator('.cf-app').waitFor();
      await page.waitForFunction(id => window.caseStore.engineId === id, scene.id);
      await page.locator('.ac-thread').getByText(/keep the owner unchanged/).waitFor();
      if (status === 'accepted') await page.locator('.ac-thread').getByText(/SYNTHETIC final decision note/).waitFor();
    });
  }

  for (const newerNotice of [false, true]) {
    await scenario(`a read thread snapshot cannot cancel its pending receipt${newerNotice ? ' or clear a newer unseen notice' : ' and strand the application unread count'}`, 'returned', async ({ page, scene, requests, hold, canceled }) => {
      await page.waitForFunction(() => document.querySelector('.cf-conversation summary')?.textContent?.includes('1 unread'));
      await page.waitForLoadState('networkidle');
      await page.evaluate(async () => { window.readAccount = (await import('/src/calm/account.ts')).getAccountState; });
      const count = () => page.evaluate(id => window.readAccount().applications.find(a => a.id === id)?.unread_messages, scene.id);
      assert.equal(await count(), 1);
      const version = (await api('owner', `/cases/${scene.id}`)).version;
      const path = `/cases/${scene.id}/messages/read`, delayed = hold(path, 'POST');
      const requestStart = requests.length, cancellationStart = canceled.length;
      await page.locator('.cf-conversation summary').click();
      await delayed.ready; // The real server has committed, but the browser has no 204 yet.
      assert.ok((await api('owner', `/cases/${scene.id}/messages`)).messages.every(m => m.read_by_me));
      await page.getByRole('button', { name: 'Refresh messages', exact: true }).click();
      await page.waitForFunction(() => !document.querySelector('.cf-conversation summary')?.textContent?.includes('unread'));
      await page.evaluate(() => new Promise(requestAnimationFrame));
      console.log('J06 receipt/snapshot observation', JSON.stringify({
        serverUnread: 0, displayedUnread: 0, listUnreadBefore204: await count(),
        receiptAbortedBefore204: canceled.slice(cancellationStart).includes(path),
        displayedReceiptRequests: requests.slice(requestStart).filter(r => r.path === path).map(r => r.body.message_ids),
      }));
      let later;
      if (newerNotice) {
        await page.locator('.cf-conversation summary').click();
        later = await api('officer', `/cases/${scene.id}/messages`, { body: 'SYNTHETIC unseen notice after the displayed snapshot.' }, 201);
      }
      delayed.release(); await delayed.done;
      await page.waitForFunction(({ id, expected }) => window.readAccount().applications.find(a => a.id === id)?.unread_messages === expected,
        { id: scene.id, expected: newerNotice ? 1 : 0 }, { timeout: 3500 });
      assert.equal(canceled.slice(cancellationStart).includes(path), false, 'same-case snapshot changes must not cancel the receipt reconciliation');
      assert.equal(requests.slice(requestStart).filter(r => r.path === path).length, 1, 'the displayed receipt must not be resent');
      assert.equal((await api('owner', `/cases/${scene.id}`)).version, version, 'receipt and thread reads must not advance content CAS');
      if (later) assert.equal((await api('owner', `/cases/${scene.id}/messages`)).messages.find(m => m.id === later.id).read_by_me, false);
    }, { history: false });
  }

  await scenario('a delayed applicant receipt is canceled on account replacement without restoring its old session cookie', 'returned', async ({ page, context, scene, hold, canceled }) => {
    await page.waitForFunction(() => document.querySelector('.cf-conversation summary')?.textContent?.includes('1 unread'));
    await page.waitForLoadState('networkidle'); // Drain unrelated startup reads; J05 owns their cancellation.
    const path = `/cases/${scene.id}/messages/read`, delayed = hold(path, 'POST');
    await page.locator('.cf-conversation summary').click();
    await delayed.ready;
    await replaceAccount(page, context);
    delayed.release(); await delayed.done;
    await assertReplacementSession(page, context);
    assert.ok(canceled.includes(path), 'ignore-publication alone is insufficient: the receipt fetch must abort');
    assert.equal(await page.locator('.cf-returned').count(), 0, 'old return content leaked into the replacement account');
    const denied = await context.request.get(base + `/cases/${scene.id}/messages`);
    assert.equal(denied.status(), 404, 'replacement account must not gain access to the old thread');
  }, { history: false });

  await scenario('a delayed applicant thread load is canceled when account identity changes on the same case', 'returned', async ({ page, context, scene, hold, canceled }) => {
    await page.locator('.cf-returned').waitFor();
    await page.locator('.cf-conversation summary').click();
    await page.waitForFunction(() => !document.querySelector('.cf-conversation summary')?.textContent?.includes('unread'));
    await page.waitForLoadState('networkidle');
    const path = `/cases/${scene.id}/messages`, delayed = hold(path, 'GET');
    await page.getByRole('button', { name: 'Refresh messages', exact: true }).click();
    await delayed.ready;
    await replaceAccount(page, context);
    delayed.release(); await delayed.done;
    await assertReplacementSession(page, context);
    assert.ok(canceled.includes(path), 'thread load fetch must abort on account replacement');
    assert.equal(await page.locator('.cf-returned').count(), 0);
  }, { history: false });

  await scenario('a delayed officer post is canceled on account replacement and cannot renew the officer cookie', 'returned', async ({ page, context, scene, hold, canceled }) => {
    await page.waitForLoadState('networkidle');
    const path = `/cases/${scene.id}/messages`, delayed = hold(path, 'POST');
    await page.getByRole('textbox', { name: 'Message to the applicant' }).fill('SYNTHETIC delayed officer notice.');
    await page.getByRole('button', { name: 'Send', exact: true }).click();
    await delayed.ready;
    await replaceAccount(page, context);
    delayed.release(); await delayed.done;
    await assertReplacementSession(page, context);
    assert.ok(canceled.includes(path), 'officer post fetch must abort on account replacement');
    // Canceling a response is not a rollback of an already committed server notice.
    const stored = await api('owner', `/cases/${scene.id}/messages`);
    assert.equal(stored.messages.filter(m => m.body === 'SYNTHETIC delayed officer notice.').length, 1);
    assert.equal(await page.getByRole('textbox', { name: 'Message to the applicant' }).count(), 0);
  }, { actor: 'officer', history: false });

  await scenario('a delayed receipt cannot overwrite a newer login cookie for the same user', 'returned', async ({ page, context, scene, hold, canceled }) => {
    await page.waitForFunction(() => document.querySelector('.cf-conversation summary')?.textContent?.includes('1 unread'));
    await page.waitForLoadState('networkidle');
    const path = `/cases/${scene.id}/messages/read`, delayed = hold(path, 'POST');
    await page.locator('.cf-conversation summary').click(); await delayed.ready;
    await replaceAccount(page, context, 'ownerAgain');
    delayed.release(); await delayed.done;
    await assertReplacementSession(page, context, 'ownerAgain');
    assert.ok(canceled.includes(path), 'a new session with the same user id must still cancel the old receipt');
  }, { history: false });

  await scenario('switching applications aborts a delayed thread load for the previous case', 'returned', async ({ page, context, scene, hold, canceled }) => {
    await page.locator('.cf-returned').waitFor();
    await page.locator('.cf-conversation summary').click();
    await page.waitForFunction(() => !document.querySelector('.cf-conversation summary')?.textContent?.includes('unread'));
    await page.waitForLoadState('networkidle');
    const other = await fixture('submitted');
    const path = `/cases/${scene.id}/messages`, delayed = hold(path, 'GET');
    await page.getByRole('button', { name: 'Refresh messages', exact: true }).click(); await delayed.ready;
    assert.equal(await page.evaluate(id => window.caseStore.openCase(id, 'contractor'), other.id), null);
    await page.waitForFunction(id => window.caseStore.engineId === id, other.id);
    delayed.release(); await delayed.done;
    assert.ok(canceled.includes(path), 'previous-case thread fetch must abort');
    assert.equal((await context.cookies(base)).find(c => c.name === 'batatis_session')?.value, actors.owner.token);
    await page.locator('.cf-conversation .ac-thread').getByText(/keep the owner unchanged/).waitFor();
    assert.equal(await page.locator('.cf-returned').count(), 0);
  }, { history: false });

  await scenario('leaving the applicant stages aborts an in-flight displayed receipt', 'returned', async ({ page, scene, hold, canceled }) => {
    await page.waitForFunction(() => document.querySelector('.cf-conversation summary')?.textContent?.includes('1 unread'));
    await page.waitForLoadState('networkidle');
    const path = `/cases/${scene.id}/messages/read`, delayed = hold(path, 'POST');
    await page.locator('.cf-conversation summary').click(); await delayed.ready;
    await page.evaluate(() => { location.hash = '#/code'; });
    await page.waitForFunction(() => !document.querySelector('.cf-correspondence'));
    delayed.release(); await delayed.done;
    assert.ok(canceled.includes(path), 'unmounted conversation must abort its receipt');
  }, { history: false });
} finally {
  await browser.close();
  db.close();
}
console.log(JSON.stringify({ passed, failed }));
process.exitCode = failed ? 1 : 0;
