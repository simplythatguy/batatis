// Real CaseProvider -> SubmitPanel -> sync -> authenticated engine, with delayed HTTP saves.
// All cases and attached storage bytes are synthetic administrative fixtures, not evidence.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE
  ? pathToFileURL(process.env.PLAYWRIGHT_MODULE).href : 'playwright-core');
const web = process.env.SYNC_WEB_BASE, base = process.env.SYNC_TEST_BASE;
assert.equal(web, 'http://localhost:3000');
assert.equal(base, 'http://localhost:8000');
const fixture = JSON.parse(await readFile(process.env.SUBMIT_FIXTURES, 'utf8'));
const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
let next = 0, passed = 0, failed = 0;
const B = 'REVISION B — synthetic saved lot', C = 'REVISION C — synthetic latest lot';
const action = (value) => ({ type: 'setDetail', field: 'legalDescription', section: 'B', value });
const legal = (c) => [...(c.facts ?? [])].reverse().find(f => ['legalDescription', 'legal_description'].includes(f.field))?.value;
// The application page shows the actual filled PDF (FormViewer), filled from the open case's values:
// what is displayed is the store's case, the same values the drawn preview used to render.
const shown = async page => String(await page.evaluate(() => [...window.caseStore.c.facts].reverse().find(f => f.field === 'legalDescription')?.value ?? ''));

async function scenario(name, run, fixtureId) {
  const context = await browser.newContext();
  await context.addCookies([{ name: 'batatis_session', value: fixture.cookie, url: base, httpOnly: true, sameSite: 'Lax' }]);
  const page = await context.newPage();
  page.setDefaultTimeout(8000);
  const errors = [], requests = [];
  page.on('pageerror', e => errors.push(e.message));
  const id = fixtureId ?? fixture.ids[next++];
  const gates = [];
  const remote = async () => {
    const response = await context.request.get(base + '/cases/' + id);
    return response.ok() ? response.json() : { status: response.status() };
  };
  await page.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.origin !== web) return route.abort();
    if (!url.pathname.startsWith('/api/')) return route.continue();
    const req = route.request();
    const entry = { path: url.pathname.slice(4), method: req.method(), ack: false, body: req.postDataJSON() };
    requests.push(entry);
    const gate = gates.find(gate => gate.matches(entry) && !gate.entered);
    if (gate) {
      gate.entered = true;
      gate.ready();
      await gate.wait;
      if (gate.status) {
        entry.status = gate.status;
        return route.fulfill({ status: gate.status, json: { detail: gate.detail } });
      }
    }
    const response = await route.fetch({ url: base + entry.path + url.search });
    entry.status = response.status(); entry.ack = response.ok();
    await route.fulfill({ response });
  });
  const hold = (suffix = '/facts', status = 0, detail = 'Synthetic save unavailable') => {
    let ready, release;
    const entered = new Promise(resolve => { ready = resolve; });
    const wait = new Promise(resolve => { release = resolve; });
    gates.push({ entered: false, matches: r => r.method === 'POST' && r.path === `/cases/${id}${suffix}`, ready, wait, status, detail });
    return { entered, release };
  };
  const submits = () => requests.filter(r => r.path.endsWith('/submit'));
  const edit = async value => {
    await page.evaluate(a => window.caseStore.dispatch(a), action(value));
    await page.waitForFunction(v => window.caseStore.c.facts.some(f => f.field === 'legalDescription' && f.value === v), value);
  };
  const submit = async () => {
    // Two invocations in one event turn also exercise the synchronous duplicate guard.
    const button = page.getByRole('button', { name: /^(?:Re)?submit to Edmonton$/i });
    assert.equal(await button.isEnabled(), true, await page.locator('.cf-submit').innerText());
    await button.evaluate(button => { button.click(); button.click(); });
  };
  try {
    await page.goto(web + '/tests/check.html');
    await page.waitForFunction(() => !!window.caseStore);
    await page.locator('.cf-app').waitFor(); // The real auth gate has admitted the caller.
    await page.evaluate(async id => {
      const { refreshApplications } = await import('/src/calm/account.ts');
      await refreshApplications();
      const error = await window.caseStore.openCase(id, 'contractor');
      if (error) throw new Error(error);
      location.hash = '#/application';
    }, id);
    await page.getByRole('button', { name: /^(?:Re)?submit to Edmonton$/i }).waitFor();
    await page.waitForFunction(() => window.caseStore.sectionCLookup.source === 'live' && !window.caseStore.gaps.some(g => g.id.startsWith('lookup-')));
    await run({ page, id, remote, requests, hold, submits, edit, submit, context });
    assert.deepEqual(errors, []);
    passed++; console.log('PASS', name);
  } catch (error) {
    failed++; console.error('FAIL', name, String(error.stack).replace(/(cookie:)[^\n]*/gi, '$1 <REDACTED>'));
    console.error('Submit state', await page.locator('.cf-submit').allTextContents(),
      'gaps', await page.evaluate(() => window.caseStore?.gaps),
      'write receipts', requests.filter(r => r.path.endsWith('/submit') || r.path.endsWith('/facts')));
    const persisted = await remote();
    console.error('Persisted receipt', { status: persisted.status, legal: legal(persisted) });
  } finally {
    // The production list may still be refreshing after a successful transition or case switch.
    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await context.close();
  }
}

try {
  await scenario('J01 last-second C is acknowledged before resubmission, with no duplicate submit', async ({ page, remote, requests, hold, submits, edit, submit }) => {
    assert.equal(legal(await remote()), B);
    const save = hold();
    await edit(C);
    await submit();
    await save.entered;
    assert.equal(submits().length, 0, 'Resubmit reached the server before the latest save was acknowledged');
    assert.equal((await remote()).status, 'returned');
    save.release();
    await page.getByText('Sent to Edmonton', { exact: true }).waitFor();
    assert.equal(submits().length, 1);
    const sent = requests.findIndex(r => r.path.endsWith('/submit'));
    assert.ok(requests.slice(0, sent).filter(r => r.path.endsWith('/facts')).every(r => r.ack));
    const saved = await remote();
    assert.equal(saved.status, 'submitted'); assert.equal(legal(saved), C);
    assert.equal(submits()[0].body.expected_version + 1, saved.version);
    assert.match(await shown(page), /REVISION C/);
  });

  await scenario('J01 waits for an older in-flight save, then acknowledges the currently displayed C', async ({ page, remote, hold, submits, edit, submit }) => {
    const old = hold();
    await edit('REVISION intermediate — synthetic in-flight lot');
    await page.evaluate(() => { window.oldSave = window.caseStore.saveDraft(); });
    await old.entered;
    await edit(C);
    await submit();
    assert.equal(submits().length, 0);
    old.release();
    await page.getByText('Sent to Edmonton', { exact: true }).waitFor();
    assert.equal(legal(await remote()), C);
    assert.equal(submits().length, 1);
  });

  for (const status of [503, 409]) {
    await scenario(`J01 a failed in-flight save (${status}) blocks submission and keeps the error visible`, async ({ page, remote, hold, submits, edit, submit }) => {
      const save = hold('/facts', status, status === 409 ? 'case was updated concurrently' : 'Synthetic save unavailable');
      await edit(C);
      await page.evaluate(() => { window.failedSave = window.caseStore.saveDraft(); });
      await save.entered;
      await submit();
      save.release();
      await page.locator('.cf-submit .cf-hint').filter({ hasText: 'not saved' }).waitFor();
      assert.equal(submits().length, 0);
      const saved = await remote();
      assert.equal(saved.status, 'returned'); assert.equal(legal(saved), B);
      assert.equal(await page.evaluate(() => window.caseStore.saveStatus), 'failed');
      assert.equal(await page.getByText('Sent to Edmonton', { exact: true }).count(), 0);
      // Recovery is an explicit save, followed by another submit click.
      assert.ok(await page.evaluate(() => window.caseStore.saveDraft()));
      await submit();
      await page.getByText('Sent to Edmonton', { exact: true }).waitFor();
      assert.equal(legal(await remote()), C); assert.equal(submits().length, 1);
    });
  }

  await scenario('J01 a deleted case refuses submission and never creates a replacement', async ({ page, context, id, remote, requests, hold, submits, edit, submit }) => {
    const save = hold();
    await edit(C); await submit(); await save.entered;
    assert.equal((await context.request.delete(base + '/cases/' + id)).status(), 204);
    save.release();
    await page.locator('.cf-submit .cf-hint').filter({ hasText: 'Case deleted or expired' }).waitFor();
    assert.equal(submits().length, 0);
    assert.equal((await remote()).status, 404);
    assert.equal(await page.evaluate(() => window.caseStore.saveStatus), 'gone');
    assert.equal(requests.some(r => r.path === '/cases' && r.method === 'POST'), false);
    assert.match(await shown(page), /REVISION C/);
  });

  await scenario('J01 changing the revision while its save is pending cancels submission', async ({ page, remote, hold, submits, edit, submit }) => {
    const save = hold();
    await edit(C); await submit(); await save.entered;
    await edit('REVISION D — synthetic edit during save');
    save.release();
    await page.locator('.cf-submit .cf-hint').filter({ hasText: 'changed while submitting' }).waitFor();
    assert.equal(submits().length, 0); assert.equal((await remote()).status, 'returned');
    assert.equal(await page.getByRole('button', { name: 'Resubmit to Edmonton', exact: true }).isEnabled(), true);
  });

  await scenario('J01 switching the case while a save is pending cannot submit the previous case', async ({ page, remote, hold, submits, edit }) => {
    const save = hold();
    await edit(C);
    await page.evaluate(() => { window.submitResult = window.caseStore.submitDraft(window.caseStore.engineId).then(() => 'success', error => error.message); });
    await save.entered;
    const other = fixture.ids[next++];
    await page.evaluate(id => window.caseStore.openCase(id, 'contractor'), other);
    save.release();
    assert.match(await page.evaluate(() => window.submitResult), /changed while submitting/);
    assert.equal(submits().length, 0); assert.equal((await remote()).status, 'returned');
    assert.equal(await page.evaluate(() => window.caseStore.engineId), other);
    assert.match(await shown(page), /REVISION B/);
  });

  await scenario('J01 switching the account session during saving cannot submit', async ({ page, remote, hold, submits, edit }) => {
    const save = hold();
    await edit(C);
    await page.evaluate(() => { window.submitResult = window.caseStore.submitDraft(window.caseStore.engineId).then(() => 'success', error => error.message); });
    await save.entered;
    await page.evaluate(async () => {
      const { setAccountState } = await import('/src/calm/account.ts');
      setAccountState({ phase: 'signed-out', user: null });
    });
    save.release();
    assert.match(await page.evaluate(() => window.submitResult), /changed while submitting/);
    assert.equal(submits().length, 0); assert.equal((await remote()).status, 'returned');
  });

  await scenario('J01 a remounted submit panel stays disabled and shares one pending submit', async ({ page, id, remote, hold, submits, edit, submit }) => {
    const sent = hold('/submit');
    await edit(C); await submit(); await sent.entered;
    const shared = await page.evaluate(id => {
      const first = window.caseStore.submitDraft(id), second = window.caseStore.submitDraft(id);
      return first === second;
    }, id);
    assert.equal(shared, true);
    await page.evaluate(() => { location.hash = '#/review'; });
    await page.getByRole('region', { name: 'Application form' }).waitFor({ state: 'detached' });
    await page.evaluate(() => { location.hash = '#/application'; });
    assert.equal(await page.getByRole('button', { name: 'Submitting…', exact: true }).isDisabled(), true);
    assert.equal(submits().length, 1);
    sent.release();
    await page.getByText('Sent to Edmonton', { exact: true }).waitFor();
    assert.equal((await remote()).status, 'submitted'); assert.equal(submits().length, 1);
  });

  await scenario('J01 an intervening real server edit rejects the pinned submit and leaves the status editable', async ({ page, id, context, remote, hold, submits, edit, submit }) => {
    const sent = hold('/submit');
    await edit(C); await submit(); await sent.entered;
    const changed = await context.request.post(base + `/cases/${id}/facts`, { data: {
      expected_version: (await remote()).version,
      field: 'submit.synthetic_other_writer', value: 'SYNTHETIC concurrent revision', kind: 'pointed', status: 'confirmed',
      source: { type: 'user_text', ref: 'SYNTHETIC second writer', quote: 'SYNTHETIC concurrent revision' },
    } });
    assert.equal(changed.status(), 200);
    sent.release();
    await page.getByText('The saved application changed. Review it before submitting again.', { exact: true }).waitFor();
    assert.equal(submits().length, 1); assert.equal(submits()[0].status, 409);
    assert.equal((await remote()).status, 'returned');
    assert.equal(await page.getByRole('button', { name: 'Resubmit to Edmonton', exact: true }).isEnabled(), true);
    assert.equal(await page.getByText('Sent to Edmonton', { exact: true }).count(), 0);
    assert.equal(await page.evaluate(() => window.caseStore.saveStatus), 'failed');
    assert.ok(await page.evaluate(() => window.caseStore.saveDraft()), 'explicit save reconciles the changed version');
    await submit();
    await page.getByText('Sent to Edmonton', { exact: true }).waitFor();
    const saved = await remote();
    assert.equal(saved.status, 'submitted'); assert.equal(legal(saved), C);
    assert.ok(saved.facts.some(f => f.field === 'submit.synthetic_other_writer'), 'the other writer is preserved');
  });

  await scenario('J01 a failed submit preserves the draft status and allows one explicit retry', async ({ page, remote, hold, submits, edit, submit }) => {
    const sent = hold('/submit', 503, 'Synthetic submit unavailable');
    await edit(C); await submit(); await sent.entered; sent.release();
    await page.getByText('Synthetic submit unavailable', { exact: true }).waitFor();
    assert.equal((await remote()).status, 'returned');
    assert.equal(legal(await remote()), C);
    assert.equal(await page.getByRole('button', { name: 'Resubmit to Edmonton', exact: true }).isEnabled(), true);
    await submit();
    await page.getByText('Sent to Edmonton', { exact: true }).waitFor();
    assert.equal(submits().length, 2);
  });

  await scenario('J01 pending submit keeps the displayed revision intact through selected-row refresh and reload', async ({ page, remote, hold, edit, submit }) => {
    const sent = hold('/submit');
    await edit(C); await submit(); await sent.entered;
    await page.evaluate(() => { location.hash = '#/questions?focus=field-legalDescription'; });
    const field = page.locator('#field-legalDescription');
    await field.waitFor();
    const editPaused = await field.isDisabled();
    if (!editPaused) await field.fill('REVISION D — synthetic user edit while submitting');
    if (editPaused) {
      await page.getByRole('status').filter({ hasText: 'Submitting your saved application' }).waitFor();
      assert.equal(await field.inputValue(), C);
      // Document shortcuts and late events must not bypass the mounted disabled control.
      await page.evaluate(a => window.caseStore.dispatch(a), action('REVISION D — synthetic late input'));
      assert.equal(await field.inputValue(), C);
      await page.evaluate(() => { location.hash = '#/'; });
      const description = page.locator('#cf-describe');
      await description.waitFor();
      assert.equal(await description.isEditable(), false, 'the description caller is also paused');
      assert.equal(await page.getByText('Sent to Edmonton', { exact: true }).count(), 0, 'pending is not described as sent');
      await page.evaluate(() => { location.hash = '#/code/9.10.9.6.'; });
      const addRule = page.getByRole('button', { name: 'Add to my application', exact: true });
      await addRule.waitFor();
      assert.equal(await addRule.isDisabled(), true, 'the code-library editing caller is also paused');
      await page.evaluate(() => { location.hash = '#/questions?focus=field-legalDescription'; });
      await field.waitFor();
      assert.equal(await field.isDisabled(), true);
    }
    sent.release();
    await page.waitForFunction(() => !window.caseStore.submitting);
    await page.locator('.cf-list-hit[aria-current="page"]').click();
    // Also exercise the public list refresh on this worker's older Shell. The integration
    // checkout performs this read as part of the selected-row click itself (J05).
    await page.evaluate(async () => { const { refreshApplications } = await import('/src/calm/account.ts'); await refreshApplications(); });
    await page.locator('a[href="#/application"]:visible').first().click();
    await page.getByText('Sent to Edmonton', { exact: true }).waitFor();
    const saved = await remote();
    const sheet = await shown(page);
    const header = await page.locator('.cf-save').innerText();
    await page.reload();
    await page.locator('.cf-app').waitFor();
    await page.getByText('Sent to Edmonton', { exact: true }).waitFor();
    await page.getByRole('region', { name: 'Application form' }).waitFor();
    const reloaded = await shown(page);
    console.log('Pending submit integrity', JSON.stringify({ editPaused, storedLegal: legal(saved),
      previewC: sheet.includes(C), previewD: sheet.includes('REVISION D'), header, reloadC: reloaded.includes(C) }));
    assert.equal(saved.status, 'submitted'); assert.equal(legal(saved), C);
    assert.equal(editPaused, true, 'the displayed application stayed editable after submit was dispatched');
    assert.ok(sheet.includes(C)); assert.ok(!sheet.includes('REVISION D'));
    assert.match(header, /read-only/); assert.ok(reloaded.includes(C));
  });

  await scenario('J01 a refused dispatched transition restores editing of the saved revision', async ({ page, remote, hold, edit, submit }) => {
    const sent = hold('/submit', 503, 'Synthetic submit unavailable');
    await edit(C); await submit(); await sent.entered;
    await page.evaluate(() => { location.hash = '#/questions?focus=field-legalDescription'; });
    const field = page.locator('#field-legalDescription');
    await field.waitFor();
    assert.equal(await field.isDisabled(), true);
    sent.release();
    await page.waitForFunction(() => !window.caseStore.submitting);
    assert.equal(await field.isDisabled(), false);
    assert.equal(await field.inputValue(), C);
    assert.equal((await remote()).status, 'returned');
    await field.fill('REVISION D — synthetic correction after refusal');
    assert.equal(await field.inputValue(), 'REVISION D — synthetic correction after refusal');
    assert.equal(await page.locator('.cf-submission-pending').count(), 0);
  });

  await scenario('J01 the first submission also saves C before transitioning from draft', async ({ page, remote, hold, submits, edit, submit }) => {
    const save = hold();
    assert.equal((await remote()).status, 'draft');
    await edit(C); await submit(); await save.entered;
    assert.equal(submits().length, 0); assert.equal((await remote()).status, 'draft');
    save.release();
    await page.getByText('Sent to Edmonton', { exact: true }).waitFor();
    assert.equal(legal(await remote()), C); assert.equal(submits().length, 1);
  }, fixture.ids[15]);
} finally { await browser.close(); }
console.log(`Applicant submit integration: ${passed} passed, ${failed} failed`);
process.exitCode = failed ? 1 : 0;
