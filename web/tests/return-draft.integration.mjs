// Mounted ReturnDialog -> real accounts client -> delayed HTTP responses; sends use disposable SQLite.
// /assist is intercepted before the engine, so this suite never invokes a provider.
import assert from 'node:assert/strict';
import { createHash, randomUUID } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import { pathToFileURL } from 'node:url';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE ? pathToFileURL(process.env.PLAYWRIGHT_MODULE).href : 'playwright-core');
const web = process.env.SYNC_WEB_BASE, base = process.env.SYNC_TEST_BASE;
for (const url of [web, base]) assert.match(url ?? '', /^http:\/\/127\.0\.0\.1:\d+$/);
assert.ok(process.env.SYNC_TEST_DB, 'A disposable SQLite store is required');
const db = new DatabaseSync(process.env.SYNC_TEST_DB);
db.exec('PRAGMA busy_timeout = 5000');
const now = new Date().toISOString();
const actors = Object.fromEntries(['owner', 'officer', 'replacement'].map(name => {
  const user = { id: `j07-draft-${randomUUID()}`, email: `${randomUUID()}@example.test`, name: `SYNTHETIC ${name}`,
    role: name === 'owner' ? 'applicant' : 'reviewer', authority: name === 'owner' ? null : 'edmonton',
    applicant_type: name === 'owner' ? 'contractor' : null, onboarded: true, created_at: now, notifications_seen_at: null };
  const token = randomUUID().replaceAll('-', '').padEnd(43, '_');
  db.prepare('INSERT INTO account_users(id,email,data) VALUES (?,?,?)').run(user.id, user.email, JSON.stringify({ user, password: null }));
  db.prepare('INSERT INTO account_sessions(digest,user_id,expires_at) VALUES (?,?,?)')
    .run(createHash('sha256').update(token).digest('hex'), user.id, Date.now() / 1000 + 3600);
  return [name, { user, token }];
}));

async function api(actor, path, body, expected = 200) {
  const response = await fetch(base + path, { method: body === undefined ? 'GET' : 'POST',
    headers: { Cookie: `batatis_session=${actors[actor].token}`, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
    body: body === undefined ? undefined : JSON.stringify(body) });
  const data = response.status === 204 ? null : await response.json();
  assert.equal(response.status, expected, JSON.stringify(data));
  return data;
}
async function fixture() {
  const created = await api('owner', '/cases', { title: 'SYNTHETIC delayed return draft', authority: 'edmonton', jurisdiction: { id: 'edmonton', name: 'Edmonton' } }, 201);
  const row = db.prepare('SELECT json,version FROM cases WHERE id=?').get(created.id);
  const c = { ...JSON.parse(row.json), status: 'submitted', submitted_at: now };
  db.prepare('UPDATE cases SET json=?,version=? WHERE id=?').run(JSON.stringify(c), row.version + 1, c.id);
  await api('officer', `/review/${c.id}/claim`, {});
  const gaps = (await api('owner', `/cases/${c.id}/gaps`)).items.filter(g => ['legal_description', 'owner_name'].includes(g.field));
  assert.equal(gaps.length, 2);
  return { id: c.id, gaps };
}

const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
let passed = 0, failed = 0;
async function scenario(name, run) {
  const scene = await fixture();
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' });
  await context.addCookies([{ name: 'batatis_session', value: actors.officer.token, url: base, httpOnly: true, sameSite: 'Lax' }]);
  const page = await context.newPage();
  page.setDefaultTimeout(5000);
  const errors = [], canceled = [], requests = [], gates = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('requestfailed', req => { if (new URL(req.url()).pathname === '/api/assist') canceled.push(req.failure()?.errorText); });
  await page.addInitScript(() => {
    const original = window.fetch.bind(window);
    window.assistSettled = 0;
    window.fetch = async (...args) => {
      const assist = String(args[0]).endsWith('/assist');
      try { return await original(...args); }
      finally { if (assist) window.assistSettled++; }
    };
  });
  function delay(status = 200, answer = 'SYNTHETIC delayed assistant draft.') {
    let entered, release, finished;
    const ready = new Promise(resolve => { entered = resolve; });
    const wait = new Promise(resolve => { release = resolve; });
    const done = new Promise(resolve => { finished = resolve; });
    const gate = { status, answer, entered, wait, finished, release, used: false };
    gates.push(gate);
    return { ready, release, done };
  }
  await page.route('**/*', async route => {
    const req = route.request(), url = new URL(req.url());
    if (url.origin !== web) return route.abort();
    if (!url.pathname.startsWith('/api/')) return route.continue();
    const path = url.pathname.replace(/^\/api/, '');
    requests.push({ path, body: req.postData() ? req.postDataJSON() : null });
    if (path === '/assist') {
      const gate = gates.find(g => !g.used);
      assert.ok(gate, 'Every assistant response must be an explicitly delayed synthetic fixture');
      gate.used = true; gate.entered(); await gate.wait;
      try { await route.fulfill({ status: gate.status, json: gate.status === 200 ? { answer: gate.answer } : { detail: 'SYNTHETIC assistant unavailable' } }); }
      catch (e) { if (!req.failure()) throw e; }
      finally { gate.finished(); }
      return;
    }
    await route.fulfill({ response: await route.fetch({ url: base + path }) });
  });
  const dialog = page.getByRole('dialog', { name: 'Return with a message', exact: true });
  const message = dialog.getByRole('textbox');
  const tick = gap => dialog.getByLabel(gap.message, { exact: true });
  async function draft(gate) {
    await dialog.getByRole('button', { name: 'Draft from ticked items', exact: true }).click();
    await gate.ready;
    assert.equal(await message.isEnabled(), true, 'the officer must remain free to edit while drafting');
  }
  async function settle(gate, total = 1) {
    gate.release(); await gate.done;
    await page.waitForFunction(n => window.assistSettled >= n, total);
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  }
  try {
    await page.goto(web + '/tests/return-draft.html');
    await page.waitForFunction(() => !!window.returnDraft);
    await page.evaluate(({ user, scene }) => {
      window.returnDraft.setAccountState({ phase: 'signed-in', user });
      window.returnDraft.setProps({ open: true, caseId: scene.id, applicant: 'SYNTHETIC applicant', gaps: scene.gaps });
    }, { user: actors.officer.user, scene });
    await dialog.waitFor();
    await tick(scene.gaps[0]).check();
    await run({ page, context, scene, dialog, message, tick, draft, settle, delay, canceled, requests });
    assert.deepEqual(errors, []);
    assert.equal(requests.some(r => /\/(identify|intake|completeness)(\/|$)/.test(r.path)), false);
    passed++; console.log('PASS', name);
  } catch (e) { failed++; console.error('FAIL', name, e.stack); }
  finally {
    for (const gate of gates) gate.release();
    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await context.close();
  }
}

const custom = 'SYNTHETIC please correct the legal description and attach revision B of the PDF.';
try {
  for (const status of [200, 503]) {
    await scenario(`delayed HTTP ${status} preserves intervening typing and saves that exact officer note`, async ({ scene, dialog, message, draft, settle, delay, canceled }) => {
      const gate = delay(status); await draft(gate);
      await message.fill(custom);
      await settle(gate);
      assert.equal(await message.inputValue(), custom, 'a delayed draft must never overwrite the officer’s edit');
      assert.equal(canceled.length, 1, 'typing must abort the obsolete authenticated request');
      await dialog.getByRole('button', { name: 'Send and return', exact: true }).click();
      await dialog.waitFor({ state: 'hidden' });
      const saved = await api('owner', `/cases/${scene.id}`);
      assert.equal(saved.decision.message.split('\n\n').at(-1), custom);
      assert.deepEqual(saved.decision.items, [{ gap_id: scene.gaps[0].id, field: scene.gaps[0].field, note: scene.gaps[0].message }]);
    });
    await scenario(`delayed HTTP ${status} publishes normally when the draft still matches the opening and selection`, async ({ message, draft, settle, delay }) => {
      const gate = delay(status); await draft(gate); await settle(gate);
      assert.ok((await message.inputValue()).includes(status === 200 ? 'SYNTHETIC delayed assistant draft.' : 'requested items are listed below'));
    });
  }
  await scenario('selection edits discard the obsolete draft and a new request can publish independently', async ({ dialog, message, tick, scene, draft, settle, delay, canceled, requests }) => {
    await message.fill(custom);
    const stale = delay(); await draft(stale);
    await tick(scene.gaps[0]).uncheck(); await tick(scene.gaps[1]).check();
    const fresh = delay(200, 'SYNTHETIC fresh selection draft.'); await draft(fresh);
    await settle(stale);
    assert.equal(await message.inputValue(), custom);
    assert.equal(await dialog.getByRole('button', { name: 'Drafting…', exact: true }).isDisabled(), true, 'old finally must not clear a newer request’s busy state');
    await settle(fresh, 2);
    assert.equal(await message.inputValue(), 'SYNTHETIC fresh selection draft.');
    assert.equal(canceled.length, 1);
    assert.ok(requests.filter(r => r.path === '/assist').at(-1).body.question.includes(scene.gaps[1].message));
  });
  await scenario('closing and reopening cancels the old opening without erasing the officer note', async ({ page, dialog, message, draft, settle, delay, canceled }) => {
    await message.fill(custom);
    const gate = delay(); await draft(gate);
    await page.evaluate(() => { window.dialogClosed = new Promise(resolve => document.querySelector('dialog').addEventListener('close', () => resolve(), { once: true })); });
    await dialog.getByRole('button', { name: 'Cancel', exact: true }).click(); await dialog.waitFor({ state: 'hidden' });
    await page.evaluate(() => window.dialogClosed);
    await page.evaluate(() => window.returnDraft.setProps(p => ({ ...p, open: true })));
    await dialog.waitFor(); await settle(gate);
    assert.equal(await message.inputValue(), custom);
    assert.equal(canceled.length, 1);
  });
  await scenario('a case switch on the same mounted dialog cannot publish the previous case’s draft', async ({ page, message, draft, settle, delay, canceled }) => {
    const gate = delay(503); await draft(gate);
    const other = await fixture();
    await page.evaluate(scene => window.returnDraft.setProps({ open: true, caseId: scene.id, applicant: 'SYNTHETIC other applicant', gaps: scene.gaps }), other);
    await message.fill('SYNTHETIC note for the other application.');
    await settle(gate);
    assert.equal(await message.inputValue(), 'SYNTHETIC note for the other application.');
    assert.equal(canceled.length, 1);
  });
  for (const sameUser of [false, true]) {
    await scenario(`${sameUser ? 'a new session for the same officer' : 'an account replacement'} cancels the in-flight draft`, async ({ page, message, draft, settle, delay, canceled }) => {
      const gate = delay(); await draft(gate);
      await page.evaluate(user => window.returnDraft.setAccountState({ phase: 'signed-in', user }), sameUser ? { ...actors.officer.user } : actors.replacement.user);
      await message.fill('SYNTHETIC note in the replacement session.');
      await settle(gate);
      assert.equal(await message.inputValue(), 'SYNTHETIC note in the replacement session.');
      assert.equal(canceled.length, 1);
    });
  }
  await scenario('sending cancels pending drafting and saves the officer’s current text', async ({ scene, page, dialog, message, draft, settle, delay, canceled }) => {
    await message.fill(custom);
    const gate = delay(); await draft(gate);
    await dialog.getByRole('button', { name: 'Send and return', exact: true }).click();
    await dialog.waitFor({ state: 'hidden' }); await settle(gate);
    assert.equal((await api('owner', `/cases/${scene.id}`)).decision.message.split('\n\n').at(-1), custom);
    await page.evaluate(() => window.returnDraft.setProps(p => ({ ...p, open: true })));
    await dialog.waitFor();
    assert.equal(await message.inputValue(), '');
    assert.equal(canceled.length, 1);
  });
  await scenario('equivalent background props retain the open dialog, typed note, and current request', async ({ page, scene, dialog, message, draft, settle, delay, canceled }) => {
    await message.fill(custom);
    await page.evaluate(scene => window.returnDraft.setProps(p => ({ ...p, gaps: structuredClone(scene.gaps) })), scene);
    assert.equal(await message.inputValue(), custom);
    const gate = delay(); await draft(gate);
    await page.evaluate(scene => window.returnDraft.setProps(p => ({ ...p, gaps: structuredClone(scene.gaps) })), scene);
    await settle(gate);
    assert.equal(await message.inputValue(), 'SYNTHETIC delayed assistant draft.');
    assert.equal(canceled.length, 0);
    assert.equal(await dialog.isVisible(), true);
  });
} finally { await browser.close(); db.close(); }
console.log(`J07 delayed ReturnDialog: ${passed} passed, ${failed} failed`);
process.exitCode = failed ? 1 : 0;
