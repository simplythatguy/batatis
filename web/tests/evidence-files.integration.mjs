// Actual Recommendations -> CaseProvider save queue -> upload -> atomic binding -> stored PDF.
// No screenshot or whole-journey claim: parent owns visual evidence and authenticated walkthrough.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE ? pathToFileURL(process.env.PLAYWRIGHT_MODULE).href : 'playwright-core');
const web = process.env.SYNC_WEB_BASE, base = process.env.SYNC_TEST_BASE;
for (const url of [web, base]) assert.match(url ?? '', /^http:\/\/127\.0\.0\.1:\d+$/);
const pdfA = await readFile(process.env.EVIDENCE_PDF_DIR + '/synthetic-A.pdf');
const pdfB = await readFile(process.env.EVIDENCE_PDF_DIR + '/synthetic-B.pdf');
const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
let passed = 0, failed = 0;
const latest = (c, field) => [...c.facts].reverse().find(f => f.field === field);
async function scenario(name, work) {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce', acceptDownloads: true });
  page.setDefaultTimeout(8000);
  const requests = [], errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.route('**/*', route => ['127.0.0.1', 'localhost'].includes(new URL(route.request().url()).hostname) ? route.continue() : route.abort());
  page.on('request', req => {
    const path = new URL(req.url()).pathname;
    if (req.url().startsWith(base)) requests.push({ path, method: req.method(), body: req.headers()['content-type']?.includes('application/json') ? req.postDataJSON() : null });
  });
  const entry = page.locator('.doc-entry');
  const row = title => page.locator('.doc-list li').filter({ hasText: title });
  const remote = async () => (await fetch(base + '/cases/' + await page.evaluate(() => window.caseStore.engineId))).json();
  async function details(title) {
    await entry.getByLabel('Document name', { exact: true }).fill(title);
    await entry.getByRole('button', { name: 'Continue', exact: true }).click();
    await entry.getByLabel('Document type', { exact: true }).selectOption('evaluation');
    await entry.getByRole('button', { name: 'Continue', exact: true }).click();
    await entry.getByLabel('Prepared by (optional)').fill('SYNTHETIC fixture author');
  }
  async function upload(buffer, name) {
    await entry.locator('input[type=file]').setInputFiles({ name, mimeType: 'application/pdf', buffer });
    await entry.getByText('PDF uploaded. Save the document to attach it.', { exact: true }).waitFor();
  }
  async function save(title, attached = true) {
    await entry.getByRole('button', { name: 'Save document', exact: true }).click();
    await row(title).getByText(attached ? 'Saved · PDF attached' : 'Saved · listed, no file attached', { exact: true }).waitFor();
  }
  async function edit(title) {
    await row(title).getByRole('button', { name: 'Edit ' + title, exact: true }).click();
    await entry.getByRole('button', { name: 'Continue', exact: true }).click();
    await entry.getByRole('button', { name: 'Continue', exact: true }).click();
  }
  try {
    await page.goto(web + '/tests/evidence-files.html');
    await page.waitForFunction(() => !!window.caseStore);
    await page.evaluate(() => window.caseStore.beginEmpty('contractor'));
    await page.evaluate(() => window.caseStore.dispatch({ type: 'addCandidate', candidate: {
      id: 'synthetic-file-rule', provision: '9.27.3.2.(1)', answer: 'yes', identified: true, suggestion: 'search', part: 9,
      benchmark: true, topic: 'Synthetic fixture', quote: { text: '', citation: 'CodeDB' }, departure: 'Synthetic proposal', clarifyingQuestion: '',
    } }));
    await page.getByRole('button', { name: 'Evidence', exact: true }).click();
    await page.locator('#evidence-choice').waitFor();
    await entry.waitFor();
    await work({ page, entry, row, details, upload, save, edit, remote, requests });
    assert.deepEqual(errors, []);
    assert.equal(requests.some(r => r.method === 'POST' && /\/(identify|intake|completeness)(\/|$)/.test(r.path)), false, 'no provider or professional review requested');
    passed++; console.log('PASS', name);
  } catch (error) { failed++; console.log('FAIL', name, error.stack); }
  finally { await page.close(); }
}

await scenario('upload and bind synthetic PDF, download exact bytes, share source, replace/unbind/remove without losing another document', async ({ page, entry, row, details, upload, save, edit, remote, requests }) => {
  const task = await page.locator('#evidence-choice').inputValue();
  await details('SYNTHETIC first document');
  await upload(pdfA, 'SYNTHETIC source A.pdf');
  const fileA = await entry.getByLabel('Supporting PDF', { exact: true }).inputValue();
  assert.ok(fileA.startsWith('file_'));
  assert.equal((await remote()).evidence.length, 0, 'uploaded bytes are not yet bound');
  await save('SYNTHETIC first document');
  let stored = await remote();
  assert.equal(stored.evidence[0].kind, 'file');
  assert.equal(latest(stored, `evidence.${task}.file_ref`).value, fileA);
  assert.equal(latest(stored, `evidence.${task}.covers.${task}`).value, true);
  const evidenceWrite = requests.find(r => r.path.endsWith('/evidence'));
  assert.equal(evidenceWrite.body.file_ref, fileA);
  assert.equal(typeof evidenceWrite.body.expected_version, 'number');
  assert.deepEqual(evidenceWrite.body.scope, { item_id: task });
  assert.equal(requests.some(r => r.path.endsWith('/facts') && r.body?.field?.endsWith('.file_ref')), false, 'binding uses the atomic endpoint');
  const downloading = page.waitForEvent('download');
  await row('SYNTHETIC first document').getByRole('link', { name: 'Download SYNTHETIC source A.pdf' }).click();
  assert.deepEqual(await readFile(await (await downloading).path()), pdfA);
  await page.evaluate(() => { location.hash = '#/application'; });
  // The application page shows the actual filled PDF; the listed documents and their saved PDFs are one step away.
  const preview = page.locator('details.cf-side-docs');
  const openDocuments = async () => {
    await preview.waitFor();
    if (!(await preview.evaluate(d => d.open))) await preview.locator('summary').click();
  };
  await openDocuments();
  assert.equal((await preview.innerText()).split('SYNTHETIC first document').length - 1, 1, 'each listed document appears once beside its action');
  await preview.getByText(/SYNTHETIC fixture author/).waitFor();
  const applicantDownload = page.waitForEvent('download');
  await preview.getByRole('link', { name: 'Download SYNTHETIC source A.pdf' }).click();
  assert.deepEqual(await readFile(await (await applicantDownload).path()), pdfA, 'the applicant page exposes the same authorized source');
  await page.evaluate(() => { location.hash = '#/evidence'; });
  await page.getByRole('button', { name: 'Evidence', exact: true }).click();
  await entry.waitFor();
  await details('SYNTHETIC second document');
  await entry.getByLabel('Supporting PDF', { exact: true }).selectOption(fileA);
  await save('SYNTHETIC second document');
  await edit('SYNTHETIC first document');
  await upload(pdfB, 'SYNTHETIC source B.pdf');
  const fileB = await entry.getByLabel('Supporting PDF', { exact: true }).inputValue();
  await save('SYNTHETIC first document');
  stored = await remote();
  assert.equal(latest(stored, `evidence.${task}.file_ref`).value, fileB);
  assert.equal(latest(stored, `evidence.${task}~2.file_ref`).value, fileA);
  await edit('SYNTHETIC first document');
  await entry.getByRole('button', { name: 'Remove file binding', exact: true }).click();
  await save('SYNTHETIC first document', false);
  stored = await remote();
  assert.equal(latest(stored, `evidence.${task}.file_ref`).status, 'unconfirmed');
  assert.equal(latest(stored, `evidence.${task}~2.file_ref`).value, fileA);
  await page.evaluate(() => { location.hash = '#/application'; });
  await openDocuments();
  const unbound = preview.locator('.cf-sheet-document').filter({ hasText: 'SYNTHETIC first document' });
  assert.equal((await preview.innerText()).split('SYNTHETIC first document').length - 1, 1, 'unbound listings stay visible once');
  await unbound.getByText('Listed only · no file attached', { exact: true }).waitFor();
  assert.equal(await unbound.getByRole('link').count(), 0);
  assert.equal((await preview.innerText()).split('SYNTHETIC second document').length - 1, 1);
  await preview.getByRole('link', { name: 'Download SYNTHETIC source A.pdf' }).waitFor();
  await page.evaluate(() => { location.hash = '#/evidence'; });
  const id = stored.id;
  // Reload and reopen using the production rehydration path; retained source selection survives.
  await page.reload(); await page.waitForFunction(() => !!window.caseStore);
  assert.equal(await page.evaluate(id => window.caseStore.openCase(id, 'contractor'), id), null);
  await page.getByRole('button', { name: 'Evidence', exact: true }).click();
  await row('SYNTHETIC first document').getByRole('button', { name: 'Remove SYNTHETIC first document', exact: true }).click();
  await page.waitForFunction(() => document.querySelectorAll('.doc-list li').length === 1);
  stored = await remote(); assert.equal(stored.evidence.length, 1);
  const inventory = (await (await fetch(base + `/cases/${id}/files`)).json()).items;
  assert.deepEqual(new Set(inventory.map(f => f.id)), new Set([fileA, fileB]));
  for (const [fileId, data] of [[fileA, pdfA], [fileB, pdfB]]) assert.deepEqual(Buffer.from(await (await fetch(base + `/cases/${id}/files/${fileId}`)).arrayBuffer()), data);
  await page.getByText('Saved source PDFs (2)', { exact: true }).waitFor();
});

await scenario('a concurrent edit rejects the binding until explicit reconcile; uploaded bytes remain selectable', async ({ page, entry, details, upload, save, remote, requests }) => {
  await details('SYNTHETIC conflicted document');
  await upload(pdfA, 'SYNTHETIC conflict.pdf');
  const fileId = await entry.getByLabel('Supporting PDF', { exact: true }).inputValue();
  const before = await remote();
  const response = await fetch(base + `/cases/${before.id}/facts`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
    field: 'synthetic.concurrent', value: 'SYNTHETIC other writer', kind: 'pointed', status: 'confirmed', source: { type: 'user_text', ref: 'SYNTHETIC fixture' },
  }) }); assert.equal(response.status, 200);
  await entry.getByRole('button', { name: 'Save document', exact: true }).click();
  await page.waitForFunction(() => window.caseStore.saveStatus === 'failed');
  assert.equal((await remote()).evidence.length, 0);
  assert.equal(requests.filter(r => r.path.endsWith('/evidence')).length, 1, 'no unconditional retry');
  await page.getByRole('button', { name: 'Try saving again', exact: true }).click();
  await page.getByText('Saved · PDF attached', { exact: true }).waitFor();
  const stored = await remote();
  assert.equal(stored.evidence.length, 1);
  assert.ok(stored.facts.some(f => f.value === 'SYNTHETIC other writer'));
  assert.equal(latest(stored, `evidence.${stored.evidence[0].id}.file_ref`).value, fileId);
});

await scenario('invalid uploaded bytes never acquire a binding or a saved-file status', async ({ entry, details, remote }) => {
  await details('SYNTHETIC invalid source');
  await entry.locator('input[type=file]').setInputFiles({ name: 'SYNTHETIC not-a-PDF.pdf', mimeType: 'application/pdf', buffer: Buffer.from('SYNTHETIC non-PDF') });
  await entry.getByText(/only PDF files are accepted/i).waitFor();
  assert.equal(await entry.getByLabel('Supporting PDF', { exact: true }).inputValue(), '');
  assert.equal((await remote()).evidence.length, 0);
});

await scenario('reconcile cannot acknowledge matching document text bound to different PDF bytes', async ({ page, entry, details, upload, remote }) => {
  const task = await page.locator('#evidence-choice').inputValue();
  await details('SYNTHETIC same-title conflict');
  await upload(pdfA, 'SYNTHETIC chosen source.pdf');
  const chosen = await entry.getByLabel('Supporting PDF', { exact: true }).inputValue();
  const before = await remote();
  const body = new FormData(); body.append('file', new Blob([pdfB], { type: 'application/pdf' }), 'SYNTHETIC other source.pdf');
  const other = await (await fetch(base + `/cases/${before.id}/files`, { method: 'POST', body })).json();
  let intercepted = false;
  await page.route(base + `/cases/${before.id}/evidence`, async route => {
    if (intercepted) return route.continue();
    intercepted = true;
    // Commit the first request, then change only its file before the acknowledgement arrives.
    const response = await route.fetch();
    assert.equal(response.status(), 200);
    const saved = await response.json();
    const change = await fetch(base + `/cases/${before.id}/evidence`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...route.request().postDataJSON(), operation: 'update', expected_version: saved.case_version, file_ref: other.id }) });
    assert.equal(change.status, 200);
    await route.fulfill({ status: 409, json: { detail: 'case was updated concurrently' } });
  });
  await entry.getByRole('button', { name: 'Save document', exact: true }).click();
  await page.waitForFunction(() => window.caseStore.saveStatus === 'failed');
  await page.getByRole('button', { name: 'Try saving again', exact: true }).click();
  await page.waitForFunction(() => window.caseStore.saveStatus === 'saved' && !window.caseStore.c.listedEvidence?.length);
  const after = await remote();
  assert.deepEqual(after.evidence.map(e => e.id), [task, `${task}~2`]);
  assert.equal(latest(after, `evidence.${task}.file_ref`).value, other.id);
  assert.equal(latest(after, `evidence.${task}~2.file_ref`).value, chosen, 'the applicant choice was not silently dropped');
});

await browser.close();
console.log(`J03 mounted upload/bind: ${passed} passed, ${failed} failed`);
process.exitCode = failed ? 1 : 0;
