// J07: real return dialog/banner/history -> accounts + CaseProvider sync -> disposable SQLite.
// No provider calls or visual-capture claim. Parent owns the complete browser walkthrough.
import assert from 'node:assert/strict';
import { createHash, randomUUID } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import { DatabaseSync } from 'node:sqlite';
import { pathToFileURL } from 'node:url';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE ? pathToFileURL(process.env.PLAYWRIGHT_MODULE).href : 'playwright-core');
const web = process.env.SYNC_WEB_BASE, base = process.env.SYNC_TEST_BASE;
for (const url of [web, base]) assert.match(url ?? '', /^http:\/\/127\.0\.0\.1:\d+$/);
assert.ok(process.env.SYNC_TEST_DB, 'A disposable SQLite store is required');
const db = new DatabaseSync(process.env.SYNC_TEST_DB);
db.exec('PRAGMA busy_timeout = 5000');
const now = new Date().toISOString();
const actors = Object.fromEntries(['owner', 'officer'].map(name => {
  const user = { id: `j07-${randomUUID()}`, email: `${randomUUID()}@example.test`, name: `SYNTHETIC ${name}`,
    role: name === 'officer' ? 'reviewer' : 'applicant', authority: name === 'officer' ? 'edmonton' : null,
    applicant_type: name === 'officer' ? null : 'contractor', onboarded: true, created_at: now, notifications_seen_at: null };
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

async function fixture({ documents = false } = {}) {
  const created = await api('owner', '/cases', { title: 'SYNTHETIC J07 requested corrections', authority: 'edmonton', jurisdiction: { id: 'edmonton', name: 'Edmonton' } }, 201);
  let pdf, file;
  if (documents) {
    // Existing local dependency; bytes are generated in memory, with no writes to shared data.
    pdf = execFileSync('../.venv/bin/python', ['-B', '-c', 'from io import BytesIO; import sys; from reportlab.pdfgen import canvas; b=BytesIO(); c=canvas.Canvas(b); c.drawString(72,720,"SYNTHETIC J07 officer attachment"); c.save(); sys.stdout.buffer.write(b.getvalue())']);
    const body = new FormData(); body.append('file', new Blob([pdf], { type: 'application/pdf' }), 'SYNTHETIC-officer.pdf');
    const response = await fetch(base + `/cases/${created.id}/files`, { method: 'POST', headers: { Cookie: `batatis_session=${actors.owner.token}` }, body });
    assert.equal(response.status, 201); file = await response.json();
  }
  // Deliberately submitted incomplete fixture, so real review routes can request a real live gap.
  const row = db.prepare('SELECT json,version FROM cases WHERE id=?').get(created.id);
  const c = { ...JSON.parse(row.json), status: 'submitted', submitted_at: now };
  if (documents) {
    const fact = (field, value, source = { type: 'user_text', ref: 'SYNTHETIC officer fixture' }) => ({ id: randomUUID(), field, value, source, kind: 'pointed', status: 'confirmed' });
    // Legacy fact-based listings exercise the same real GET/ReviewDetail projection as new ones.
    c.facts.push(fact('evidence.attached.title', 'SYNTHETIC attached officer report'),
      fact('evidence.attached.evidence_type', 'evaluation'), fact('evidence.attached.responsible_party', 'SYNTHETIC attached author'),
      fact('evidence.attached.date', 'SYNTHETIC revision A'),
      fact('evidence.attached.file_ref', file.id, { type: 'file', ref: file.id, quote: file.name }),
      fact('evidence.unbound.title', 'SYNTHETIC unbound officer report'), fact('evidence.unbound.evidence_type', 'test'),
      fact('evidence.unbound.responsible_party', 'SYNTHETIC unbound author'), fact('evidence.unbound.date', 'SYNTHETIC revision U'));
  }
  db.prepare('UPDATE cases SET json=?,version=? WHERE id=?').run(JSON.stringify(c), row.version + 1, created.id);
  await api('officer', `/review/${created.id}/claim`, {});
  const { items: gaps } = await api('owner', `/cases/${created.id}/gaps`);
  const gap = gaps.find(g => g.field === 'legal_description');
  assert.ok(gap);
  const item = { gap_id: gap.id, field: gap.field, note: gap.message };
  return { id: created.id, gap, item, pdf, file };
}

const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
let passed = 0, failed = 0;
async function scenario(name, run, options) {
  const scene = await fixture(options);
  const contexts = [], pages = [], errors = [], requests = [];
  async function mount(actor) {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce', acceptDownloads: true });
    contexts.push(context);
    await context.addCookies([{ name: 'batatis_session', value: actors[actor].token, url: base, httpOnly: true, sameSite: 'Lax' }]);
    const page = await context.newPage();
    pages.push(page);
    page.setDefaultTimeout(8000);
    page.on('pageerror', e => errors.push(e.message));
    await page.route('**/*', async route => {
      const req = route.request(), url = new URL(req.url());
      if (url.origin !== web) return route.abort();
      if (!url.pathname.startsWith('/api/')) return route.continue();
      const path = url.pathname.replace(/^\/api/, '') + url.search;
      requests.push({ path, method: req.method(), body: req.postData() ? req.postDataJSON() : null });
      // Exercise the supported deterministic fallback, without asking any live assistant.
      if (path === '/assist') return route.fulfill({ status: 503, json: { detail: 'SYNTHETIC offline assistant' } });
      const response = await route.fetch({ url: base + path });
      await route.fulfill({ response });
    });
    await page.goto(web + '/tests/check.html' + (actor === 'officer' ? `#/review/${scene.id}` : ''));
    await page.waitForFunction(() => !!window.caseStore);
    await page.locator('.cf-app').waitFor(); // AuthGate must finish session restore/reset (J05).
    if (actor === 'owner') {
      assert.equal(await page.evaluate(id => window.caseStore.openCase(id, 'contractor'), scene.id), null);
      await page.evaluate(() => { location.hash = '#/application'; });
      await page.locator('.cf-returned').waitFor();
    } else await page.getByRole('heading', { name: 'Messages', exact: true }).waitFor();
    return page;
  }
  try {
    await run({ scene, mount, requests });
    assert.deepEqual(errors, []);
    assert.equal(requests.some(r => r.method === 'POST' && /\/(identify|intake|completeness)(\/|$)/.test(r.path)), false, 'no provider-backed checks');
    passed++; console.log('PASS', name);
  } catch (e) { failed++; console.error('FAIL', name, e.stack); }
  finally {
    for (const page of pages) await page.unrouteAll({ behavior: 'ignoreErrors' });
    for (const context of contexts) await context.close();
  }
}

const occurrences = (text, label) => text.split(label).length - 1;
async function returnCase(scene, message, items = [scene.item]) {
  return api('officer', `/review/${scene.id}/decision`, { outcome: 'return', message, items });
}

try {
  await scenario('drafted checklist item renders once on both sides while structured identity persists', async ({ scene, mount }) => {
    const officer = await mount('officer');
    await officer.getByRole('button', { name: 'Return with message', exact: true }).click();
    const dialog = officer.getByRole('dialog', { name: 'Return with a message', exact: true });
    await dialog.getByLabel(scene.gap.message, { exact: true }).check();
    await dialog.getByRole('button', { name: 'Draft from ticked items', exact: true }).click();
    await dialog.getByText('Draft built from the ticked items. Edit it before sending.', { exact: true }).waitFor();
    const message = dialog.getByRole('textbox');
    await message.fill((await message.inputValue()) + '\n\nSYNTHETIC keep the owner unchanged.');
    await dialog.getByRole('button', { name: 'Send and return', exact: true }).click();
    await dialog.waitFor({ state: 'hidden' });
    const thread = officer.locator('.ac-thread .is-decision');
    await thread.waitFor();
    assert.equal(occurrences(await thread.innerText(), scene.item.note), 1);
    const stored = await api('owner', `/cases/${scene.id}/messages`);
    assert.deepEqual(stored.decision.items, [scene.item], 'structured routing identifiers must survive');
    const owner = await mount('owner');
    assert.equal(occurrences(await owner.locator('.cf-returned').innerText(), scene.item.note), 1);
    assert.ok((await owner.locator('.cf-returned').innerText()).includes('SYNTHETIC keep the owner unchanged.'));
  });

  await scenario('legacy bullet appears once, keeps freeform comments, and follow-up cannot replace return items', async ({ scene, mount }) => {
    const message = `SYNTHETIC legacy instruction.\n\n- ${scene.item.note}\n- SYNTHETIC keep this separate officer comment.\n\nReview the corrections before resubmitting.`;
    const saved = await returnCase(scene, message);
    await api('officer', `/cases/${scene.id}/messages`, { body: 'SYNTHETIC later follow-up: retain the owner.' }, 201);
    const owner = await mount('owner');
    const banner = owner.locator('.cf-returned');
    assert.equal(occurrences(await banner.innerText(), scene.item.note), 1);
    assert.equal(await banner.locator('time').getAttribute('datetime'), saved.decision.at);
    assert.equal(await banner.getByText(/later follow-up/).count(), 0);
    await owner.locator('.cf-conversation summary').click();
    assert.equal(await owner.locator('.cf-conversation .ac-msg.is-decision').count(), 0, 'The current decision is already displayed above history');
    assert.equal(occurrences(await owner.locator('.cf-correspondence').innerText(), scene.item.note), 1);
    assert.ok((await banner.innerText()).includes('- SYNTHETIC keep this separate officer comment.'));
    await owner.locator('.ac-thread').getByText('SYNTHETIC later follow-up: retain the owner.', { exact: true }).waitFor();
    const officer = await mount('officer');
    assert.equal(occurrences(await officer.locator('.ac-thread .is-decision').innerText(), scene.item.note), 1);
    assert.deepEqual((await api('owner', `/cases/${scene.id}/messages`)).decision, saved.decision, 'display normalization must not rewrite historical records');
  });

  await scenario('saved correction clears red live gap, awaits officer confirmation, and reopens when withdrawn', async ({ scene, mount, requests }) => {
    await returnCase(scene, 'SYNTHETIC add the legal description, then review and resubmit.');
    const owner = await mount('owner');
    const row = owner.locator('.cf-returned-items li');
    await row.getByText('Still to address', { exact: true }).waitFor();
    assert.equal(await row.locator('.is-blocking').count(), 1);
    assert.equal(await row.getByRole('link').getAttribute('href'), '#/questions?focus=field-legalDescription');
    let release, entered;
    const pending = new Promise(resolve => { entered = resolve; });
    const gate = new Promise(resolve => { release = resolve; });
    await owner.route(`**/api/cases/${scene.id}/facts`, async route => { entered(); await gate; await route.fallback(); });
    await owner.evaluate(() => window.caseStore.dispatch({ type: 'setDetail', field: 'legalDescription', value: 'SYNTHETIC Lot 7 Block 8 Plan 9', section: 'B' }));
    await owner.waitForFunction(() => window.caseStore.c.facts.some(f => f.field === 'legalDescription' && f.value === 'SYNTHETIC Lot 7 Block 8 Plan 9'));
    await owner.evaluate(() => { window.j07Save = window.caseStore.saveDraft(); });
    try {
      await pending;
      await row.getByText('Save correction before resubmitting', { exact: true }).waitFor();
      assert.equal(await row.locator('.is-blocking').count(), 0);
      assert.equal(await row.getByText('Awaiting officer confirmation', { exact: true }).count(), 0);
    } finally { release(); }
    assert.equal(await owner.evaluate(() => window.j07Save), scene.id);
    await row.getByText('Awaiting officer confirmation', { exact: true }).waitFor();
    assert.equal(await row.locator('.is-blocking').count(), 0);
    assert.equal(await owner.locator('.cf-returned-acts').getByRole('link', { name: 'Review corrections', exact: true }).getAttribute('href'), '#/application');
    assert.ok((await owner.locator('.cf-returned').innerText()).includes('Resubmit on Application'));
    const remote = await api('owner', `/cases/${scene.id}`);
    assert.ok(remote.facts.some(f => f.field === 'legalDescription' && f.value === 'SYNTHETIC Lot 7 Block 8 Plan 9'));
    assert.ok(requests.some(r => r.path.endsWith('/facts') && r.body.field === 'legalDescription'), 'actual save queue must post the correction');
    assert.ok(!(await api('owner', `/cases/${scene.id}/gaps`)).items.some(g => g.field === 'legal_description'));
    assert.equal(remote.decision.outcome, 'return', 'the applicant cannot approve corrections');
    await owner.reload(); await owner.waitForFunction(() => !!window.caseStore); await owner.locator('.cf-app').waitFor();
    await owner.waitForFunction(id => window.caseStore.engineId === id, scene.id);
    await row.getByText('Awaiting officer confirmation', { exact: true }).waitFor();
    await owner.evaluate(() => window.caseStore.dispatch({ type: 'setDetail', field: 'legalDescription', value: '', section: 'B' }));
    await owner.evaluate(() => window.caseStore.saveDraft());
    await row.getByText('Still to address', { exact: true }).waitFor();
    assert.equal(await row.locator('.is-blocking').count(), 1);
  });

  await scenario('itemless return preserves useful officer instructions and routes review then Resubmit to Application', async ({ scene, mount }) => {
    const note = 'SYNTHETIC revise the drawing legend as discussed. Keep the owner name.\n\n- SYNTHETIC legacy body-only instruction.';
    await returnCase(scene, note, []);
    const owner = await mount('owner');
    const banner = owner.locator('.cf-returned');
    assert.ok((await banner.locator('.cf-returned-msg').textContent()).includes(note), 'body-only history retains its exact text and line breaks');
    assert.equal(occurrences(await banner.innerText(), 'SYNTHETIC legacy body-only instruction.'), 1);
    assert.equal(await banner.getByRole('link', { name: 'See what’s missing', exact: true }).count(), 0);
    assert.equal(await banner.getByRole('link', { name: 'Review corrections', exact: true }).getAttribute('href'), '#/application');
    assert.ok((await banner.innerText()).includes('Resubmit on Application'));
    await banner.getByRole('link', { name: 'Review corrections', exact: true }).click();
    await owner.getByRole('article', { name: 'Application preview', exact: true }).waitFor();
  });

  await scenario('next correction skips saved items while unresolved requested fields stay open', async ({ scene, mount }) => {
    const ownerGap = (await api('owner', `/cases/${scene.id}/gaps`)).items.find(g => g.field === 'owner_name');
    assert.ok(ownerGap);
    await returnCase(scene, 'SYNTHETIC please address both requested fields before resubmitting.', [scene.item, { gap_id: ownerGap.id, field: ownerGap.field, note: ownerGap.message }]);
    const owner = await mount('owner');
    await owner.evaluate(() => window.caseStore.dispatch({ type: 'setDetail', field: 'legalDescription', value: 'SYNTHETIC Lot 3 Block 4 Plan 5', section: 'B' }));
    await owner.waitForFunction(() => window.caseStore.c.facts.some(f => f.field === 'legalDescription' && f.value === 'SYNTHETIC Lot 3 Block 4 Plan 5'));
    assert.equal(await owner.evaluate(() => window.caseStore.saveDraft()), scene.id);
    const rows = owner.locator('.cf-returned-items li');
    await rows.filter({ hasText: scene.item.note }).getByText('Awaiting officer confirmation', { exact: true }).waitFor();
    await rows.filter({ hasText: ownerGap.message }).getByText('Still to address', { exact: true }).waitFor();
    assert.equal(await rows.locator('.is-blocking').count(), 1);
    const action = owner.locator('.cf-returned-acts').getByRole('link', { name: 'Address next item', exact: true });
    assert.equal(await action.getAttribute('href'), '#/questions?focus=field-owner');
    await action.click();
    await owner.getByRole('heading', { name: 'Who is the owner?', exact: true }).waitFor();
  });

  await scenario('officer sheet lists each bound/unbound document once with metadata and an authorized download', async ({ scene, mount }) => {
    const officer = await mount('officer');
    const sheet = officer.getByRole('article', { name: 'Submitted application', exact: true });
    const text = await sheet.innerText();
    assert.equal(occurrences(text, 'SYNTHETIC attached officer report'), 1);
    assert.equal(occurrences(text, 'SYNTHETIC unbound officer report'), 1);
    assert.ok(text.includes('evaluation · SYNTHETIC attached author · SYNTHETIC revision A'));
    assert.ok(text.includes('test · SYNTHETIC unbound author · SYNTHETIC revision U'));
    assert.equal(await sheet.getByText('Listed only · no file attached', { exact: true }).count(), 1);
    assert.ok(text.includes('Source: SYNTHETIC-officer.pdf'));
    const download = officer.waitForEvent('download');
    await sheet.getByRole('link', { name: 'Download SYNTHETIC-officer.pdf', exact: true }).click();
    const downloaded = await readFile(await (await download).path());
    assert.ok(downloaded.equals(scene.pdf), 'the officer download must contain the exact uploaded PDF bytes');
  }, { documents: true });
} finally { await browser.close(); db.close(); }
console.log(`J07 requested items: ${passed} passed, ${failed} failed`);
process.exitCode = failed ? 1 : 0;
