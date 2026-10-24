// Mounted real sheets + same-case inventory/download HTTP. All material is explicitly synthetic.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE ? pathToFileURL(process.env.PLAYWRIGHT_MODULE).href : 'playwright-core');
const web = process.env.SYNC_WEB_BASE, base = process.env.SYNC_TEST_BASE;
for (const url of [web, base]) assert.match(url ?? '', /^http:\/\/127\.0\.0\.1:\d+$/);
const fixture = JSON.parse(await readFile(process.env.RETAINED_FIXTURES, 'utf8'));
if (process.env.RETAINED_REQUIRE_REFUSED === '1') assert.ok(fixture.cases.refused, 'engine must support real refused records');
const pdfs = await Promise.all(['A', 'B'].map(r => readFile(process.env.EVIDENCE_PDF_DIR + `/synthetic-${r}.pdf`)));
const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
let passed = 0, failed = 0;

async function scenario(name, actor, work) {
  const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' });
  const page = await context.newPage();
  page.setDefaultTimeout(5000);
  const errors = [], writes = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('request', r => { if (r.url().startsWith(base) && r.method() !== 'GET') writes.push(new URL(r.url()).pathname); });
  await page.route('**/*', route => ['127.0.0.1', 'localhost'].includes(new URL(route.request().url()).hostname) ? route.continue() : route.abort());
  await page.addInitScript(() => {
    const original = window.fetch;
    window.fileGates = [];
    window.holdFileRead = path => {
      let release;
      const gate = { path, entered: false, returned: false, aborted: false, release: null };
      gate.wait = new Promise(resolve => { release = resolve; });
      gate.release = release;
      window.fileGates.push(gate);
      return window.fileGates.length - 1;
    };
    window.fetch = async (input, init) => {
      const path = new URL(String(input), location.href).pathname;
      const gate = window.fileGates.find(g => !g.entered && g.path === path && (!init?.method || init.method === 'GET'));
      if (!gate) return original(input, init);
      gate.entered = true;
      init?.signal?.addEventListener('abort', () => { gate.aborted = true; });
      // This is a real authorized HTTP response held past navigation/session change.
      // Deliberately ignore the abort too: the consumer must guard the late continuation.
      const response = await original(input, { ...init, signal: undefined });
      gate.status = response.status;
      gate.ready = true;
      await gate.wait;
      gate.returned = true;
      return response;
    };
  });
  async function session(who) {
    await context.clearCookies();
    await context.addCookies([{ name: 'batatis_session', value: fixture.users[who].cookie, url: base, httpOnly: true, sameSite: 'Lax' }]);
    await page.evaluate(async () => {
      const { setCredentialsMode } = await import('/src/api/engineAuth.ts');
      setCredentialsMode('include');
      const { engine } = await import('/src/api/client.ts');
      const response = await fetch(new URL(engine.fileUrl('unused', 'unused')).origin + '/auth/me', { credentials: 'include' });
      if (!response.ok) throw new Error('Synthetic session is not authenticated');
      const { user } = await response.json();
      const applicationsResponse = await fetch(new URL(engine.fileUrl('unused', 'unused')).origin + '/me/applications', { credentials: 'include' });
      const { applications } = await applicationsResponse.json();
      const { setAccountState } = await import('/src/calm/account.ts');
      setAccountState({ phase: 'signed-in', user, applications });
    });
  }
  async function open(which, who = actor) {
    const c = fixture.cases[which];
    if (who === 'applicant') {
      assert.equal(await page.evaluate(id => window.caseStore.openCase(id, 'contractor'), c.id), null);
      await page.evaluate(() => { location.hash = '#/application'; });
      await page.getByRole('article', { name: 'Application preview' }).waitFor();
    } else {
      await page.evaluate(id => { location.hash = '#/officer?case=' + id; }, c.id);
      await page.getByRole('article', { name: 'Submitted application' }).waitFor();
    }
    return c;
  }
  const disclosure = () => page.locator('details').filter({ has: page.locator('summary', { hasText: 'Saved source PDFs' }) });
  async function inventory(which) {
    await page.evaluate(id => { location.hash = '#/inventory?case=' + id; }, fixture.cases[which].id);
    const summary = disclosure().locator('summary');
    await summary.waitFor();
    if (!await disclosure().evaluate(el => el.open)) await summary.click();
    return disclosure();
  }
  const hold = path => page.evaluate(path => window.holdFileRead(path), path);
  const entered = gate => page.waitForFunction(gate => window.fileGates[gate].ready, gate);
  const release = async gate => {
    await page.evaluate(gate => window.fileGates[gate].release(), gate);
    await page.waitForFunction(gate => window.fileGates[gate].returned, gate);
    await page.evaluate(() => new Promise(requestAnimationFrame));
  };
  try {
    await page.goto(web + '/tests/retained-sources.html');
    await page.waitForFunction(() => !!window.caseStore);
    await session(actor);
    await work({ page, context, open, session, inventory, disclosure, hold, entered, release });
    assert.deepEqual(errors, []);
    assert.equal(writes.some(path => /\/files|\/evidence|\/submit|\/decision|\/identify|\/intake/.test(path)), false, 'the disclosure performs no writes');
    passed++; console.log('PASS', name);
  } catch (error) { failed++; console.log('FAIL', name, error.stack); }
  finally { await context.close(); }
}

for (const status of Object.keys(fixture.cases).filter(s => !['second', 'expired', 'empty', 'disappearing'].includes(s))) {
  for (const actor of ['applicant', 'officer']) {
    if (actor === 'officer' && ['draft', 'withdrawn'].includes(status)) continue;
    if (process.env.RETAINED_REPRODUCE === '1' && (status !== 'accepted' || actor !== 'applicant')) continue;
    await scenario(`${actor} ${status}: original and current PDFs remain downloadable from the read-only sheet`, actor, async ({ page, context, open }) => {
      const c = await open(status);
      const before = await (await context.request.get(base + '/cases/' + c.id)).json();
      assert.equal(before.status, status, 'actual server status, not a simulated label');
      if (status === 'accepted' && actor === 'applicant') await page.getByText('Accepted by Edmonton', { exact: true }).waitFor();
      const disclosure = page.locator('details').filter({ has: page.locator('summary', { hasText: 'Saved source PDFs' }) });
      await disclosure.locator('summary').click();
      for (const [i, file] of c.files.entries()) {
        const pending = page.waitForEvent('download');
        await disclosure.getByRole('link', { name: 'Download ' + file.name, exact: true }).click();
        assert.deepEqual(await readFile(await (await pending).path()), pdfs[i]);
      }
      const after = await (await context.request.get(base + '/cases/' + c.id)).json();
      assert.equal(after.version, before.version, 'inventory and delivery never advance content CAS');
      assert.deepEqual(after.evidence, before.evidence);
      assert.equal([...after.facts].reverse().find(f => f.field.endsWith('.file_ref')).value, c.files[1].id);
    });
  }
}

if (process.env.RETAINED_REPRODUCE !== '1') {
  await scenario('case change aborts inventory and discards the late authorized response', 'applicant', async ({ page, inventory, hold, entered, release }) => {
    const first = fixture.cases.accepted, second = fixture.cases.second;
    const gate = await hold(`/cases/${first.id}/files`);
    await inventory('accepted'); await entered(gate);
    const list = await inventory('second');
    await list.getByRole('link', { name: 'Download ' + second.files[0].name }).waitFor();
    assert.equal(await page.evaluate(gate => window.fileGates[gate].aborted, gate), true);
    await release(gate);
    assert.equal(await list.getByText(first.files[0].name, { exact: true }).count(), 0);
    assert.equal(await list.getByRole('link').count(), 2);
  });

  await scenario('account change clears inventory and discards the late authorized response', 'applicant', async ({ page, inventory, session, hold, entered, release }) => {
    const c = fixture.cases.accepted;
    const gate = await hold(`/cases/${c.id}/files`);
    const list = await inventory('accepted'); await entered(gate);
    await session('other');
    await list.getByText(/Source PDFs are unavailable/).waitFor();
    assert.equal(await page.evaluate(gate => window.fileGates[gate].aborted, gate), true);
    await release(gate);
    assert.equal(await list.getByRole('link').count(), 0);
    assert.equal(await list.getByText(c.files[0].name, { exact: true }).count(), 0);
  });

  await scenario('an application-list refresh preserves a same-session source download', 'applicant', async ({ page, inventory, hold, entered, release }) => {
    const c = fixture.cases.accepted;
    const list = await inventory('accepted');
    const link = list.getByRole('link', { name: 'Download ' + c.files[0].name });
    await link.waitFor();
    const gate = await hold(`/cases/${c.id}/files/${c.files[0].id}`);
    await link.click(); await entered(gate);
    await page.evaluate(async () => (await import('/src/calm/account.ts')).refreshApplications());
    assert.equal(await page.evaluate(gate => window.fileGates[gate].aborted, gate), false);
    const pending = page.waitForEvent('download');
    await release(gate);
    assert.deepEqual(await readFile(await (await pending).path()), pdfs[0]);
  });

  for (const change of ['case', 'account']) {
    await scenario(`${change} change aborts download and never saves late prior-case bytes`, 'applicant', async ({ page, inventory, session, hold, entered, release }) => {
      const c = fixture.cases.accepted;
      const list = await inventory('accepted');
      const link = list.getByRole('link', { name: 'Download ' + c.files[0].name });
      await link.waitFor();
      const downloads = []; page.on('download', file => downloads.push(file));
      const gate = await hold(`/cases/${c.id}/files/${c.files[0].id}`);
      await link.click(); await entered(gate);
      if (change === 'case') {
        const next = await inventory('second');
        await next.getByRole('link', { name: 'Download ' + fixture.cases.second.files[0].name }).waitFor();
      } else {
        await session('other');
        await list.getByText(/Source PDFs are unavailable/).waitFor();
      }
      assert.equal(await page.evaluate(gate => window.fileGates[gate].aborted, gate), true);
      await release(gate);
      assert.equal(downloads.length, 0);
    });
  }

  await scenario('real re-login as the same applicant aborts a previous-session download', 'applicant', async ({ page, context, inventory, hold, entered, release }) => {
    const c = fixture.cases.accepted;
    const list = await inventory('accepted');
    const link = list.getByRole('link', { name: 'Download ' + c.files[0].name });
    await link.waitFor();
    const before = (await context.cookies(base)).find(cookie => cookie.name === 'batatis_session').value;
    const downloads = []; page.on('download', file => downloads.push(file));
    const gate = await hold(`/cases/${c.id}/files/${c.files[0].id}`);
    await link.click(); await entered(gate);
    const id = await page.evaluate(async ({ base, email }) => {
      const response = await fetch(base + '/auth/login', { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password: 'a long test password' }) });
      if (!response.ok) throw new Error('Synthetic re-login failed');
      const { user } = await response.json();
      const { setAccountState } = await import('/src/calm/account.ts');
      setAccountState({ phase: 'signed-in', user, applications: null });
      return user.id;
    }, { base, email: fixture.users.applicant.user.email });
    assert.equal(id, fixture.users.applicant.user.id);
    const after = (await context.cookies(base)).find(cookie => cookie.name === 'batatis_session').value;
    assert.notEqual(after, before);
    // The real login invalidates the old fixture session, including for later scenarios.
    fixture.users.applicant.cookie = after;
    await list.getByRole('link', { name: 'Download ' + c.files[0].name }).waitFor();
    assert.equal(await page.evaluate(gate => window.fileGates[gate].aborted, gate), true);
    await release(gate);
    assert.equal(downloads.length, 0);
  });

  for (const actor of ['other', 'foreign']) {
    await scenario(`${actor} cannot list or download another application's sources`, actor, async ({ context, inventory }) => {
      const list = await inventory('accepted');
      await list.getByText(/Source PDFs are unavailable/).waitFor();
      assert.equal(await list.getByRole('link').count(), 0);
      const c = fixture.cases.accepted;
      for (const path of [`/cases/${c.id}/files`, `/cases/${c.id}/files/${c.files[0].id}`]) {
        const response = await context.request.get(base + path);
        assert.equal(response.status(), 404);
        assert.equal(response.headers()['cache-control'], 'no-store');
      }
    });
  }

  await scenario('expired source inventory fails closed, and an empty inventory has its own state', 'applicant', async ({ context, inventory }) => {
    const list = await inventory('expired');
    await list.getByText(/Source PDFs are unavailable/).waitFor();
    assert.equal(await list.getByRole('link').count(), 0);
    const c = fixture.cases.expired;
    assert.equal((await context.request.get(base + `/cases/${c.id}/files/${c.files[0].id}`)).status(), 404);
    const empty = await inventory('empty');
    await empty.getByText('No source PDFs are stored in this application.', { exact: true }).waitFor();
    assert.equal(await empty.getByRole('link').count(), 0);
  });

  await scenario('an unavailable download clears the inventory rather than retaining stale file links', 'applicant', async ({ context, page, inventory }) => {
    const c = fixture.cases.disappearing;
    const list = await inventory('disappearing');
    const link = list.getByRole('link', { name: 'Download ' + c.files[0].name });
    await link.waitFor();
    assert.equal((await context.request.delete(base + '/cases/' + c.id)).status(), 204);
    const downloads = []; page.on('download', file => downloads.push(file));
    await link.click();
    await list.getByText(/Source PDFs are unavailable/).waitFor();
    assert.equal(await list.getByRole('link').count(), 0);
    assert.equal(downloads.length, 0);
  });
}

await browser.close();
console.log(`J03 retained source sheets: ${passed} passed, ${failed} failed; refused HTTP ${fixture.cases.refused ? 'included' : 'unavailable on this engine base'}`);
process.exitCode = failed ? 1 : 0;
