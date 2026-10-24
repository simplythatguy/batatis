// Mounted SubmitPanel -> CaseProvider exact-save queue -> authenticated, disposable SQLite.
// Delay HTTP responses across case/account identities; no provider calls or browser captures.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE
  ? pathToFileURL(process.env.PLAYWRIGHT_MODULE).href : 'playwright-core');
const web = process.env.SYNC_WEB_BASE, base = process.env.SYNC_TEST_BASE;
for (const url of [web, base]) assert.match(url ?? '', /^http:\/\/(?:localhost|127\.0\.0\.1):(?:3000|8000)$/);
const fixture = JSON.parse(await readFile(process.env.SUBMIT_FIXTURES, 'utf8'));
const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
let next = 0, passed = 0, failed = 0;
const blocker = 'SYNTHETIC application A document is missing';
const blockingBody = { detail: { gaps: [{ id: 'synthetic-A-document', field: 'evidence.A.title', message: blocker }] } };
const edit = (page, value) => page.evaluate(value => window.caseStore.dispatch({
  type: 'setDetail', field: 'legalDescription', section: 'B', value,
}), value);
const paint = page => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));

async function scenario(name, run, { freshLogin = false } = {}) {
  const context = await browser.newContext();
  if (freshLogin) {
    const signedIn = await context.request.post(base + '/auth/login', { data: { email: 'submit@example.test', password: 'a long test password' } });
    assert.equal(signedIn.status(), 200);
  } else await context.addCookies([{ name: 'batatis_session', value: fixture.cookie, url: base, httpOnly: true, sameSite: 'Lax' }]);
  const page = await context.newPage();
  page.setDefaultTimeout(5000);
  const id = fixture.ids[next++], other = fixture.ids[next++];
  const errors = [], requests = [], gates = [], canceled = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('requestfailed', request => canceled.push(new URL(request.url()).pathname.replace(/^\/api/, '')));
  const remote = async (caseId = id) => {
    const response = await context.request.get(base + '/cases/' + caseId);
    assert.equal(response.status(), 200);
    return response.json();
  };
  await page.route('**/*', async route => {
    const url = new URL(route.request().url()), req = route.request();
    if (url.origin === base) return route.continue(); // Explicit loopback CORS/credentials coverage below.
    if (url.origin !== web) return route.abort();
    if (!url.pathname.startsWith('/api/')) return route.continue();
    const entry = { path: url.pathname.slice(4), method: req.method() };
    requests.push(entry);
    const gate = gates.find(g => !g.used && g.path === entry.path && entry.method === g.method);
    if (gate) gate.used = true;
    if (gate && !gate.after) { gate.ready(); await gate.wait; }
    try {
      if (gate?.raw) {
        // Node's fetch has no browser cookie jar: Set-Cookie reaches Chromium only on release.
        // route.fetch() may consume cookie headers eagerly, which would hide this response race.
        const response = await fetch(base + entry.path + url.search, {
          method: req.method(), headers: await req.allHeaders(), body: req.postData() ?? undefined,
        });
        const reply = { status: response.status, headers: Object.fromEntries(response.headers), body: Buffer.from(await response.arrayBuffer()) };
        entry.status = response.status;
        gate.ready(); await gate.wait;
        await route.fulfill(reply);
        return;
      }
      const response = gate?.status ? null : await route.fetch({ url: base + entry.path + url.search });
      entry.status = gate?.status || response.status();
      if (gate?.after) { gate.ready(); await gate.wait; }
      await route.fulfill(response ? { response } : { status: gate.status, json: gate.body });
    } catch (error) {
      if (!req.failure()) throw error;
    } finally { gate?.finish(); }
  });
  const hold = (path = `/cases/${id}/submit`, { method = 'POST', after = false, raw = false, status = 0, body = { detail: 'SYNTHETIC application A submit unavailable' } } = {}) => {
    let ready, release, finish;
    const entered = new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error(`Expected delayed ${method} ${path}`)), 5000);
      ready = () => { clearTimeout(timer); resolve(); };
    });
    const wait = new Promise(resolve => { release = resolve; });
    const done = new Promise(resolve => { finish = resolve; });
    gates.push({ path, method, after, raw, status, body, used: false, ready, release, wait, finish });
    return { entered, release, done };
  };
  const open = async (caseId = other) => {
    assert.equal(await page.evaluate(caseId => window.caseStore.openCase(caseId, 'contractor'), caseId), null);
    await page.evaluate(() => { location.hash = '#/application'; });
    await page.waitForFunction(caseId => window.caseStore.engineId === caseId
      && window.caseStore.sectionCLookup.source === 'live', caseId);
    await page.waitForFunction(async () => !(await import('/src/calm/account.ts')).getAccountState().loadingList);
    await page.getByRole('article', { name: 'Application preview' }).waitFor();
    await paint(page);
  };
  const submit = async (caseId = id, result = 'originalSubmit') => {
    await page.getByRole('button', { name: /^(?:Re)?submit to Edmonton$/i }).click();
    // Observe the existing shared promise after the real button dispatch. No test-only submit path.
    await page.evaluate(({ caseId, result }) => {
      window[result] = window.caseStore.submitDraft(caseId).then(() => 'submitted', error => error.message);
    }, { caseId, result });
  };
  const snapshot = () => page.evaluate(async () => {
    const { getAccountState } = await import('/src/calm/account.ts');
    const store = window.caseStore;
    return {
      id: store.engineId, data: store.c, status: store.applicationStatus, busy: store.submitting,
      save: store.saveStatus, sync: store.readSync(),
      application: getAccountState().applications.find(app => app.id === store.engineId),
      submit: document.querySelector('.cf-submit')?.textContent,
      preview: document.querySelector('[aria-label="Application preview"]')?.textContent,
      actions: [...document.querySelectorAll('[aria-label="Download"] button, [aria-label="Download"] a')]
        .map(el => [el.textContent, el.disabled ?? null, el.getAttribute('href')]),
    };
  });
  const lists = () => requests.filter(r => r.path === '/me/applications').length;
  const settle = async (result = 'originalSubmit') => {
    const value = await page.evaluate(result => window[result], result);
    await paint(page);
    return value;
  };
  try {
    await page.goto(web + '/tests/check.html');
    await page.waitForFunction(() => !!window.caseStore);
    await page.locator('.cf-app').waitFor();
    await open(id);
    await run({ page, context, id, other, remote, hold, open, submit, snapshot, settle, lists, requests, canceled });
    assert.deepEqual(errors, []);
    assert.equal(requests.some(r => r.method === 'POST' && /\/(identify|intake)/.test(r.path)), false);
    passed++; console.log('PASS', name);
  } catch (error) {
    failed++; console.error('FAIL', name, error.stack);
  } finally {
    for (const gate of gates) { gate.ready(); gate.release(); }
    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await context.close();
  }
}

try {
  await scenario('J11 existing submission blockers belong only to A, including after reopening A', async ({ page, id, hold, open, submit, settle }) => {
    const rejected = hold(undefined, { status: 409, body: blockingBody });
    await submit(); await rejected.entered; rejected.release(); await settle();
    await page.getByText(blocker, { exact: true }).waitFor();
    await open();
    assert.equal(await page.getByText(blocker, { exact: true }).count(), 0, 'A blockers leaked into B');
    await open(id);
    assert.equal(await page.getByText(blocker, { exact: true }).count(), 0, 'a new opening retained a prior submit attempt');
    assert.equal(await page.getByRole('button', { name: 'Resubmit to Edmonton', exact: true }).isEnabled(), true);
  });

  await scenario('J11 a delayed A save cannot add errors, status or actions to B', async ({ page, id, other, remote, hold, open, submit, snapshot, settle, lists, requests, canceled }) => {
    const saving = hold(`/cases/${id}/facts`);
    await edit(page, 'SYNTHETIC A edit before a delayed exact-save acknowledgement');
    await submit(); await saving.entered;
    await open();
    const before = await snapshot(), stored = await remote(other), count = lists();
    saving.release();
    assert.match(await settle(), /changed while submitting/);
    assert.deepEqual(await snapshot(), before);
    assert.deepEqual(await remote(other), stored);
    assert.equal(lists(), count, 'late A completion refreshed the list');
    assert.ok(canceled.includes(`/cases/${id}/facts`), 'changing cases must abort the submit save response');
    assert.equal(requests.some(r => r.path.endsWith('/submit')), false);
    assert.equal((await remote()).status, 'returned');
  });

  for (const status of [503, 409]) {
    await scenario(`J11 a delayed A submit error (${status}) cannot change B`, async ({ id, other, remote, hold, open, submit, snapshot, settle, lists }) => {
      const rejected = hold(undefined, { after: true, status, ...(status === 409 ? { body: blockingBody } : {}) });
      await submit(); await rejected.entered;
      await open();
      const before = await snapshot(), stored = await remote(other), count = lists();
      rejected.release(); await settle();
      assert.deepEqual(await snapshot(), before);
      assert.deepEqual(await remote(other), stored);
      assert.equal(lists(), count);
      assert.equal((await remote(id)).status, 'returned');
    });
  }

  await scenario('J11 late A success cannot publish in B; opening A again reads its submitted server state', async ({ page, id, other, remote, hold, open, submit, snapshot, settle, lists, canceled }) => {
    const sent = hold(undefined, { after: true });
    await submit(); await sent.entered;
    assert.equal((await remote()).status, 'submitted', 'the transition must be committed before its response is released');
    await open();
    const before = await snapshot(), stored = await remote(other), count = lists();
    sent.release(); await settle();
    assert.deepEqual(await snapshot(), before);
    assert.deepEqual(await remote(other), stored);
    assert.equal(lists(), count);
    assert.ok(canceled.includes(`/cases/${id}/submit`), 'changing cases must abort the submitted response');
    await open(id);
    await page.getByText('Sent to Edmonton', { exact: true }).waitFor();
    assert.equal(await page.getByRole('button', { name: 'Resubmit to Edmonton', exact: true }).count(), 0);
    await open();
    assert.equal(await page.getByRole('button', { name: 'Resubmit to Edmonton', exact: true }).isEnabled(), true);
  });

  await scenario('J11 reopening the same case invalidates an earlier submit error', async ({ page, id, remote, hold, open, submit, snapshot, settle, lists, canceled }) => {
    const sent = hold(undefined, { after: true, status: 503 });
    await submit(); await sent.entered;
    await open(id);
    assert.equal(await page.getByRole('button', { name: 'Resubmit to Edmonton', exact: true }).isEnabled(), true);
    const before = await snapshot(), count = lists();
    sent.release(); await settle();
    assert.deepEqual(await snapshot(), before);
    assert.equal(lists(), count);
    assert.ok(canceled.includes(`/cases/${id}/submit`), 'a new local generation of the same case must abort the prior request');
    assert.equal((await remote()).status, 'returned');
  });

  await scenario('J11 a new sign-in session cancels submit ownership even if it restores the same user object', async ({ page, id, remote, hold, open, submit, snapshot, settle, lists }) => {
    const sent = hold(undefined, { after: true });
    await submit(); await sent.entered;
    await page.evaluate(async () => {
      const { getAccountState, setAccountState } = await import('/src/calm/account.ts');
      const previous = getAccountState();
      setAccountState({ phase: 'signed-out', user: null });
      setAccountState(previous);
    });
    await paint(page);
    assert.equal(await page.evaluate(() => window.caseStore.submitting), false, 'the prior session still owns busy state');
    const before = await snapshot(), count = lists();
    sent.release(); assert.match(await settle(), /changed while submitting/);
    assert.deepEqual(await snapshot(), before);
    assert.equal(lists(), count);
    assert.equal(await page.getByRole('button', { name: 'Resubmit to Edmonton', exact: true }).isEnabled(), true);
    assert.equal(await page.evaluate(() => window.caseStore.engineId), id);
    assert.equal((await remote()).status, 'submitted');
    await open(id);
    await page.getByText('Sent to Edmonton', { exact: true }).waitFor();
  });

  await scenario('J11 leaving Application and returning keeps the same pending submission and truthful success', async ({ page, id, remote, hold, submit, settle, requests, canceled }) => {
    const sent = hold();
    await submit(); await sent.entered;
    await page.evaluate(() => { location.hash = '#/review'; });
    await page.getByRole('article', { name: 'Application preview' }).waitFor({ state: 'detached' });
    await page.evaluate(() => { location.hash = '#/application'; });
    assert.equal(await page.getByRole('button', { name: 'Submitting…', exact: true }).isDisabled(), true);
    assert.equal(canceled.includes(`/cases/${id}/submit`), false, 'Application navigation must keep its provider-owned submit alive');
    sent.release(); assert.equal(await settle(), 'submitted');
    await page.getByText('Sent to Edmonton', { exact: true }).waitFor();
    assert.equal((await remote()).status, 'submitted');
    assert.equal(requests.filter(r => r.path.endsWith('/submit')).length, 1);
    await page.reload();
    await page.getByText('Sent to Edmonton', { exact: true }).waitFor();
    assert.equal(await page.getByRole('button', { name: /^(?:Re)?submit to Edmonton$/i }).count(), 0);
  });

  await scenario('J11 settling A cannot clear B’s pending submit or replace its next actions', async ({ page, other, hold, open, submit, snapshot, settle, remote }) => {
    const sentA = hold(undefined, { after: true });
    await submit(); await sentA.entered;
    await open();
    const sentB = hold(`/cases/${other}/submit`);
    await submit(other, 'otherSubmit'); await sentB.entered;
    const before = await snapshot();
    sentA.release(); await settle();
    assert.deepEqual(await snapshot(), before);
    assert.equal(await page.getByRole('button', { name: 'Submitting…', exact: true }).isDisabled(), true);
    sentB.release(); assert.equal(await settle('otherSubmit'), 'submitted');
    await page.getByText('Sent to Edmonton', { exact: true }).waitFor();
    assert.equal((await remote(other)).status, 'submitted');
  });

  for (const replacement of ['submit@example.test', 'submit-replacement@example.test']) {
    for (const pending of ['submit', 'queued save', 'professional read', 'application list read', 'credential probe', 'code context read']) {
      await scenario(`J11 real-cookie ${pending}: a fresh ${replacement.startsWith('submit@') ? 'same-user' : 'different-user'} login survives a committed old response`, async ({ page, context, id, hold, submit, settle, canceled, requests }) => {
        await page.waitForLoadState('networkidle');
        const writing = pending === 'submit' || pending === 'queued save';
        const path = pending === 'application list read' ? '/me/applications'
          : pending === 'credential probe' ? '/auth/me'
          : pending === 'code context read' ? '/code/9.10.9.6.(1)/context'
          : `/cases/${id}/${pending === 'submit' ? 'submit' : pending === 'queued save' ? 'facts' : 'professional'}`;
        const delayed = hold(path, { method: writing ? 'POST' : 'GET', after: true, raw: true });
        if (pending === 'queued save') {
          await edit(page, 'SYNTHETIC committed save awaiting an old session acknowledgement');
          await page.evaluate(() => window.caseStore.dispatch({ type: 'setDetail', field: 'owner', section: 'A', value: 'SYNTHETIC later write that must not resume in a new login' }));
          await page.waitForFunction(() => window.caseStore.c.facts.some(f => f.value === 'SYNTHETIC later write that must not resume in a new login'));
          await page.evaluate(() => { window.earlierSave = window.caseStore.saveDraft(); });
          await delayed.entered;
        }
        if (writing) await submit();
        else await page.evaluate(async ({ id, pending }) => {
          let work;
          if (pending === 'professional read') work = (await import('/src/api/client.ts')).engine.professional(id);
          else if (pending === 'code context read') work = (await import('/src/api/codeLibrary.ts')).codeLibrary.context('9.10.9.6.(1)');
          else if (pending === 'credential probe') {
            const auth = await import('/src/api/engineAuth.ts');
            auth.resetProbe(); work = auth.probeAuth();
          } else work = (await import('/src/api/accounts.ts')).accounts.applications();
          window.originalSubmit = work.then(() => 'read', error => error.message);
        }, { id, pending });
        await delayed.entered;
        // Use an independent cookie jar to inspect server state without renewing browser cookies.
        const read = await fetch(base + '/cases/' + id, { headers: { Cookie: `batatis_session=${fixture.cookie}` } });
        assert.equal(read.status, 200);
        const committed = await read.json();
        assert.equal(committed.status, pending === 'submit' ? 'submitted' : 'returned');
        if (pending === 'queued save') assert.ok(committed.facts.some(f => f.value === 'SYNTHETIC committed save awaiting an old session acknowledgement'));
        const oldCookie = (await context.cookies(base)).find(cookie => cookie.name === 'batatis_session')?.value;
        await page.evaluate(async email => {
          await (await import('/src/calm/auth/useAuthGate.ts')).signIn(email, 'a long test password');
        }, replacement);
        const replacementCookie = (await context.cookies(base)).find(cookie => cookie.name === 'batatis_session')?.value;
        assert.ok(replacementCookie && replacementCookie !== oldCookie, 'a real login must rotate the actual cookie');
        await page.waitForFunction(async () => !(await import('/src/calm/account.ts')).getAccountState().loadingList);
        delayed.release(); await delayed.done; await settle();
        const actual = (await context.cookies(base)).find(cookie => cookie.name === 'batatis_session')?.value;
        const me = await context.request.get(base + '/auth/me');
        const user = me.ok() ? (await me.json()).user : null;
        // Never print session tokens, including on failure.
        assert.ok(actual === replacementCookie && me.status() === 200 && user?.email === replacement,
          `replacement cookie preserved: ${actual === replacementCookie}; /auth/me: ${me.status()}; replacement user preserved: ${user?.email === replacement}`);
        assert.ok(canceled.includes(path), 'the old authenticated request must be aborted, not merely ignored');
        assert.equal(requests.filter(r => r.path.endsWith('/submit')).length, pending === 'submit' ? 1 : 0);
        if (pending === 'queued save') {
          assert.equal(requests.filter(r => r.path === path).length, 1, 'an aborted multi-fact save resumed under the replacement cookie');
          const saved = await fetch(base + '/cases/' + id, { headers: { Cookie: `batatis_session=${fixture.cookie}` } });
          assert.deepEqual(await saved.json(), committed, 'the abandoned save continued writing after session replacement');
        }
        if (writing && replacement === 'submit@example.test') {
          await page.evaluate(id => window.caseStore.openCase(id, 'contractor'), id);
          if (pending === 'submit') {
            await page.getByText('Sent to Edmonton', { exact: true }).waitFor();
            assert.equal(await page.getByRole('button', { name: 'Resubmit to Edmonton', exact: true }).count(), 0);
          } else {
            assert.equal(await page.evaluate(() => window.caseStore.saveStatus), 'saved');
            assert.match(await page.getByRole('article', { name: 'Application preview' }).innerText(), /committed save awaiting an old session acknowledgement/);
            assert.equal(await page.getByRole('button', { name: 'Resubmit to Edmonton', exact: true }).isEnabled(), true);
          }
        }
      }, { freshLogin: true });
    }
  }

  await scenario('J11 provider unmount aborts a committed submit; Application navigation above does not', async ({ page, id, hold, submit, settle, canceled, lists }) => {
    const path = `/cases/${id}/submit`, delayed = hold(path, { after: true, raw: true });
    await submit(); await delayed.entered;
    const count = lists();
    await page.evaluate(() => window.unmountCase());
    assert.match(await settle(), /changed while submitting/);
    delayed.release(); await delayed.done;
    assert.ok(canceled.includes(path), 'provider teardown must abort the request even without an account change');
    assert.equal(lists(), count, 'a completed old submit started a refresh after provider teardown');
    const read = await fetch(base + '/cases/' + id, { headers: { Cookie: `batatis_session=${fixture.cookie}` } });
    assert.equal((await read.json()).status, 'submitted', 'aborting the response cannot undo a committed submission');
  }, { freshLogin: true });

  await scenario('J11 the shared engine lifetime preserves caller cancellation', async ({ page, id, hold, settle, canceled }) => {
    const path = `/cases/${id}/professional`, delayed = hold(path, { method: 'GET', after: true, raw: true });
    await page.evaluate(async id => {
      window.readController = new AbortController();
      window.originalSubmit = (await import('/src/api/client.ts')).engine.professional(id, window.readController.signal)
        .then(() => 'read', error => error.name);
    }, id);
    await delayed.entered;
    await page.evaluate(() => window.readController.abort());
    assert.equal(await settle(), 'AbortError');
    delayed.release(); await delayed.done;
    assert.ok(canceled.includes(path));
  });

  await scenario('J11 the shared engine lifetime retains its existing eight-second deadline', async ({ page, id, hold, settle, canceled }) => {
    const path = `/cases/${id}/professional`, delayed = hold(path, { method: 'GET', after: true, raw: true });
    await page.evaluate(async id => {
      window.originalSubmit = (await import('/src/api/client.ts')).engine.professional(id)
        .then(() => 'read', error => `${error.status}: ${error.detail}`);
    }, id);
    await delayed.entered;
    assert.equal(await settle(), '0: The engine did not answer in time.');
    delayed.release(); await delayed.done;
    assert.ok(canceled.includes(path));
  });

  await scenario('J11 credential probing and real cross-origin credential modes remain intact', async ({ page, id }) => {
    const results = await page.evaluate(async ({ base, id }) => {
      const auth = await import('/src/api/engineAuth.ts');
      const api = (await import('/src/api/client.ts')).createEngine(base);
      auth.setCredentialsMode('same-origin');
      const anonymous = await api.professional(id).then(() => 200, error => error.status);
      const account = await (await import('/src/api/accounts.ts')).accounts.me();
      auth.resetProbe();
      const probe = await auth.probeAuth();
      const included = await api.professional(id).then(() => 200, error => error.status);
      return { anonymous, email: account.email, probe: { credentials: probe.credentials, status: probe.status }, mode: auth.credentialsMode(), included };
    }, { base, id });
    assert.ok([401, 404].includes(results.anonymous), 'same-origin credentials must omit cookies on direct cross-origin engine calls');
    assert.equal(results.email, 'submit@example.test', 'same-origin accounts calls must retain their session');
    assert.deepEqual(results.probe, { credentials: true, status: 200 });
    assert.equal(results.mode, 'include');
    assert.equal(results.included, 200, 'credentialed CORS engine calls must keep working');
  });
} finally { await browser.close(); }
console.log(`Applicant submit isolation: ${passed} passed, ${failed} failed`);
process.exitCode = failed ? 1 : 0;
