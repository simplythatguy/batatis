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
  // The officer's review shows one step at a time: the decision is the last step (or, when no package
  // review can run, the panel under its notice). The submitted application sits in the header drawer.
  const decision = async () => {
    const refuse = op.getByRole('button', { name: 'Refuse', exact: true });
    const step = op.getByRole('navigation', { name: 'Review steps' }).getByRole('button', { name: /: Decide\b/ });
    await refuse.or(step).first().waitFor();
    if (!await refuse.isVisible()) await step.click();
    await refuse.waitFor();
  };
  const reviewer = async () => {
    await op.goto(web + '/tests/check.html#/review/' + id);
    await op.getByRole('button', { name: 'Application', exact: true }).click();
    await op.getByRole('article', { name: 'Submitted application' }).waitFor();
    await op.keyboard.press('Escape');
    await decision();
  };
  const begin = async () => {
    await api(owner, `/cases/${id}/submit`, {});
    await api(officer, `/review/${id}/claim`, {});
  };
  const send = async (reason = REASON) => {
    await op.getByRole('button', { name: 'Refuse', exact: true }).click();
    const dialog = op.getByRole('dialog', { name: 'Refuse the variance' });
    await dialog.getByRole('textbox', { name: 'Your reasons' }).fill(reason);
    await dialog.getByRole('button', { name: 'Refuse', exact: true }).click();
    return dialog;
  };
  // The officer's note once a refusal is recorded (its reasons and the appeal notice went to the applicant).
  const refusedNote = () => op.getByText(/^Refusal sent to .+ with the appeal notice\. This application is closed\.$/).waitFor();
  const downloadText = async () => {
    const pending = ap.waitForEvent('download', { predicate: download => download.suggestedFilename().endsWith('-text-record.txt') });
    await ap.getByRole('button', { name: 'Download a text record', exact: true }).click();
    const download = await pending;
    assert.match(download.suggestedFilename(), /-text-record\.txt$/);
    return (await bytes(download)).toString('utf8');
  };
  try {
    await run({ owner, officer, ap, op, id, api, remote, applicant, reviewer, begin, send, requests,
      downloadText, refusedNote, setIntercept: callback => { intercept = callback; } });
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
  await scenario('refusal survives both reloads, notification refresh, queue filtering and actual saved review/text/PDF downloads', async ({ owner, officer, ap, op, id, api, remote, applicant, reviewer, begin, requests, downloadText, refusedNote }) => {
    await begin();
    await api(officer, `/review/${id}/decision`, { outcome: 'return', message: 'SYNTHETIC previous return requesting the attachment record.' });
    await api(officer, `/cases/${id}/messages`, { body: 'SYNTHETIC previous officer notice.' }, 'POST', 201);
    await api(owner, `/cases/${id}/submit`, {});
    await api(officer, `/review/${id}/claim`, {});
    await applicant(); await reviewer();
    await op.getByRole('button', { name: 'Refuse', exact: true }).click();
    const dialog = op.getByRole('dialog', { name: 'Refuse the variance' });
    await dialog.getByRole('button', { name: 'Refuse', exact: true }).click();
    await dialog.getByText('Write your reasons for the refusal.', { exact: true }).waitFor();
    assert.equal(requests.filter(r => r.path.endsWith('/decision')).length, 0);
    await dialog.getByRole('textbox', { name: 'Your reasons' }).fill(REASON);
    const before = await remote();
    await dialog.getByRole('button', { name: 'Refuse', exact: true }).click();
    await refusedNote();
    const request = requests.find(r => r.path.endsWith('/decision'));
    // The displayed version, the officer's own reasons verbatim with the appeal notice below them, no correction list.
    assert.deepEqual(Object.keys(request.body).sort(), ['expected_version', 'message', 'outcome']);
    assert.equal(request.body.outcome, 'refuse');
    assert.equal(request.body.expected_version, before.version);
    assert.ok(request.body.message.includes(REASON));
    assert.match(request.body.message, /Safety Codes Council within 30 days/);
    let saved = await remote();
    assert.equal(saved.status, 'refused');
    assert.deepEqual(saved.decision_history.map(d => d.outcome), ['return', 'refuse']);
    assert.equal(saved.submission_number, 2);
    await op.reload();
    await op.getByRole('button', { name: /^Messages/ }).click();
    await op.locator('.ac-thread').getByText(new RegExp(REASON)).waitFor();
    await op.keyboard.press('Escape');
    assert.equal(await op.getByRole('button', { name: 'Refuse', exact: true }).count(), 0);
    assert.equal(await op.getByRole('button', { name: 'Accept', exact: true }).count(), 0);
    await ap.evaluate(async () => (await import('/src/calm/notifications/notifications.ts')).loadNotifications());
    await ap.locator('.cf-save-label').getByText('Refused · read-only', { exact: true }).waitFor();
    // The full decision is on the comments page; the stage keeps a one-line notice that links there.
    await ap.evaluate(() => { location.hash = '#/comments'; });
    await ap.locator('.cf-refused').getByText(new RegExp(REASON)).waitFor();
    await ap.reload(); await ap.locator('.cf-refused').getByText(new RegExp(REASON)).waitFor();
    await ap.evaluate(() => { location.hash = '#/application'; });
    await ap.getByRole('region', { name: 'Application form' }).waitFor();
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
    assert.deepEqual(requests.filter(r => r.actor === 'applicant' && r.method !== 'GET'
      && !r.path.endsWith('/messages/read') && !r.path.endsWith('/notifications/read') && r.path !== '/section-c'
      && !(r.path === `/cases/${id}/export` && r.body?.draft === true)), [], 'only read receipts, Section C lookup and the draft PDF projection are allowed');
    await ap.getByRole('button', { name: 'Check saved application', exact: true }).click();
    await ap.waitForFunction(() => window.caseStore.readSync().reviewed);
    for (const label of ['Download draft PDF', 'Official PDF']) {
      const filename = `${id}-scc-variance${label === 'Download draft PDF' ? '-DRAFT' : ''}.pdf`;
      const pending = ap.waitForEvent('download', { predicate: download => download.suggestedFilename() === filename });
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
    const row = op.locator('a.rq-row').filter({ hasText: saved.title });
    await row.getByText('Refused', { exact: true }).waitFor();
    assert.equal(await row.getByText('Pick up', { exact: true }).count(), 0, 'a refused file is never picked up again');
  });

  await scenario('stale officer refusal is rejected without losing the written reason; explicit refresh permits a current decision', async ({ officer, op, id, api, remote, reviewer, begin, send, refusedNote }) => {
    await begin(); await reviewer();
    const before = await remote();
    await api(officer, `/review/${id}/claim`, undefined, 'DELETE', 204);
    await api(officer, `/review/${id}/claim`, {});
    const dialog = await send();
    await dialog.getByRole('alert').getByText(/The application changed/).waitFor();
    assert.equal((await remote()).decision, null);
    assert.equal(await dialog.getByRole('textbox', { name: 'Your reasons' }).inputValue(), REASON);
    await dialog.getByRole('button', { name: 'Refresh', exact: true }).click();
    // J12 refreshes the saved revision in place and keeps the active reason dialog (the Refuse choice
    // behind it is disabled while the read is in flight).
    await op.waitForFunction(() => { const refuse = document.querySelector('button[aria-label="Refuse"]'); return Boolean(refuse && !refuse.disabled); });
    assert.equal(await dialog.isVisible(), true);
    assert.equal(await dialog.getByRole('textbox', { name: 'Your reasons' }).inputValue(), REASON);
    await dialog.getByRole('button', { name: 'Refuse', exact: true }).click();
    await refusedNote();
    const after = await remote();
    assert.equal(after.status, 'refused'); assert.equal(after.version, before.version + 3);
    assert.equal(after.decision_history.filter(d => d.outcome === 'refuse').length, 1);
  });

  await scenario('a failed fresh review-record read offers retry and never downloads an incomplete local-only record', async ({ ap, op, id, remote, applicant, reviewer, begin, send, downloadText, refusedNote, setIntercept }) => {
    await begin(); await reviewer(); await send();
    await refusedNote();
    await applicant();
    await ap.evaluate(() => { location.hash = '#/comments'; });
    await ap.locator('.cf-refused').waitFor();
    await ap.evaluate(() => { location.hash = '#/application'; });
    await ap.getByRole('region', { name: 'Application form' }).waitFor();
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
