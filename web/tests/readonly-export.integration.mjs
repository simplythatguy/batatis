// Actual applicant screens -> CaseProvider -> authenticated read-only API -> real PDF.
// No screenshots or rendered PDF claim: the integrating parent owns visual inspection.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE
  ? pathToFileURL(process.env.PLAYWRIGHT_MODULE).href : 'playwright-core');
const web = process.env.SYNC_WEB_BASE, base = process.env.SYNC_TEST_BASE;
for (const url of [web, base]) assert.match(url ?? '', /^http:\/\/127\.0\.0\.1:\d+$/);
const fixture = JSON.parse(await readFile(process.env.READONLY_FIXTURES, 'utf8'));
const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
let passed = 0, failed = 0;
// Thread-only reads may update communication metadata. Every content/workflow value,
// version, message body and retention date must still match exactly.
const withoutReceipts = ({ updated_at, ...saved }) => ({ ...saved, messages: saved.messages.map(({ read_by, ...message }) => message) });

async function scenario(name, key, run) {
  const context = await browser.newContext({ acceptDownloads: true });
  await context.addCookies([{ name: 'batatis_session', value: fixture.cookie, url: base, httpOnly: true, sameSite: 'Lax' }]);
  const page = await context.newPage();
  page.setDefaultTimeout(7000);
  const id = fixture.ids[key], requests = [], errors = [];
  let intercept = () => null;
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/*', async route => {
    const req = route.request(), url = new URL(req.url());
    if (url.origin !== web) return route.abort();
    if (!url.pathname.startsWith('/api/')) return route.continue();
    const entry = { path: url.pathname.slice(4), method: req.method(), body: req.postDataJSON() };
    requests.push(entry);
    const replacement = await intercept(entry);
    if (replacement) return route.fulfill(replacement);
    const response = await route.fetch({ url: base + entry.path + url.search });
    entry.status = response.status();
    await route.fulfill({ response });
  });
  const remote = async () => (await context.request.get(base + '/cases/' + id)).json();
  const open = async (path = '/application') => {
    await page.goto(web + '/tests/check.html');
    await page.waitForFunction(() => !!window.caseStore);
    await page.locator('.cf-app').waitFor(); // The mounted auth gate must finish before a case can be opened.
    const restoring = await page.evaluate(() => sessionStorage.getItem('batatis-open-application'));
    // A cold reload now restores the selected application itself. Do not race that
    // real caller with a second direct open from the harness.
    if (restoring === id) {
      await page.waitForFunction(id => window.caseStore.engineId === id && window.caseStore.phase === 'case', id);
      await page.waitForFunction(() => !document.querySelector('.cf-applist-note')?.textContent.includes('Opening'));
      await page.evaluate(path => { location.hash = '#' + path; }, path);
      return;
    }
    await page.evaluate(async ({ id, path }) => {
      const { refreshApplications } = await import('/src/calm/account.ts');
      await refreshApplications();
      const error = await window.caseStore.openCase(id, 'contractor');
      if (error) throw new Error(error);
      location.hash = '#' + path;
    }, { id, path });
    await page.waitForFunction(id => window.caseStore.engineId === id && window.caseStore.phase === 'case', id);
  };
  const nav = async path => {
    await page.evaluate(path => { location.hash = '#' + path; }, path);
    await page.evaluate(() => new Promise(requestAnimationFrame));
  };
  const check = async () => {
    const button = page.getByRole('button', { name: 'Check saved application', exact: true });
    assert.equal(await button.count(), 1, 'Locked application needs a reachable read-only check after reload');
    await button.click();
    await page.waitForFunction(() => ['ready', 'needs_answers', 'unavailable'].includes(window.caseStore.checkStatus));
  };
  const noWrites = () => {
    const receipts = requests.filter(r => r.method === 'POST' && r.path === `/cases/${id}/messages/read`);
    for (const receipt of receipts) {
      assert.deepEqual(Object.keys(receipt.body), ['message_ids']);
      assert.ok(receipt.body.message_ids.every(value => typeof value === 'string'));
    }
    assert.deepEqual(requests.filter(r => r.method !== 'GET' && /^\/cases(?:\/|$)/.test(r.path) && !r.path.endsWith('/export') && !receipts.includes(r)), [], 'Locked checks/navigation must never save content, identify or change workflow');
    assert.equal(requests.some(r => /\/(identify|intake)(\/|$)/.test(r.path) && r.method !== 'GET'), false);
  };
  try {
    await open();
    await run({ page, id, requests, context, open, nav, check, remote, noWrites, intercept: fn => { intercept = fn; } });
    assert.deepEqual(errors, []);
    passed++; console.log('PASS', name);
  } catch (error) {
    failed++; console.error('FAIL', name, error.stack);
  } finally {
    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await context.close();
  }
}

try {
  for (const status of ['accepted', 'submitted', 'in_review']) {
    await scenario(`J09 ${status} reload: read-only server check unlocks the real official PDF without a write`, status, async ({ page, open, check, remote, noWrites, nav }) => {
      // A new visit must establish server completeness; it must not inherit a prior draft check.
      await open();
      const before = await remote();
      assert.equal(await page.getByRole('button', { name: 'Official PDF', exact: true }).isDisabled(), true);
      await check();
      assert.equal(await page.getByRole('button', { name: 'Official PDF', exact: true }).isEnabled(), true);
      const downloading = page.waitForEvent('download');
      await page.getByRole('button', { name: 'Official PDF', exact: true }).click();
      const download = await downloading;
      assert.match(download.suggestedFilename(), /-scc-variance\.pdf$/);
      const bytes = await readFile(await download.path());
      assert.equal(bytes.subarray(0, 4).toString(), '%PDF');
      assert.ok(bytes.length > 10000);
      assert.match(await page.getByRole('complementary', { name: 'Download' }).innerText(), /does not.*(?:design complies|say the design)/i);
      await nav('/review');
      assert.equal(await page.getByRole('link', { name: /^Answer/ }).count(), 0);
      assert.equal(await page.getByRole('link', { name: 'Open your case and proof' }).count(), 0);
      await nav('/questions?focus=section-d');
      if (status === 'accepted') assert.equal(await page.getByText(/until the officer returns it/).count(), 0);
      await page.waitForTimeout(650);
      noWrites();
      assert.deepEqual(withoutReceipts(await remote()), withoutReceipts(before), 'PDF/check/navigation preserve all saved content, messages, provenance and version');
    });
  }

  for (const key of ['legacy-incomplete', 'professional-pending']) {
    await scenario(`J09 ${key}: current server blockers keep official export closed and show no impossible answer action`, key, async ({ page, check, nav, remote, noWrites, context, id }) => {
      const before = await remote();
      await check();
      assert.equal(await page.getByRole('button', { name: 'Official PDF', exact: true }).isDisabled(), true);
      await nav('/review');
      assert.equal(await page.getByRole('link', { name: /^Answer/ }).count(), 0);
      assert.equal(await page.getByRole('link', { name: 'Open your case and proof' }).count(), 0);
      assert.equal(await page.getByText(/almost there/i).count(), 0);
      assert.ok((await page.evaluate(() => window.caseStore.gaps)).some(g => g.severity === 'blocking'));
      assert.equal((await context.request.post(base + `/cases/${id}/export`, { data: { draft: false } })).status(), 409, 'The backend independently enforces every official-export gate');
      await nav('/application');
      const downloading = page.waitForEvent('download');
      await page.getByRole('button', { name: 'Download draft PDF', exact: true }).click();
      assert.match((await downloading).suggestedFilename(), /-DRAFT\.pdf$/);
      noWrites(); assert.deepEqual(withoutReceipts(await remote()), withoutReceipts(before));
    });
  }

  await scenario('J09 read-only completeness failure remains closed and has an explicit retry', 'accepted', async ({ page, check, intercept, noWrites }) => {
    intercept(entry => entry.path.endsWith('/gaps') ? { status: 503, json: { detail: 'SYNTHETIC gap service unavailable' } } : null);
    await check();
    assert.equal(await page.evaluate(() => window.caseStore.checkStatus), 'unavailable');
    assert.equal(await page.getByRole('button', { name: 'Official PDF', exact: true }).isDisabled(), true);
    intercept(() => null);
    await check();
    assert.equal(await page.getByRole('button', { name: 'Official PDF', exact: true }).isEnabled(), true);
    noWrites();
  });

  await scenario('J09 failed official export reports unavailable form without claiming a download', 'accepted', async ({ page, check, intercept, noWrites }) => {
    await check();
    intercept(entry => entry.path.endsWith('/export') ? { status: 503, json: { detail: 'SYNTHETIC missing form file' } } : null);
    await page.getByRole('button', { name: 'Official PDF', exact: true }).click();
    await page.getByText('The application PDF form is unavailable. Download a text record or try again later.', { exact: true }).waitFor();
    assert.equal(await page.getByRole('button', { name: 'Download again', exact: true }).count(), 0);
    noWrites();
  });

  await scenario('J09 saved-version change during completeness stays closed instead of publishing a mixed check', 'accepted', async ({ page, check, intercept, context, id, noWrites }) => {
    const snapshot = await (await context.request.get(base + '/cases/' + id)).json();
    let reads = 0;
    intercept(entry => entry.path === '/cases/' + id && entry.method === 'GET' && ++reads === 2
      ? { status: 200, json: { ...snapshot, version: snapshot.version + 1 } } : null);
    await check();
    assert.equal(await page.evaluate(() => window.caseStore.checkStatus), 'unavailable');
    assert.match(await page.evaluate(() => window.caseStore.checkDetail), /changed during the check/);
    assert.equal(await page.getByRole('button', { name: 'Official PDF', exact: true }).isDisabled(), true);
    noWrites();
  });

  await scenario('J09 official download rechecks the saved server blockers instead of trusting the earlier client result', 'accepted', async ({ page, check, intercept, requests, noWrites }) => {
    await check();
    intercept(entry => entry.path.endsWith('/gaps') ? { status: 200, json: { items: [{
      id: 'SYNTHETIC-new-required-item', field: 'risk_assessment', section: 'D', severity: 'blocking',
      message: 'SYNTHETIC newly reported risk requirement', submission_blocking: true,
    }] } } : null);
    await page.getByRole('button', { name: 'Official PDF', exact: true }).click();
    await page.getByText('The saved application has required administrative items. Review them before official export.', { exact: true }).waitFor();
    assert.equal(requests.some(r => r.path.endsWith('/export')), false);
    assert.equal(await page.getByRole('button', { name: 'Official PDF', exact: true }).isDisabled(), true);
    noWrites();
  });

  await scenario('J09 backend export rejection preserves its reasons and never reports a PDF download', 'accepted', async ({ page, check, intercept, noWrites }) => {
    await check();
    intercept(entry => entry.path.endsWith('/export') ? { status: 409, json: { detail: {
      message: 'export blocked', reasons: ['SYNTHETIC official form requirement remains unresolved'],
    } } } : null);
    await page.getByRole('button', { name: 'Official PDF', exact: true }).click();
    await page.getByText('The PDF was blocked. Review the current missing items below. The full response is in Technical detail.', { exact: true }).waitFor();
    await page.getByText('Technical detail', { exact: true }).click();
    assert.equal(await page.getByText('SYNTHETIC official form requirement remains unresolved', { exact: true }).count(), 1);
    assert.equal(await page.getByRole('button', { name: 'Download again', exact: true }).count(), 0);
    noWrites();
  });

  await scenario('J09 applicant-complete professional handoff directs Preview/Submit while official PDF stays closed', 'professional-pending-draft', async ({ page, nav, remote, context, id }) => {
    await page.getByRole('button', { name: 'Check now', exact: true }).click();
    await page.waitForFunction(() => window.caseStore.checkStatus === 'needs_answers');
    const holdNote = await page.locator('.cf-side-status p').first().innerText();
    assert.match(holdNote, /professional requirement/);
    assert.equal((await page.locator('.cf-side').innerText()).split(holdNote).length - 1, 1, 'A single professional hold must not repeat in the status, route and record note');
    await nav('/review');
    assert.equal(await page.getByRole('button', { name: 'Check my application', exact: true }).count(), 0, 'The acknowledged check remains current after navigation');
    assert.equal(await page.getByRole('heading', { name: 'Ready to submit for review.', exact: true }).count(), 1);
    assert.equal(await page.getByRole('link', { name: /^Answer/ }).count(), 0);
    assert.equal(await page.getByText('required items missing', { exact: true }).count(), 0);
    assert.match(await page.locator('.cf-metrics').innerText(), /Left for you\s+0\s*1 with the officer/);
    await page.getByRole('link', { name: /^Preview application/ }).click();
    assert.equal(await page.getByRole('button', { name: 'Official PDF', exact: true }).isDisabled(), true);
    assert.equal((await context.request.post(base + `/cases/${id}/export`)).status(), 409);
    const submit = page.getByRole('button', { name: 'Submit to Edmonton', exact: true });
    assert.equal(await submit.isEnabled(), true);
    await submit.click();
    await page.getByText('Sent to Edmonton', { exact: true }).waitFor();
    assert.equal((await remote()).status, 'submitted');
  });

  await scenario('J09 returned corrections keep the draft check/save/resubmit path', 'returned', async ({ page, nav, remote, requests }) => {
    await nav('/review');
    assert.equal(await page.getByRole('button', { name: 'Check my application', exact: true }).count(), 1);
    await nav('/application');
    await page.evaluate(() => window.caseStore.dispatch({ type: 'setDetail', field: 'legalDescription', section: 'B', value: 'SYNTHETIC J09 corrected lot' }));
    await page.evaluate(() => window.caseStore.requestCheck());
    assert.equal((await remote()).facts.at(-1).value, 'SYNTHETIC J09 corrected lot');
    await page.getByRole('button', { name: 'Resubmit to Edmonton', exact: true }).click();
    await page.getByText('Sent to Edmonton', { exact: true }).waitFor();
    assert.equal((await remote()).status, 'submitted');
    assert.ok(requests.some(r => r.path.endsWith('/facts') && r.method === 'POST'));
  });
} finally {
  await browser.close();
}
console.log(`${passed} passed, ${failed} failed`);
if (failed) process.exitCode = 1;
