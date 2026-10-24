// Mounted production Shell + CaseProvider -> authenticated HTTP -> disposable SQLite.
// No provider calls, external network, user records, screenshots or persisted browser profile.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE
  ? pathToFileURL(process.env.PLAYWRIGHT_MODULE).href : 'playwright-core');
const web = process.env.SYNC_WEB_BASE, base = process.env.SYNC_TEST_BASE;
for (const url of [web, base]) assert.match(url ?? '', /^http:\/\/127\.0\.0\.1:\d+$/);
const fixture = JSON.parse(await readFile(process.env.REFRESH_FIXTURES, 'utf8'));
const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
let next = 0, passed = 0, failed = 0;
const legal = c => [...c.facts].reverse().find(f => f.field === 'legalDescription')?.value;
const action = value => ({ type: 'setDetail', field: 'legalDescription', section: 'B', value });
const localValue = page => page.evaluate(() => [...window.caseStore.c.facts].reverse().find(f => f.field === 'legalDescription')?.value);
const poll = page => page.evaluate(async () => (await import('/src/calm/notifications/notifications.ts')).loadNotifications());
const patchStatus = (page, id, status) => page.evaluate(async ({ id, status }) => {
  (await import('/src/calm/account.ts')).patchApplication(id, { status });
}, { id, status });
const edit = async (page, value) => {
  await page.evaluate(a => window.caseStore.dispatch(a), action(value));
  await page.waitForFunction(value => window.caseStore.c.facts.some(f => f.field === 'legalDescription' && f.value === value), value);
};
const acknowledged = (page, id) => page.evaluate(async id => (await import('/src/api/sync.ts')).acknowledgedVersion(id), id);

async function scenario(name, run, role = 'applicant') {
  if (process.env.REFRESH_FILTER && !name.includes(process.env.REFRESH_FILTER)) return;
  const context = await browser.newContext();
  const officer = await browser.newContext();
  for (const [ctx, who] of [[context, role], [officer, 'reviewer']]) {
    await ctx.addCookies([{ name: 'batatis_session', value: fixture[who].cookie, url: base, httpOnly: true, sameSite: 'Lax' }]);
  }
  const page = await context.newPage();
  page.setDefaultTimeout(3500);
  const id = fixture.ids[next++], other = fixture.ids[next++];
  const requests = [], errors = [], gates = [];
  page.on('pageerror', e => errors.push(e.message));
  const api = async (ctx, path, data, method = 'POST') => {
    const response = await ctx.request.fetch(base + path, { method, ...(data === undefined ? {} : { data }) });
    assert.ok(response.ok(), `${method} ${path}: ${response.status()} ${await response.text()}`);
    return response.status() === 204 ? null : response.json();
  };
  const remote = (caseId = id) => api(context, '/cases/' + caseId, undefined, 'GET');
  const returned = async () => {
    await api(officer, `/review/${id}/claim`, {});
    await api(officer, `/review/${id}/decision`, { outcome: 'return', message: 'Please correct the synthetic legal description.', items: [] });
  };
  await page.route('**/*', async route => {
    const url = new URL(route.request().url()), req = route.request();
    if (url.origin !== web) return route.abort();
    if (!url.pathname.startsWith('/api/')) return route.continue();
    const cookie = (await req.allHeaders()).cookie ?? '';
    const entry = { path: url.pathname.slice(4), method: req.method(), actor: cookie.includes(fixture.applicant.cookie) ? 'applicant' : cookie.includes(fixture.reviewer.cookie) ? 'reviewer' : 'unknown' };
    requests.push(entry);
    const gate = gates.find(g => !g.used && g.matches(entry));
    if (gate) gate.used = true;
    if (gate && !gate.after) { gate.ready(); await gate.wait; }
    const response = await route.fetch({ url: base + entry.path + url.search });
    entry.status = response.status();
    if (gate?.after) { gate.ready(); await gate.wait; }
    await route.fulfill({ response });
  });
  const hold = (path, method = 'GET', after = true) => {
    let ready, release;
    const entered = new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error(`Expected delayed ${method} ${path}`)), 5000);
      ready = () => { clearTimeout(timer); resolve(); };
    });
    const wait = new Promise(resolve => { release = resolve; });
    gates.push({ matches: r => r.path === path && r.method === method, after, ready, wait, release });
    return { entered, release };
  };
  const open = async (caseId = id) => {
    assert.equal(await page.evaluate(caseId => window.caseStore.openCase(caseId, 'contractor'), caseId), null);
    await page.waitForFunction(caseId => window.caseStore.engineId === caseId, caseId);
    await page.evaluate(() => { location.hash = '#/application'; });
    await page.getByRole('region', { name: 'Application form' }).waitFor();
  };
  const row = () => page.locator('.cf-list-hit[aria-current="page"]');
  try {
    await page.goto(web + '/tests/check.html' + (role === 'reviewer' ? `#/review/${id}` : ''));
    await page.waitForFunction(() => !!window.caseStore);
    await page.locator('.cf-app').waitFor(); // Wait for the mounted auth gate, not an async polling predicate.
    await page.evaluate(() => import('/src/calm/calm.css'));
    if (role === 'applicant') { await open(); await poll(page); }
    await run({ page, context, officer, id, other, requests, hold, api, remote, returned, open, row });
    assert.deepEqual(errors, []);
    assert.equal(requests.filter(r => r.method === 'POST' && /\/(identify|intake)/.test(r.path)).length, 0, 'refresh spent a provider call');
    passed++; console.log('PASS', name);
  } catch (error) {
    failed++; console.error('FAIL', name, error.stack);
  } finally {
    for (const gate of gates) { gate.ready(); gate.release(); }
    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await context.close(); await officer.close();
  }
}

// The officer's review shows one step at a time: the decision is the last step (or the panel shown when no
// package review ran). The submitted application sits in the header's Application drawer and the thread,
// with its composer, in the Messages drawer (an unsent message survives closing it).
const officerReady = page => page.getByRole('button', { name: /^Messages/ }).waitFor();
async function decisionStep(page) {
  // Resuming starts the saved version's automatic package review. A new review deliberately
  // starts on Changes, so choose Decide after that version has finished replacing the old one.
  await page.locator('.pr-note').filter({ hasText: 'Changed since review v' }).waitFor({ state: 'detached' });
  const ask = page.getByRole('button', { name: 'Ask for more', exact: true });
  const step = page.getByRole('navigation', { name: 'Review steps' }).getByRole('button', { name: /: Decide\b/ });
  await ask.or(step).first().waitFor();
  if (!await ask.isVisible()) await step.click();
  await ask.waitFor();
}
async function openReturn(page) {
  await decisionStep(page);
  const plain = page.getByRole('button', { name: 'Return with a message', exact: true });
  await (await plain.count() ? plain : page.getByRole('button', { name: 'Ask for more', exact: true })).click();
  return page.getByRole('dialog', { name: 'Return with a message', exact: true });
}
async function messagesDrawer(page) {
  await page.getByRole('button', { name: /^Messages/ }).click();
  return page.getByRole('dialog', { name: 'Messages' });
}

try {
  await scenario('J05 selected-article-only revisions reconcile every card before a later acknowledged save', async ({ page, context, id, other, open, returned, row, api, remote, requests }) => {
    await returned(); await poll(page);
    await page.getByRole('button', { name: 'Resubmit to Edmonton', exact: true }).waitFor();
    await page.waitForFunction(() => window.caseStore.sectionCLookup.source === 'live');
    await page.evaluate(async () => {
      window.refreshSelection = (await import('/src/calm/openCase.ts')).selectedArticles;
      window.refreshVersion = (await import('/src/api/sync.ts')).acknowledgedVersion;
    });
    const saved = await remote();
    const baseline = saved.selected_articles ?? saved.provisions.map(provision => ({ id: 'search-' + provision, provision, answer: 'yes', pending: false }));
    const b = { id: 'search-remote-b', provision: '9.27.3.4.', answer: null, pending: false };
    const selections = [
      [...baseline, b],
      [...baseline, { ...b, id: 'search-remote-b-renamed' }],
      [...baseline, { ...b, provision: '9.27.3.4.(2)' }],
      [...baseline, { ...b, answer: 'not-sure' }],
      [...baseline, { ...b, answer: 'no', pending: true }],
      [...baseline, { ...b, answer: 'no', pending: false }],
      [...baseline, { ...b, answer: 'yes', pending: true }],
      [],
      [b, ...baseline],
    ];
    for (const [index, selected_articles] of selections.entries()) {
      const before = await remote();
      const updated = await api(context, `/cases/${id}/selected-articles`, { expected_version: before.version, selected_articles }, 'PUT');
      assert.deepEqual(updated.provisions, saved.provisions, 'selection writes never confirm or withdraw a benchmark');
      const start = requests.length;
      await row().click();
      await page.waitForFunction(({ id, version }) => window.refreshVersion(id) === version, { id, version: updated.version });
      await page.waitForFunction(expected => JSON.stringify(window.refreshSelection(window.caseStore.c)) === JSON.stringify(expected), selected_articles);
      const actual = await page.evaluate(async () => {
        const { selectedArticles } = await import('/src/calm/openCase.ts');
        return selectedArticles(window.caseStore.c);
      });
      assert.deepEqual(actual, selected_articles, 'the acknowledged revision must include the complete saved selection');
      assert.equal(await page.evaluate(() => window.caseStore.c.candidates.some(a => a.id === 'search-remote-b' && a.benchmark)), false, 'a selected or pending Yes is not a confirmed benchmark');
      if (selected_articles.some(a => a.answer === 'not-sure')) {
        assert.equal(await page.evaluate(() => window.caseStore.c.questions.some(q => q.cardId === 'search-remote-b')), true, 'Not sure retains its open question');
      }
      await page.waitForLoadState('networkidle');
      if (index === 0) await page.waitForTimeout(650); // Beyond the autosave deadline: adoption must remain read-only.
      assert.equal(requests.slice(start).some(r => r.method !== 'GET' && r.path !== '/section-c'), false, 'refresh must not write the adopted selection in the background');
      assert.equal((await remote()).version, updated.version);
    }
    await page.evaluate(() => { window.cardsBeforeSelectionRefresh = window.caseStore.c.candidates; });
    assert.equal(await page.evaluate(() => window.caseStore.refreshCurrentCase()), null);
    assert.equal(await page.evaluate(() => window.caseStore.c.candidates === window.cardsBeforeSelectionRefresh), true, 'an unchanged selection retains the active cards');
    await page.evaluate(() => { location.hash = '#/code/' + encodeURIComponent('9.27.3.1.(1)'); });
    const writing = page.waitForResponse(r => r.request().method() === 'PUT' && r.url().endsWith('/selected-articles'));
    await page.getByRole('button', { name: 'Add to my application', exact: true }).click();
    const response = await writing;
    assert.equal(response.status(), 200, await response.text());
    await page.locator('.cf-save-label').filter({ hasText: 'Saved' }).waitFor();
    const after = await remote();
    assert.ok(after.selected_articles.some(a => a.id === b.id && a.provision === b.provision), 'the later acknowledged PUT/GET retains remote B');
    assert.ok(after.selected_articles.some(a => a.provision === '9.27.3.1.(1)'), 'the later local addition was saved');
    await page.evaluate(() => window.caseStore.decide(window.caseStore.c.candidates.find(a => a.id === 'search-remote-b'), 'yes'));
    await page.waitForFunction(() => window.caseStore.c.candidates.some(a => a.provision === '9.27.3.4.(1)'));
    assert.equal(await page.evaluate(() => window.caseStore.c.candidates.some(a => a.provision.startsWith('9.27.3.4.') && (a.answer !== null || a.benchmark))), false, 'explicit expansion never inherits the parent Yes');
    assert.equal(await page.evaluate(() => window.caseStore.saveDraft()), id);
    assert.deepEqual((await remote()).provisions, saved.provisions, 'an answer or lookup never substitutes for confirmed references');
    await open(other);
    await page.waitForFunction(() => window.caseStore.sectionCLookup.source === 'live' && window.caseStore.c.candidates.some(a => a.provision === '9.27.3.4.(1)'));
    await page.evaluate(() => { window.cardsBeforeSelectionRefresh = window.caseStore.c.candidates; });
    assert.equal(await page.evaluate(() => window.caseStore.refreshCurrentCase()), null);
    assert.equal(await page.evaluate(() => window.caseStore.c.candidates === window.cardsBeforeSelectionRefresh), true, 'unchanged read-only content retains its derived cards and active controls');
  });

  await scenario('J05 a new return notification refreshes the open application and unlocks it without reload or fetch loops', async ({ page, returned, requests }) => {
    await page.evaluate(() => window.caseStore.dispatch({ type: 'addFiles', files: [{ id: 'synthetic-local-pdf', name: 'Synthetic plan.pdf' }] }));
    await returned(); await poll(page);
    await page.getByRole('button', { name: 'Resubmit to Edmonton', exact: true }).waitFor();
    await page.evaluate(() => window.caseStore.refreshCurrentCase());
    assert.equal(await page.locator('.cf-save').innerText(), 'Saved');
    assert.equal(await page.evaluate(() => window.caseStore.c.files[0]?.name), 'Synthetic plan.pdf', 'a status-only refresh lost local file labels');
    const count = requests.filter(r => /\/me\/applications$|\/cases\/[^/]+$/.test(r.path)).length;
    await poll(page); await poll(page);
    await page.waitForTimeout(650);
    assert.equal(requests.filter(r => /\/me\/applications$|\/cases\/[^/]+$/.test(r.path)).length, count, 'same notifications repeatedly refreshed the application');
  });

  await scenario('J05 acceptance refreshes the already-open read-only application', async ({ page, officer, api, id }) => {
    await api(officer, `/review/${id}/claim`, {});
    await api(officer, `/review/${id}/decision`, { outcome: 'accept' });
    await poll(page);
    await page.getByText('Accepted by Edmonton', { exact: true }).waitFor();
    assert.equal(await page.locator('.cf-save').innerText(), 'Accepted');
  });

  await scenario('J05 current-case notification and list clicks both refresh after their event was already seen', async ({ page, id, returned, row, requests, hold }) => {
    await returned(); await poll(page);
    await patchStatus(page, id, 'submitted');
    const reading = hold('/cases/' + id);
    await page.getByRole('button', { name: /^Notifications(?:, \d+ new)?$/ }).click();
    await page.locator('.ac-note').filter({ hasText: 'returned' }).first().click();
    // An applicant notification opens that application's comments; the open case refreshes in place.
    await page.getByRole('heading', { name: 'Comments', exact: true }).waitFor();
    await reading.entered;
    await page.evaluate(() => { location.hash = '#/application'; });
    const refreshed = page.waitForResponse(response => new URL(response.url()).pathname === '/api/cases/' + id);
    reading.release(); await refreshed;
    await page.getByRole('button', { name: 'Resubmit to Edmonton', exact: true }).waitFor();
    await page.waitForTimeout(150);
    assert.equal(await page.evaluate(() => location.hash), '#/application', 'a finished notification refresh must not navigate over a later stage choice');
    await patchStatus(page, id, 'submitted');
    const before = requests.length;
    await row().click();
    await page.getByRole('button', { name: 'Resubmit to Edmonton', exact: true }).waitFor();
    assert.ok(requests.slice(before).some(r => r.path === '/me/applications'));
  });

  await scenario('J05 notification and current-list refresh preserve unsaved answers, in-flight saves and an unfinished evidence editor', async ({ page, officer, api, id, returned, hold, row, remote, requests }) => {
    await returned(); await poll(page);
    await page.getByRole('button', { name: 'Resubmit to Edmonton', exact: true }).waitFor();
    const saving = hold(`/cases/${id}/facts`, 'POST', false);
    await edit(page, 'REVISION C — synthetic unsaved local answer');
    await page.evaluate(() => {
      window.caseStore.dispatch({ type: 'editEvidenceDraft', itemId: 'synthetic-editor', patch: { document: 'Unfinished synthetic listing' } });
      window.saving = window.caseStore.saveDraft();
    });
    await saving.entered;
    const before = requests.length;
    await api(officer, `/cases/${id}/messages`, { body: 'Synthetic follow-up while the applicant is editing.' });
    await poll(page); await row().click();
    await page.getByText('Your local answers stay open. Save them before refreshing this application.', { exact: true }).waitFor();
    assert.equal(await localValue(page), 'REVISION C — synthetic unsaved local answer');
    assert.equal(await page.evaluate(() => window.caseStore.c.evidenceDrafts['synthetic-editor'].document), 'Unfinished synthetic listing');
    assert.equal(requests.slice(before).some(r => r.path === '/cases/' + id && r.method === 'GET'), false, 'a dirty draft was read for replacement');
    saving.release(); await page.evaluate(() => window.saving);
    assert.equal(legal(await remote()), 'REVISION C — synthetic unsaved local answer');
  });

  await scenario('J05 an older remote snapshot cannot overwrite a local answer saved while refresh is delayed', async ({ page, id, returned, hold, row, remote }) => {
    await returned(); await poll(page);
    await page.getByRole('button', { name: 'Resubmit to Edmonton', exact: true }).waitFor();
    const reading = hold('/cases/' + id);
    await row().click(); await reading.entered;
    await edit(page, 'REVISION D — synthetic saved during delayed read');
    assert.equal(await page.evaluate(() => window.caseStore.saveDraft()), id);
    const version = await acknowledged(page, id);
    reading.release();
    await page.getByText('Your local answers stay open. Save them before refreshing this application.', { exact: true }).waitFor();
    assert.equal(await localValue(page), 'REVISION D — synthetic saved during delayed read');
    assert.equal(await acknowledged(page, id), version, 'late GET regressed the acknowledged version');
    assert.equal(legal(await remote()), 'REVISION D — synthetic saved during delayed read');
  });

  await scenario('J05 a delayed selected-case refresh cannot replace a subsequently opened case', async ({ page, id, other, hold, row, open }) => {
    const reading = hold('/cases/' + id);
    await row().click(); await reading.entered;
    await open(other);
    reading.release();
    await page.waitForFunction(() => !document.querySelector('.cf-applist-note')?.textContent.includes('Opening'));
    assert.equal(await page.evaluate(() => window.caseStore.engineId), other);
    assert.equal(await page.evaluate(() => window.caseStore.c.title), fixture.ids.indexOf(other) >= 0 ? `SYNTHETIC refresh regression ${fixture.ids.indexOf(other)}` : 'invalid');
  });

  await scenario('J05 a late case read from opening one case cannot affect a newer open', async ({ page, id, other, hold, open, requests }) => {
    const reading = hold(`/cases/${id}`);
    await page.evaluate(id => { window.oldOpen = window.caseStore.openCase(id, 'contractor'); }, id);
    await reading.entered;
    await open(other); reading.release();
    assert.match(await page.evaluate(() => window.oldOpen), /changed while opening/);
    assert.equal(await page.evaluate(() => window.caseStore.engineId), other);
    assert.equal(await page.evaluate(() => window.caseStore.readSync().saved), true);
    assert.equal(requests.some(r => r.method === 'GET' && /\/(intake|identify)$/.test(r.path)), false, 'open must restore records embedded in one saved revision');
  });

  await scenario('J05 edits made while a different application opens keep the edited application selected', async ({ page, id, other, hold }) => {
    const reading = hold(`/cases/${other}`);
    await page.evaluate(id => { window.oldOpen = window.caseStore.openCase(id, 'contractor'); }, other);
    await reading.entered;
    await edit(page, 'REVISION E — synthetic edit during open');
    reading.release();
    assert.match(await page.evaluate(() => window.oldOpen), /changed while opening/);
    assert.equal(await page.evaluate(() => window.caseStore.engineId), id);
    assert.equal(await localValue(page), 'REVISION E — synthetic edit during open');
  });

  await scenario('J05 a newer application-list response wins over an older in-flight status read', async ({ page, id, returned, hold }) => {
    const reading = hold('/me/applications');
    await page.evaluate(() => { window.oldList = import('/src/calm/account.ts').then(a => a.refreshApplications()); });
    await reading.entered;
    await returned();
    await page.evaluate(async () => (await import('/src/calm/account.ts')).refreshApplications());
    reading.release(); await page.evaluate(() => window.oldList);
    assert.equal(await page.evaluate(async id => (await import('/src/calm/account.ts')).getAccountState().applications.find(a => a.id === id)?.status, id), 'returned');
  });

  await scenario('J05 a thread read receipt preserves its unread count without cancelling a newer returned status', async ({ page, context, api, id, returned, hold }) => {
    await returned();
    const reading = hold('/me/applications');
    await page.evaluate(() => { window.pendingList = import('/src/calm/account.ts').then(a => a.refreshApplications()); });
    await reading.entered;
    // Read through the mounted thread, so zero is an acknowledged server receipt as well as
    // a local patch. A newer list may legitimately replace a local-only synthetic zero.
    await page.evaluate(() => { location.hash = '#/comments'; });
    await page.locator('.cf-returned-msg').filter({ hasText: 'Please correct' }).waitFor();
    await page.evaluate(async () => { window.readAccount = (await import('/src/calm/account.ts')).getAccountState; });
    await page.waitForFunction(id => window.readAccount().applications.find(a => a.id === id)?.unread_messages === 0, id);
    const saved = (await api(context, '/me/applications', undefined, 'GET')).applications.find(a => a.id === id);
    assert.equal(saved.status, 'returned'); assert.equal(saved.unread_messages, 0);
    reading.release(); await page.evaluate(() => window.pendingList);
    const row = await page.evaluate(async id => (await import('/src/calm/account.ts')).getAccountState().applications.find(a => a.id === id), id);
    assert.equal(row.status, 'returned'); assert.equal(row.unread_messages, 0);
  });

  await scenario('J05 metadata-only revisions refresh obsolete gaps/professional guidance and invalidate the old check without replacing active cards', async ({ page, id, officer, context, api, requests }) => {
    await page.route(`**/api/cases/${id}/gaps`, route => route.fulfill({ json: [{
      id: 'synthetic-obsolete-professional', field: 'professional_requirement', section: 'D', severity: 'blocking', message: 'SYNTHETIC obsolete blocker',
    }] }), { times: 1 });
    await page.evaluate(async () => {
      window.caseStore.dispatch({ type: 'notePractice', value: true });
      await window.caseStore.requestCheck();
      window.cardsBeforeRefresh = window.caseStore.c.candidates;
      window.snapshotBeforeRefresh = window.caseStore.snapshotKey;
    });
    assert.equal(await page.evaluate(() => window.caseStore.engineGaps.some(g => g.id === 'synthetic-obsolete-professional')), true);
    await api(officer, `/review/${id}/claim`, {});
    await poll(page);
    await page.waitForFunction(() => window.caseStore.snapshotKey !== window.snapshotBeforeRefresh);
    const professional = await api(context, `/cases/${id}/professional`, undefined, 'GET');
    const result = await api(context, `/cases/${id}/section-d/issues`, undefined, 'GET');
    const issues = Array.isArray(result) ? result : result.items;
    const required = professional.required === 'yes' || issues.some(issue => issue.practice_of_engineering.value === true)
      ? true : professional.required === 'no' && issues.every(issue => issue.practice_of_engineering.value === false) ? false : 'unknown';
    const got = await page.evaluate(() => ({
      obsolete: window.caseStore.engineGaps.some(g => g.id === 'synthetic-obsolete-professional'),
      practice: window.caseStore.c.practiceOfEngineering, sameCards: window.caseStore.c.candidates === window.cardsBeforeRefresh,
      checkedAt: window.caseStore.checkedAt, status: window.caseStore.checkStatus,
    }));
    assert.equal(got.obsolete, false); assert.equal(got.practice, required);
    assert.equal(got.sameCards, true); assert.equal(got.checkedAt, undefined); assert.equal(got.status, 'stale');
    assert.equal(requests.some(r => r.method === 'POST' && r.path.endsWith('/section-d')), false, 'status refresh performed a Section D content write');
  });

  await scenario('J05 stored intake/identify are restored from a single embedded snapshot across an intervening remote run', async ({ page, id, context, hold, row, returned, api, requests }) => {
    await returned(); await poll(page);
    await page.getByRole('button', { name: 'Resubmit to Edmonton', exact: true }).waitFor();
    const reading = hold('/cases/' + id);
    await row().click(); await reading.entered;
    const newer = await api(context, `/cases/${id}/intake`, { text: 'SYNTHETIC a two storey office building.', model: false });
    assert.ok(newer.record);
    reading.release();
    await page.waitForFunction(() => !document.querySelector('.cf-applist-note')?.textContent.includes('Opening'));
    assert.equal(await page.evaluate(() => window.caseStore.c.intake), undefined, 'old saved facts were combined with a newer intake record');
    assert.equal(requests.some(r => r.method === 'GET' && /\/(intake|identify)$/.test(r.path)), false);
    await row().click();
    await page.waitForFunction(() => !!window.caseStore.c.intake);
    assert.deepEqual(await page.evaluate(() => window.caseStore.c.intake.factIds), newer.facts.map(f => f.id));
  });

  await scenario('J05 a remote revision change during derived reads is rejected once and recovered by an explicit selection', async ({ page, id, officer, api, row, hold, requests }) => {
    const version = await acknowledged(page, id);
    await api(officer, `/review/${id}/claim`, {});
    const reading = hold(`/cases/${id}/gaps`);
    await row().click(); await reading.entered;
    await api(officer, `/review/${id}/claim`, undefined, 'DELETE');
    reading.release();
    await page.getByText('The saved application changed during refresh. Select it again to refresh.', { exact: true }).waitFor();
    assert.equal(await acknowledged(page, id), version);
    const count = requests.length;
    await page.waitForTimeout(150);
    assert.equal(requests.length, count, 'a mixed revision started an automatic retry loop');
    await row().click();
    await page.evaluate(() => window.caseStore.refreshCurrentCase());
    assert.ok(await acknowledged(page, id) > version);
  });

  await scenario('J05 late application, case and notification responses cannot publish into a replacement account session', async ({ page, context, id, returned, hold, row, api, requests }) => {
    await returned(); await poll(page);
    await page.getByRole('button', { name: 'Resubmit to Edmonton', exact: true }).waitFor();
    await page.waitForFunction(() => window.caseStore.sectionCLookup.source === 'live');
    // Isolate the three reads below; the conversation receipt belongs to J06 and
    // also renews a session cookie. Finish it before deliberately replacing cookies.
    await page.evaluate(() => { location.hash = '#/comments'; });
    await page.locator('.cf-returned-msg').filter({ hasText: 'Please correct' }).waitFor();
    await page.evaluate(async () => { window.readAccount = (await import('/src/calm/account.ts')).getAccountState; });
    await page.waitForFunction(id => window.readAccount().applications.find(a => a.id === id)?.unread_messages === 0, id);
    await page.evaluate(() => { location.hash = '#/application'; });
    await page.evaluate(() => window.caseStore.refreshCurrentCase());
    const list = hold('/me/applications'), notifications = hold('/me/notifications'), reading = hold('/cases/' + id);
    await row().click(); await Promise.all([list.entered, reading.entered]);
    await page.evaluate(() => { window.oldNotifications = import('/src/calm/notifications/notifications.ts').then(n => n.loadNotifications()); });
    await notifications.entered;
    // This person owns no applications or notifications. The reviewer fixture legitimately receives
    // the earlier scenarios' authority-wide events, so it cannot prove an empty replacement account.
    await context.addCookies([{ name: 'batatis_session', value: fixture.replacement.cookie, url: base }]);
    await page.evaluate(async user => {
      (await import('/src/calm/account.ts')).setAccountState({ phase: 'signed-in', user, applications: [] });
      window.caseStore.resetToWho();
    }, fixture.replacement.user);
    list.release(); notifications.release(); reading.release();
    await page.evaluate(() => window.oldNotifications);
    await page.waitForTimeout(150);
    const state = await page.evaluate(async () => {
      const a = (await import('/src/calm/account.ts')).getAccountState();
      return { user: a.user.id, ids: a.applications?.map(a => a.id), caseId: window.caseStore.engineId, phase: window.caseStore.phase };
    });
    assert.equal(state.user, fixture.replacement.user.id);
    assert.deepEqual(state.ids, []);
    assert.equal(state.caseId, null); assert.equal(state.phase, 'who');
    const notificationsAfterReplacement = await page.evaluate(async () => (await import('/src/calm/notifications/notifications.ts')).getNotificationsState());
    assert.deepEqual(notificationsAfterReplacement.items, [], 'a late response republished the previous account notifications');
    await poll(page);
    const currentNotifications = await api(context, '/me/notifications', undefined, 'GET');
    assert.deepEqual(currentNotifications.notifications, [], 'the replacement fixture must have no notifications on the server');
    await page.getByRole('button', { name: /^Notifications/ }).click();
    assert.equal(await page.locator('.ac-note').count(), 0, 'the replacement session inherited old notifications');
  });

  await scenario('J05 a removed officer case clears action controls and offers refresh plus queue return', async ({ page, context, api, id }) => {
    await officerReady(page);
    const owner = await browser.newContext();
    try {
      await owner.addCookies([{ name: 'batatis_session', value: fixture.applicant.cookie, url: base }]);
      await api(owner, '/cases/' + id, undefined, 'DELETE');
      // Opening the review already picked it up; the page's next read finds it gone (missing and
      // unauthorized share one privacy-friendly answer).
      await page.reload();
      await page.getByText(/^This application isn’t available to you\./).waitFor();
      assert.equal(await page.getByRole('button', { name: /^(Accept|Ask for more|Refuse|Pick up|Resume review)$/ }).count(), 0);
      await page.getByRole('button', { name: 'Refresh', exact: true }).click();
      await page.getByRole('link', { name: 'Back to the queue', exact: true }).click();
      await page.waitForFunction(() => location.hash === '#/review');
      assert.equal((await context.request.get(base + '/cases/' + id)).status(), 404, 'privacy-friendly missing-case semantics preserved');
    } finally { await owner.close(); }
  }, 'reviewer');

  await scenario('J05 a delayed officer detail read cannot replace the case selected afterwards', async ({ page, id, other, hold }) => {
    await officerReady(page);
    const reading = hold('/cases/' + other);
    await page.evaluate(other => { location.hash = '#/review/' + other; }, other);
    await reading.entered;
    await page.evaluate(id => { location.hash = '#/review/' + id; }, id);
    await page.getByRole('button', { name: 'Application', exact: true }).click();
    await page.getByRole('article', { name: 'Submitted application' }).waitFor();
    await page.keyboard.press('Escape');
    reading.release();
    await page.waitForTimeout(100);
    const title = `SYNTHETIC refresh regression ${fixture.ids.indexOf(id)}`;
    assert.equal(await page.getByRole('heading').filter({ hasText: title }).count(), 1);
    assert.equal(await page.getByRole('heading').filter({ hasText: `SYNTHETIC refresh regression ${fixture.ids.indexOf(other)}` }).count(), 0);
  }, 'reviewer');

  await scenario('J12 officer same-case notification refreshes resubmission/questions without losing drafts or active dialogs', async ({ page, officer, api, id, requests, hold }) => {
    const owner = await browser.newContext();
    const colleague = await browser.newContext();
    try {
      await owner.addCookies([{ name: 'batatis_session', value: fixture.applicant.cookie, url: base }]);
      await api(colleague, '/auth/signup', { email: 'j12-colleague@example.test', name: 'Synthetic colleague', password: 'a long test password' });
      await api(colleague, '/auth/onboarding', { role: 'reviewer', authority: 'edmonton', access_code: 'officer-secret' });
      await officerReady(page);
      // Opening the review picked it up; deciding waits for its decision step.
      await decisionStep(page);
      const reviewing = await api(officer, `/cases/${id}`, undefined, 'GET');
      await api(officer, `/review/${id}/professional-requirement`, { expected_version: reviewing.version, required: true,
        scope: 'SYNTHETIC existing professional scope.', basis: 'SYNTHETIC human requirement record; no design approval.', reference: 'SYNTHETIC authority record' });
      // This fixture setup changed the content revision outside the mounted officer view.
      // Decision callers now pin their displayed version; read that saved determination first.
      await page.reload();
      const returnDialog = await openReturn(page);
      await returnDialog.getByRole('textbox').fill('Please clarify the synthetic wall assembly.');
      await page.getByRole('button', { name: 'Send and return', exact: true }).click();
      await page.getByText('Returned to the applicant. It comes back here when they resend it.', { exact: true }).waitFor();
      const draft = (await messagesDrawer(page)).getByRole('textbox', { name: 'Message to the applicant', exact: true });
      await draft.fill('Unsent officer draft must survive background updates.');
      await page.keyboard.press('Escape');
      // The composer lives in the Messages drawer and the review page holds its unsent text: each check
      // opens the drawer again and reads the real control, then closes it.
      const drafted = async () => {
        await messagesDrawer(page);
        const value = await draft.inputValue();
        await page.keyboard.press('Escape');
        return value;
      };
      await api(owner, `/cases/${id}/facts`, { field: 'codecheck.desc-wall', value: 'not-sure', kind: 'pointed', status: 'confirmed',
        source: { type: 'user_click', ref: 'Your code check answer', quote: 'Does your design replace the usual wall assembly?' } });
      const saved = await api(owner, `/cases/${id}`, undefined, 'GET');
      await api(owner, `/cases/${id}/submit`, { expected_version: saved.version });
      await poll(page);
      await page.getByRole('heading', { name: 'Resubmitted · submission 2', exact: true }).waitFor();
      await page.getByRole('button', { name: 'Resume review', exact: true }).waitFor();
      await page.locator('.ac-sheet-question strong').filter({ hasText: 'Does your design replace the usual wall assembly?' }).waitFor();
      assert.equal(await drafted(), 'Unsent officer draft must survive background updates.');
      const count = () => requests.filter(r => r.path === `/cases/${id}` && r.method === 'GET').length;
      const seen = count();
      await poll(page); await poll(page); await page.waitForTimeout(100);
      assert.equal(count(), seen, 'unchanged/read-marker polls must not reload detail');
      await page.getByRole('button', { name: /^Notifications/ }).click();
      await page.locator('.ac-note').filter({ hasText: 'resubmitted' }).first().click();
      for (let i = 0; i < 100 && count() <= seen; i++) await page.waitForTimeout(50);
      assert.ok(count() > seen, 'same-case notification click must refresh even when the event was already seen');
      assert.equal(await drafted(), 'Unsent officer draft must survive background updates.');
      await page.getByRole('button', { name: 'Resume review', exact: true }).click();
      await page.getByRole('region', { name: 'Resubmitted', exact: true }).waitFor({ state: 'detached' });
      await openReturn(page);
      await returnDialog.getByRole('textbox').fill('Unsent return decision must survive notifications.');
      const protectedCount = count();
      await api(colleague, `/cases/${id}/messages`, { body: 'Synthetic notice while return dialog is open.' });
      await poll(page); await page.waitForTimeout(100);
      assert.equal(await returnDialog.getByRole('textbox').inputValue(), 'Unsent return decision must survive notifications.');
      assert.equal(count(), protectedCount, 'defer the background snapshot while a decision is being edited');
      await page.getByRole('button', { name: 'Cancel', exact: true }).click();
      await messagesDrawer(page);
      await page.getByText('Synthetic notice while return dialog is open.', { exact: true }).waitFor();
      assert.equal(await draft.inputValue(), 'Unsent officer draft must survive background updates.');
      await page.keyboard.press('Escape');
      await page.getByRole('button', { name: /^(Record|Update) determination$/ }).click();
      await page.getByRole('textbox', { name: 'Scope reviewed', exact: true }).fill('Unsent determination scope.');
      const determining = count();
      await api(colleague, `/cases/${id}/messages`, { body: 'Synthetic notice while determination is open.' });
      await poll(page); await page.waitForTimeout(100);
      assert.equal(await page.getByRole('textbox', { name: 'Scope reviewed', exact: true }).inputValue(), 'Unsent determination scope.');
      assert.equal(count(), determining, 'defer while the professional determination dialog is being edited');
      await page.getByRole('button', { name: 'Cancel', exact: true }).click();
      await messagesDrawer(page);
      await page.getByText('Synthetic notice while determination is open.', { exact: true }).waitFor();
      assert.equal(await draft.inputValue(), 'Unsent officer draft must survive background updates.');
      await page.keyboard.press('Escape');
      const updating = hold(`/cases/${id}/identify/information-request`);
      await page.getByRole('button', { name: /^Notifications/ }).click();
      await page.locator('.ac-note').filter({ hasText: 'resubmitted' }).first().click();
      await updating.entered;
      await api(colleague, `/review/${id}/claim`, { take_over: true });
      updating.release();
      await page.getByText('The application changed while its review was loading. Refresh to read the current version.', { exact: false }).waitFor();
      assert.equal(await page.getByRole('button', { name: 'Accept', exact: true }).isDisabled(), true);
      assert.equal(await drafted(), 'Unsent officer draft must survive background updates.');
      await page.getByRole('button', { name: 'Refresh application', exact: true }).click();
      await page.locator('.rv-who').filter({ hasText: 'Synthetic colleague is reviewing this' }).waitFor();
      assert.equal(await drafted(), 'Unsent officer draft must survive background updates.');
    } finally { await owner.close(); await colleague.close(); }
  }, 'reviewer');

  await scenario('J12 background message snapshots retain acknowledged notices and read receipts', async ({ page, officer, api, id, hold }) => {
    await officerReady(page);
    // Opening the review picked it up; the thread and its composer are in the Messages drawer.
    await decisionStep(page);
    await messagesDrawer(page);
    const colleague = await browser.newContext();
    const receiptIds = [];
    page.on('request', request => {
      if (request.method() === 'POST' && new URL(request.url()).pathname === `/api/cases/${id}/messages/read`) {
        receiptIds.push(...(request.postDataJSON()?.message_ids ?? []));
      }
    });
    try {
      await api(colleague, '/auth/signup', { email: 'j12-message-colleague@example.test', name: 'SYNTHETIC notice colleague', password: 'a long test password' });
      await api(colleague, '/auth/onboarding', { role: 'reviewer', authority: 'edmonton', access_code: 'officer-secret' });
      const before = await api(officer, `/cases/${id}`, undefined, 'GET');
      const delayed = hold(`/cases/${id}/messages`);
      const trigger = await api(colleague, `/cases/${id}/messages`, { body: 'SYNTHETIC trigger an officer detail refresh.' });
      await poll(page);
      await delayed.entered; // The server has produced a thread snapshot without the next notice.
      const note = 'SYNTHETIC acknowledged notice sent while background refresh was in flight.';
      const draft = page.getByRole('textbox', { name: 'Message to the applicant', exact: true });
      await draft.fill(note);
      await page.getByRole('button', { name: 'Send', exact: true }).click();
      await page.locator('.ac-thread').getByText(note, { exact: true }).waitFor();
      assert.equal(await draft.inputValue(), '', 'the real successful POST cleared its composer');
      const receipt = hold(`/cases/${id}/messages/read`, 'POST', false);
      delayed.release();
      await receipt.entered;
      const visible = await page.locator('.ac-thread').getByText(note, { exact: true }).count();
      const stored = await api(officer, `/cases/${id}`, undefined, 'GET');
      console.log('J12_MESSAGE_REFRESH_RECEIPT', JSON.stringify({
        version_before: before.version, version_after: stored.version,
        persisted: stored.messages.some(message => message.body === note), visible_after_refresh: visible,
        composer: await draft.inputValue(),
      }));
      assert.equal(visible, 1, 'background detail refresh discarded an acknowledged notice from the mounted thread');
      assert.equal(stored.version, before.version, 'communication must not increment the content revision');

      // Hold another old GET while the actual displayed-message receipt completes.
      const staleReceipts = hold(`/cases/${id}/messages`);
      const nextNotice = await api(colleague, `/cases/${id}/messages`, { body: 'SYNTHETIC second colleague notice.' });
      await poll(page);
      await staleReceipts.entered;
      const triggerRow = page.locator('.ac-msg').filter({ has: page.getByText(trigger.body, { exact: true }) });
      assert.equal(await triggerRow.getByLabel('New', { exact: true }).count(), 1);
      receipt.release();
      await page.waitForFunction(text => Array.from(document.querySelectorAll('.ac-msg')).some(row =>
        row.textContent.includes(text) && !row.querySelector('[aria-label="New"]')), trigger.body);
      staleReceipts.release();
      await page.locator('.ac-thread').getByText(nextNotice.body, { exact: true }).waitFor();
      assert.equal(await triggerRow.getByLabel('New', { exact: true }).count(), 0, 'an old snapshot cannot undo an acknowledged read receipt');
      assert.equal(receiptIds.filter(messageId => messageId === trigger.id).length, 1, 'stale receipts must not mark the same displayed notice unread again');
      assert.equal(await page.locator('.ac-thread').getByText(note, { exact: true }).count(), 1);
      const remote = await api(officer, `/cases/${id}`, undefined, 'GET');
      assert.equal(remote.version, before.version);
      assert.ok(remote.messages.some(message => message.body === note));
    } finally { await colleague.close(); }
  }, 'reviewer');

  await scenario('J05 a late restore failure cannot clear a new applicant draft begun during reload', async ({ page, id, hold }) => {
    const reading = hold('/cases/' + id);
    await page.reload();
    await page.locator('.cf-app').waitFor();
    await reading.entered;
    await page.evaluate(() => {
      window.caseStore.beginEmpty('contractor');
      window.caseStore.dispatch({ type: 'setDescription', text: 'SYNTHETIC new draft begun during restore' });
    });
    reading.release();
    await page.waitForFunction(() => !document.querySelector('.cf-applist-note')?.textContent.includes('Opening'));
    assert.equal(await page.evaluate(() => window.caseStore.phase), 'case');
    assert.equal(await page.evaluate(() => window.caseStore.c.description), 'SYNTHETIC new draft begun during restore');
  });
  await scenario('J12 a new returned clarification becomes an editable card without reopening the case', async ({ page, id, officer, api, remote, requests }) => {
    const note = 'SYNTHETIC clarify the wall assembly for the officer.';
    const field = 'clarification.intake.assembly';
    await api(officer, `/review/${id}/claim`, {});
    const before = await remote();
    await api(officer, `/review/${id}/decision`, { outcome: 'return', expected_version: before.version,
      message: 'Please address the requested synthetic clarification.',
      items: [{ gap_id: 'intake.assembly', field, note }] });
    await poll(page);
    await page.evaluate(() => { location.hash = '#/comments'; });
    const link = page.locator('.cf-returned-items a').filter({ hasText: note });
    await page.locator('.cf-returned-items a[href="#/questions?focus=q-return-clarification.intake.assembly"]').waitFor();
    assert.equal(await link.getAttribute('href'), '#/questions?focus=q-return-clarification.intake.assembly');
    assert.match(await link.innerText(), /Still to clarify/);
    assert.equal(await page.getByText(note, { exact: true }).count(), 1, 'The current requested item appears once across banner and expanded history');
    await link.click();
    await page.getByRole('textbox', { name: note, exact: true }).fill('SYNTHETIC response: layers remain subject to responsible human review.');
    await page.getByRole('button', { name: 'OK', exact: true }).click();
    await page.evaluate(() => window.caseStore.saveDraft());
    assert.equal((await remote()).facts.filter(f => f.field === field).at(-1).value, 'SYNTHETIC response: layers remain subject to responsible human review.');
    assert.equal(requests.filter(r => r.method === 'POST' && /\/(identify|intake)/.test(r.path)).length, 0);
  });
} finally { await browser.close(); }
console.log(`Application refresh integration: ${passed} passed, ${failed} failed`);
process.exitCode = failed ? 1 : 0;
