// Production queue/SubmitPanel -> authenticated HTTP -> disposable SQLite. No captures/providers.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE
  ? pathToFileURL(process.env.PLAYWRIGHT_MODULE).href : 'playwright-core');
const web = process.env.SYNC_WEB_BASE, base = process.env.SYNC_TEST_BASE;
for (const url of [web, base]) assert.match(url ?? '', /^http:\/\/127\.0\.0\.1:\d+$/);
const fixture = JSON.parse(await readFile(process.env.CONTINUITY_FIXTURES, 'utf8'));
const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
let passed = 0, failed = 0, next = 0;
const poll = page => page.evaluate(async () => (await import('/src/calm/notifications/notifications.ts')).loadNotifications());
const queueState = page => page.evaluate(() => window.reviewData.getQueueState());

async function scenario(name, run) {
  const context = await browser.newContext(), applicant = await browser.newContext();
  for (const [ctx, who] of [[context, 'reviewer'], [applicant, 'applicant']]) {
    await ctx.addCookies([{ name: 'batatis_session', value: fixture[who].cookie, url: base, httpOnly: true, sameSite: 'Lax' }]);
  }
  const page = await context.newPage();
  page.setDefaultTimeout(7000);
  const id = fixture.ids[next++], title = `SYNTHETIC continuity application ${fixture.ids.indexOf(id)}`;
  const requests = [], errors = [], gates = [];
  page.on('pageerror', error => errors.push(error.message));
  const api = async (ctx, path, data, method = 'POST') => {
    const response = await ctx.request.fetch(base + path, { method, ...(data === undefined ? {} : { data }) });
    assert.ok(response.ok(), `${method} ${path}: ${response.status()} ${await response.text()}`);
    return response.status() === 204 ? null : response.json();
  };
  await page.route('**/*', async route => {
    const req = route.request(), url = new URL(req.url());
    if (url.origin !== web) return route.abort();
    if (!url.pathname.startsWith('/api/')) return route.continue();
    const entry = { path: url.pathname.slice(4), method: req.method() };
    requests.push(entry);
    const gate = gates.find(g => !g.used && g.path === entry.path && g.method === entry.method);
    if (gate) gate.used = true;
    const response = await route.fetch({ url: base + entry.path + url.search });
    entry.status = response.status();
    if (gate) { gate.ready(); await gate.wait; }
    await route.fulfill({ response });
  });
  const hold = (path, method = 'GET') => {
    let ready, release;
    const entered = new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error(`Expected delayed ${method} ${path}`)), 7000);
      ready = () => { clearTimeout(timer); resolve(); };
    });
    const wait = new Promise(resolve => { release = resolve; });
    gates.push({ path, method, ready, release, wait });
    return { entered, release };
  };
  const open = async () => {
    await page.goto(web + '/tests/check.html#/review');
    await page.getByRole('heading', { name: /Review queue/ }).waitFor();
    await page.evaluate(async () => { window.reviewData = await import('/src/calm/reviewer/reviewData.ts'); });
    await page.waitForFunction(() => window.reviewData.getQueueState().phase === 'ready');
    await poll(page);
    await page.evaluate(() => window.reviewData.loadQueue());
  };
  const submit = () => api(applicant, `/cases/${id}/submit`, {});
  const row = () => page.getByRole('row').filter({ has: page.getByRole('link', { name: title, exact: true }) });
  const replaceAccount = async who => {
    await context.addCookies([{ name: 'batatis_session', value: fixture[who].cookie, url: base }]);
    await page.evaluate(async user => (await import('/src/calm/account.ts')).setAccountState({ phase: 'signed-in', user, applications: [] }), fixture[who].user);
  };
  const replacedQueue = () => page.waitForFunction(() => {
    const state = window.reviewData.getQueueState();
    return ['ready', 'error'].includes(state.phase) && state.rows.length === 0;
  });
  try {
    await run({ page, context, applicant, id, title, requests, api, hold, open, submit, row, replaceAccount, replacedQueue });
    assert.deepEqual(errors, []);
    assert.equal(requests.some(r => r.method === 'POST' && /\/(identify|intake|relevance)(\/|$)/.test(r.path)), false);
    passed++; console.log('PASS', name);
  } catch (error) {
    failed++; console.error('FAIL', name, error.stack);
    console.error('Queue receipt', await page.evaluate(async () => ({ queue: window.reviewData?.getQueueState(),
      authority: (await import('/src/calm/account.ts')).getAccountState().user?.authority,
      path: location.hash, text: document.querySelector('.ac-page')?.textContent?.slice(0, 1800) })), requests.slice(-12));
  } finally {
    for (const gate of gates) { gate.ready(); gate.release(); }
    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await context.close(); await applicant.close();
  }
}

try {
  await scenario('J08 open empty queue receives first submission and real applicant resubmission through notifications', async ({ page, context, applicant, id, title, requests, api, open, submit, row }) => {
    await open();
    await page.getByText('No applications have been sent to Edmonton yet.', { exact: true }).waitFor();
    await page.getByRole('button', { name: /^New 0$/ }).click();
    await page.getByRole('searchbox', { name: 'Search applications' }).fill(title);
    await submit(); await poll(page);
    await row().getByRole('button', { name: 'Start reviewing', exact: true }).waitFor();
    assert.equal(await page.getByRole('searchbox').inputValue(), title);
    assert.equal(await page.getByRole('button', { name: /^New 1$/ }).getAttribute('aria-pressed'), 'true');
    // Repeated polls and read markers must not create queue requests or another timer.
    const before = requests.filter(r => r.path === '/review/queue').length;
    await poll(page);
    await page.evaluate(async () => (await import('/src/calm/notifications/notifications.ts')).openedPanel());
    assert.equal(requests.filter(r => r.path === '/review/queue').length, before);
    await row().getByRole('button', { name: 'Start reviewing', exact: true }).click();
    await page.getByRole('article', { name: 'Submitted application' }).waitFor();
    const expiry = await api(applicant, '/cases/' + id, undefined, 'GET');
    assert.equal(await page.getByRole('note').filter({ hasText: 'Stored until' }).locator('time[datetime]').getAttribute('datetime'), expiry.expires_at);
    assert.match(await page.getByRole('note').filter({ hasText: 'Stored until' }).innerText(), /seven days after creation.*attachments.*authority’s records.*does not extend/s);
    await api(context, `/review/${id}/decision`, { outcome: 'return', message: 'Please clarify the synthetic legal description.', items: [{ field: 'legalDescription', note: 'Clarify the synthetic lot.' }] });
    await page.evaluate(() => { location.hash = '#/review'; });
    await page.getByRole('button', { name: /^Mine / }).click();
    await page.getByRole('searchbox', { name: 'Search applications' }).fill(title);
    const ownerPage = await applicant.newPage();
    await ownerPage.route('**/*', async route => {
      const url = new URL(route.request().url());
      if (url.origin !== web) return route.abort();
      if (!url.pathname.startsWith('/api/')) return route.continue();
      const response = await route.fetch({ url: base + url.pathname.slice(4) + url.search });
      await route.fulfill({ response });
    });
    await ownerPage.goto(web + '/tests/check.html');
    await ownerPage.locator('.cf-app').waitFor();
    await ownerPage.evaluate(async id => {
      await (await import('/src/calm/account.ts')).refreshApplications();
      const error = await window.caseStore.openCase(id, 'contractor');
      if (error) throw new Error(error);
      window.caseStore.dispatch({ type: 'setDetail', field: 'legalDescription', section: 'B', value: 'REVISION B — synthetic corrected lot' });
      location.hash = '#/application';
    }, id);
    await ownerPage.waitForFunction(() => window.caseStore.sectionCLookup.source === 'live');
    assert.equal(await ownerPage.getByRole('note').filter({ hasText: 'Stored until' }).locator('time[datetime]').getAttribute('datetime'), expiry.expires_at);
    await ownerPage.getByRole('button', { name: 'Resubmit to Edmonton', exact: true }).click();
    await ownerPage.getByText('Sent to Edmonton', { exact: true }).waitFor();
    await ownerPage.getByText(/Resubmitted · submission 2/).waitFor();
    const revised = await api(applicant, '/cases/' + id, undefined, 'GET');
    assert.equal(revised.claim.reviewer_id, fixture.reviewer.user.id);
    assert.equal(revised.expires_at, expiry.expires_at);
    await poll(page);
    await row().getByText('Resubmitted', { exact: true }).waitFor();
    await row().getByRole('button', { name: 'Resume review', exact: true }).waitFor();
    assert.equal(await page.getByRole('button', { name: /^Mine 1$/ }).getAttribute('aria-pressed'), 'true');
    assert.equal(await page.getByRole('searchbox').inputValue(), title);
    assert.equal(await page.getByRole('button', { name: /^New 0$/ }).count(), 1);
    await row().getByRole('link', { name: title, exact: true }).click();
    const history = page.getByRole('region', { name: 'Submission history' });
    await history.getByText('Resubmitted · submission 2', { exact: true }).waitFor();
    await history.getByText(/changed item/).click();
    assert.match(await history.innerText(), /Before: REVISION A.*Now: REVISION B/s);
    await history.getByText('Decision history (1)', { exact: true }).click();
    assert.match(await history.innerText(), /Returned · Synthetic reviewer/);
    await page.getByText('Clarify the synthetic lot.', { exact: true }).waitFor();
    assert.equal(await page.getByRole('button', { name: 'Accept as complete', exact: true }).isDisabled(), true);
    await page.getByRole('button', { name: 'Resume review', exact: true }).click();
    await page.getByText(/You’re reviewing this/).waitFor();
    assert.equal((await api(applicant, '/cases/' + id, undefined, 'GET')).status, 'in_review');
  });

  await scenario('J08 a delayed queue response cannot roll back an acknowledged exclusive claim', async ({ page, id, open, submit, hold, row }) => {
    await submit(); await open();
    const reading = hold('/review/queue');
    await page.evaluate(() => { window.oldQueueRead = window.reviewData.loadQueue(true); });
    await reading.entered;
    await row().getByRole('button', { name: 'Start reviewing', exact: true }).click();
    await page.getByRole('article', { name: 'Submitted application' }).waitFor();
    reading.release();
    await page.evaluate(() => window.oldQueueRead);
    const entry = (await queueState(page)).rows.find(row => row.id === id);
    assert.equal(entry.status, 'in_review');
    assert.equal(entry.claim.reviewer_id, fixture.reviewer.user.id);
  });

  await scenario('J08 a late queue response is discarded after the officer authority changes', async ({ page, open, submit, hold, replaceAccount, replacedQueue }) => {
    await submit(); await open();
    const reading = hold('/review/queue');
    await page.evaluate(() => { window.oldQueueRead = window.reviewData.loadQueue(true); });
    await reading.entered;
    await replaceAccount('foreign');
    await replacedQueue();
    reading.release(); await page.evaluate(() => window.oldQueueRead);
    assert.deepEqual((await queueState(page)).rows, []);
    assert.deepEqual((await queueState(page)).blocking, {});
    assert.equal(await page.locator('.ac-table').count(), 0);
  });

  await scenario('J08 late blocking counts cannot leak into another officer account', async ({ page, id, open, submit, hold, replaceAccount, replacedQueue }) => {
    await submit();
    const reading = hold('/cases/' + id + '/gaps');
    await open(); await reading.entered;
    await replaceAccount('foreign');
    await replacedQueue();
    reading.release();
    await page.waitForTimeout(100);
    assert.deepEqual((await queueState(page)).blocking, {});
    assert.deepEqual((await queueState(page)).rows, []);
  });

  await scenario('J08 a pending claim cannot navigate or publish into a replacement officer session', async ({ page, id, open, submit, hold, row, replaceAccount, replacedQueue }) => {
    await submit(); await open();
    const claiming = hold('/review/' + id + '/claim', 'POST');
    await row().getByRole('button', { name: 'Start reviewing', exact: true }).click();
    await claiming.entered;
    await replaceAccount('foreign');
    await replacedQueue();
    claiming.release();
    await page.waitForTimeout(100);
    assert.equal(await page.evaluate(() => location.hash), '#/review');
    assert.deepEqual((await queueState(page)).rows, []);
    assert.equal(await page.getByRole('dialog').count(), 0);
  });

  await scenario('J08 queue rejects a server response for another reviewer in the same authority', async ({ page, context, open, submit, replaceAccount }) => {
    await submit(); await open();
    await replaceAccount('second');
    await page.evaluate(() => window.reviewData.loadQueue(true));
    // Model a late cookie renewal from an older request. Authority alone cannot identify the viewer.
    await context.addCookies([{ name: 'batatis_session', value: fixture.reviewer.cookie, url: base }]);
    await page.evaluate(() => window.reviewData.loadQueue(true));
    assert.deepEqual((await queueState(page)).rows, []);
    assert.deepEqual((await queueState(page)).blocking, {});
    assert.match((await queueState(page)).error, /sign-in changed/);
    assert.equal(await page.locator('.ac-table').count(), 0);
  });
} finally { await browser.close(); }
console.log(`Review continuity integration: ${passed} passed, ${failed} failed`);
process.exitCode = failed ? 1 : 0;
