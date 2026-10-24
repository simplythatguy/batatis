// Production officer/applicant callers -> authenticated HTTP -> disposable SQLite.
// Actual downloaded text/PDF bytes are checked. The parent owns visual/media inspection.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE
  ? pathToFileURL(process.env.PLAYWRIGHT_MODULE).href : 'playwright-core');
const web = process.env.SYNC_WEB_BASE, base = process.env.SYNC_TEST_BASE;
for (const url of [web, base]) assert.match(url ?? '', /^http:\/\/127\.0\.0\.1:\d+$/);
const fixture = JSON.parse(await readFile(process.env.REFUSAL_FIXTURES, 'utf8'));
const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
const REASON = 'SYNTHETIC refusal reason: the requested administrative attachment record was not provided.';
let passed = 0, failed = 0, index = 0;

async function bytes(download) {
  const stream = await download.createReadStream(), chunks = [];
  for await (const chunk of stream) chunks.push(chunk);
  return Buffer.concat(chunks);
}

async function scenario(name, run) {
  const owner = await browser.newContext({ acceptDownloads: true }), officer = await browser.newContext();
  const id = fixture.ids[index++], requests = [], errors = [];
  let intercept = () => null;
  for (const [context, actor] of [[owner, 'applicant'], [officer, 'reviewer']]) {
    await context.addCookies([{ name: 'batatis_session', value: fixture[actor].cookie, url: base, httpOnly: true, sameSite: 'Lax' }]);
    context.on('page', page => { page.setDefaultTimeout(8000); page.on('pageerror', error => errors.push(error.message)); });
    await context.route('**/*', async route => {
      const req = route.request(), url = new URL(req.url());
      if (url.origin !== web) return route.abort();
      if (!url.pathname.startsWith('/api/')) return route.continue();
      const entry = { actor, path: url.pathname.slice(4), method: req.method(), body: req.postDataJSON() };
      requests.push(entry);
      const replacement = await intercept(entry);
      if (replacement) return route.fulfill(replacement);
      const response = await route.fetch({ url: base + entry.path + url.search });
      entry.status = response.status();
      await route.fulfill({ response });
    });
  }
  const ap = await owner.newPage(), op = await officer.newPage();
  const api = async (context, path, data, method = 'POST', status = 200) => {
    const result = await context.request.fetch(base + path, { method, ...(data === undefined ? {} : { data }) });
    assert.equal(result.status(), status, `${method} ${path}: ${await result.text()}`);
    return result.status() === 204 ? null : result.json();
  };
  const remote = () => api(owner, '/cases/' + id, undefined, 'GET');
  const applicant = async () => {
    await ap.goto(web + '/tests/check.html#/application');
    await ap.waitForFunction(() => !!window.caseStore);
    await ap.locator('.cf-app').waitFor();
    await ap.evaluate(async id => {
      await (await import('/src/calm/account.ts')).refreshApplications();
      const error = await window.caseStore.openCase(id, 'contractor');
      if (error) throw new Error(error);
    }, id);
    await ap.waitForFunction(id => window.caseStore.engineId === id, id);
  };
  const reviewer = async () => {
    await op.goto(web + '/tests/check.html#/review/' + id);
    await op.getByRole('article', { name: 'Submitted application' }).waitFor();
    await op.getByRole('button', { name: 'Refuse application', exact: true }).waitFor();
  };
  const begin = async () => {
    await api(owner, `/cases/${id}/submit`, {});
    await api(officer, `/review/${id}/claim`, {});
  };
  const send = async (reason = REASON) => {
    await op.getByRole('button', { name: 'Refuse application', exact: true }).click();
    const dialog = op.getByRole('dialog', { name: 'Refuse this application?' });
    await dialog.getByRole('textbox', { name: 'Reason for refusal' }).fill(reason);
    await dialog.getByRole('button', { name: 'Record refusal', exact: true }).click();
    return dialog;
  };
  const downloadText = async () => {
    const pending = ap.waitForEvent('download');
    await ap.getByRole('button', { name: 'Download a text record', exact: true }).click();
    const download = await pending;
    assert.match(download.suggestedFilename(), /-text-record\.txt$/);
    return (await bytes(download)).toString('utf8');
  };
  try {
    await run({ owner, officer, ap, op, id, api, remote, applicant, reviewer, begin, send, requests,
      downloadText, setIntercept: callback => { intercept = callback; } });
    assert.deepEqual(errors, []);
    assert.equal(requests.some(r => r.method === 'POST' && /\/(identify|intake|relevance|assist)(\/|$)/.test(r.path)), false);
    passed++; console.log('PASS', name);
  } catch (error) {
    failed++; console.error('FAIL', name, error.stack);
    console.error('Receipt', await ap.locator('body').innerText().catch(() => ''),
      await op.locator('body').innerText().catch(() => ''), requests.slice(-8));
  } finally {
    await owner.unrouteAll({ behavior: 'ignoreErrors' });
    await officer.unrouteAll({ behavior: 'ignoreErrors' });
    await owner.close(); await officer.close();
  }
}

try {
  await scenario('refusal survives both reloads, notification refresh, queue filtering and actual saved review/text/PDF downloads', async ({ owner, officer, ap, op, id, api, remote, applicant, reviewer, begin, requests, downloadText }) => {
    await begin();
    await api(officer, `/review/${id}/decision`, { outcome: 'return', message: 'SYNTHETIC previous return requesting the attachment record.' });
    await api(officer, `/cases/${id}/messages`, { body: 'SYNTHETIC previous officer notice.' }, 'POST', 201);
    await api(owner, `/cases/${id}/submit`, {});
    await api(officer, `/review/${id}/claim`, {});
    await applicant(); await reviewer();
    await op.getByRole('button', { name: 'Refuse application', exact: true }).click();
    const dialog = op.getByRole('dialog', { name: 'Refuse this application?' });
    await dialog.getByRole('button', { name: 'Record refusal', exact: true }).click();
    await dialog.getByText('Write a reason of at least 10 characters.', { exact: true }).waitFor();
    assert.equal(requests.filter(r => r.path.endsWith('/decision')).length, 0);
    await dialog.getByRole('textbox', { name: 'Reason for refusal' }).fill(REASON);
    const before = await remote();
    await dialog.getByRole('button', { name: 'Record refusal', exact: true }).click();
    await op.getByText('Administrative refusal recorded. This application is closed and read-only.', { exact: true }).waitFor();
    const request = requests.find(r => r.path.endsWith('/decision'));
    assert.deepEqual(request.body, { outcome: 'refuse', message: REASON, expected_version: before.version });
    let saved = await remote();
    assert.equal(saved.status, 'refused');
    assert.deepEqual(saved.decision_history.map(d => d.outcome), ['return', 'refuse']);
    assert.equal(saved.submission_number, 2);
    await op.reload();
    await op.locator('.ac-thread').getByText(new RegExp(REASON)).waitFor();
    assert.equal(await op.getByRole('button', { name: 'Refuse application', exact: true }).count(), 0);
    assert.equal(await op.getByRole('button', { name: 'Accept as complete', exact: true }).count(), 0);
    await ap.evaluate(async () => (await import('/src/calm/notifications/notifications.ts')).loadNotifications());
    await ap.locator('.cf-save-label').getByText('Refused · read-only', { exact: true }).waitFor();
    await ap.locator('.cf-refused').getByText(new RegExp(REASON)).waitFor();
    await ap.reload(); await ap.locator('.cf-refused').getByText(new RegExp(REASON)).waitFor();
    assert.equal(await ap.getByRole('button', { name: /^(Submit|Resubmit) to / }).count(), 0);
    assert.equal(await ap.getByRole('button', { name: 'Reply', exact: true }).count(), 0);
    // A notice arriving after reload must be in the download, even without refreshing the thread.
    await api(officer, `/cases/${id}/messages`, { body: 'SYNTHETIC final notice arriving after applicant reload.' }, 'POST', 201);
    saved = await remote();
    const text = await downloadText();
    for (const fragment of ['Administrative review record', `Application ID: ${id}`, 'Status: refused', REASON,
      saved.decision.by_name, saved.decision.at, 'Submission 2', 'in_review → refused']) assert.ok(text.includes(fragment), fragment);
    for (const decision of saved.decision_history) {
      assert.ok(text.includes(decision.message)); assert.ok(text.includes(decision.by_name)); assert.ok(text.includes(decision.at));
    }
    for (const message of saved.messages) assert.ok(text.includes(message.body), 'Missing downloaded message: ' + message.body);
    assert.ok(text.includes('Keep original supporting attachments separately.'));
    assert.equal(requests.some(r => r.actor === 'applicant' && r.method !== 'GET'
      && !r.path.endsWith('/messages/read') && !r.path.endsWith('/notifications/read') && r.path !== '/section-c'), false);
    await ap.getByRole('button', { name: 'Check saved application', exact: true }).click();
    await ap.waitForFunction(() => window.caseStore.readSync().reviewed);
    for (const label of ['Download draft PDF', 'Official PDF']) {
      const pending = ap.waitForEvent('download');
      await ap.getByRole('button', { name: label, exact: true }).click();
      const pdf = await bytes(await pending);
      assert.equal(pdf.subarray(0, 4).toString(), '%PDF'); assert.ok(pdf.length > 1000);
    }
    assert.equal((await remote()).version, saved.version);
    for (const path of ['#/questions', '#/references', '#/code/9.10.9.16.', '#/']) {
      await ap.evaluate(path => { location.hash = path; }, path);
      if (path === '#/questions') await ap.getByText('Your saved answers are read-only.', { exact: true }).waitFor();
      if (path === '#/references') {
        await ap.getByRole('heading', { name: 'Section C', exact: true }).waitFor();
        assert.equal(await ap.locator('#section-c-search').count(), 0);
        const choice = ap.locator('#sentence-decision');
        if (await choice.count()) assert.equal(await choice.isDisabled(), true);
      }
      if (path.startsWith('#/code/')) {
        await ap.getByText('Your saved application is read-only. You can still read the code.', { exact: true }).waitFor();
        assert.equal(await ap.getByRole('button', { name: 'Add to my application' }).count(), 0);
      }
      if (path === '#/') await ap.getByText(/The officer recorded an administrative refusal/).waitFor();
    }
    await op.evaluate(() => { location.hash = '#/review'; });
    await op.getByRole('heading', { name: /Review queue/ }).waitFor();
    await op.getByRole('button', { name: /^Refused 1$/ }).click();
    const row = op.getByRole('row').filter({ has: op.getByRole('link', { name: saved.title, exact: true }) });
    await row.getByText('Refused', { exact: true }).waitFor();
    assert.equal(await row.getByRole('button', { name: 'Start reviewing', exact: true }).count(), 0);
  });

  await scenario('stale officer refusal is rejected without losing the written reason; explicit refresh permits a current decision', async ({ officer, op, id, api, remote, reviewer, begin, send }) => {
    await begin(); await reviewer();
    const before = await remote();
    await api(officer, `/review/${id}/claim`, undefined, 'DELETE', 204);
    await api(officer, `/review/${id}/claim`, {});
    const dialog = await send();
    await dialog.getByRole('alert').getByText(/The application changed/).waitFor();
    assert.equal((await remote()).decision, null);
    assert.equal(await dialog.getByRole('textbox', { name: 'Reason for refusal' }).inputValue(), REASON);
    await dialog.getByRole('button', { name: 'Refresh application', exact: true }).click();
    // J12 refreshes the saved revision in place and keeps the active reason dialog.
    await op.waitForFunction(() => Array.from(document.querySelectorAll('button'))
      .some(button => button.textContent === 'Refuse application' && !button.disabled));
    assert.equal(await dialog.isVisible(), true);
    assert.equal(await dialog.getByRole('textbox', { name: 'Reason for refusal' }).inputValue(), REASON);
    await dialog.getByRole('button', { name: 'Record refusal', exact: true }).click();
    await op.getByText('Administrative refusal recorded. This application is closed and read-only.', { exact: true }).waitFor();
    const after = await remote();
    assert.equal(after.status, 'refused'); assert.equal(after.version, before.version + 3);
    assert.equal(after.decision_history.filter(d => d.outcome === 'refuse').length, 1);
  });

  await scenario('a failed fresh review-record read offers retry and never downloads an incomplete local-only record', async ({ ap, op, id, remote, applicant, reviewer, begin, send, downloadText, setIntercept }) => {
    await begin(); await reviewer(); await send();
    await op.getByText('Administrative refusal recorded. This application is closed and read-only.', { exact: true }).waitFor();
    await applicant(); await ap.locator('.cf-refused').waitFor();
    let downloads = 0; ap.on('download', () => downloads++);
    setIntercept(r => r.actor === 'applicant' && r.method === 'GET' && r.path === '/cases/' + id
      ? { status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'SYNTHETIC saved review record temporarily unavailable.' }) } : null);
    await ap.getByRole('button', { name: 'Download a text record', exact: true }).click();
    await ap.getByText(/Review record not downloaded.*SYNTHETIC saved review record temporarily unavailable/).waitFor();
    assert.equal(downloads, 0);
    setIntercept(() => null);
    const text = await downloadText(), saved = await remote();
    assert.equal(downloads, 1); assert.ok(text.includes(REASON)); assert.ok(text.includes(saved.decision.at));
  });
} finally {
  await browser.close();
}
console.log(JSON.stringify({ passed, failed }));
process.exitCode = failed ? 1 : 0;
