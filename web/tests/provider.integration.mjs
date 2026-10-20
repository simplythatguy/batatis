import assert from 'node:assert/strict';
import { chromium } from 'playwright-core';

const base = process.env.SYNC_TEST_BASE;
const web = process.env.SYNC_WEB_BASE;
assert.match(base ?? '', /^http:\/\/(127\.0\.0\.1|localhost):\d+/);
assert.match(web ?? '', /^http:\/\/(127\.0\.0\.1|localhost):\d+/);
const browser = await chromium.launch({ ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}), headless: true });
let passed = 0;
try {
  async function scenario(name, run) {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.addInitScript(({ base }) => {
      const original = window.fetch;
      window.requests = [];
      window.fetch = async (input, init) => {
        const url = new URL(String(input), location.href);
        const target = url.pathname.startsWith('/api/') ? base + url.pathname.slice(4) + url.search : base + url.pathname + url.search;
        window.requests.push({ url: target, method: init?.method });
        const hold = window.hold;
        const match = hold && !hold.used && target.endsWith(hold.suffix) && init?.method === hold.method;
        if (match) {
          hold.used = true;
          hold.wait = new Promise(resolve => { window.release = resolve; });
          if (!hold.after) { hold.ready = true; await hold.wait; }
        }
        if (match && hold.fail) return new Response(JSON.stringify({detail:'synthetic save failure'}), {status:503});
        const response = await original(target, init);
        if (match && hold.after) { hold.ready = true; await hold.wait; }
        return response;
      };
    }, { base });
    await page.goto(web + '/tests/provider.html');
    await page.waitForFunction(() => !!window.caseStore);
    try {
      await run(page);
      assert.deepEqual(errors, []);
      passed++;
      console.log('PASS', name);
    } finally { await page.close(); }
  }
  const dispatch = async (page, action) => {
    await page.evaluate(action => window.caseStore.dispatch(action), action);
    await page.evaluate(() => new Promise(requestAnimationFrame));
  };
  const begin = async page => {
    await page.evaluate(() => window.caseStore.beginEmpty('homebuilder'));
    await page.waitForFunction(() => window.caseStore.phase === 'case');
  };
  const hold = (page, suffix, method, after = true, fail = false) => page.evaluate(h => { window.hold = h; }, { suffix, method, after, fail });
  const startSave = page => page.evaluate(() => { window.pending = window.caseStore.saveDraft(); });
  const waitHeld = page => page.waitForFunction(() => window.hold?.ready);
  const release = page => page.evaluate(async () => { window.release(); return await window.pending; });
  const save = page => page.evaluate(() => window.caseStore.saveDraft());
  const remote = async id => (await fetch(base + '/cases/' + id)).json();
  const add = document => ({type:'saveEvidence', itemId:'wall', document, responsible:'Synthetic applicant', date:'2026-10-20', evidenceType:'evaluation', provisionId:'9.25.2.2.(1)'});

  await scenario('cleared process/detail stay missing during failed save and old online review', async page => {
    await begin(page);
    await dispatch(page, {type:'setProcess', field:'risk', value:'Synthetic old risk'});
    await dispatch(page, {type:'setDetail', field:'owner', value:'Synthetic owner', section:'A'});
    const id = await save(page);
    await hold(page, '/facts', 'POST', false, true);
    await dispatch(page, {type:'setProcess', field:'risk', value:''});
    await dispatch(page, {type:'setDetail', field:'owner', value:'', section:'A'});
    await startSave(page); await waitHeld(page);
    let state = await page.evaluate(() => ({sync:window.caseStore.readSync(), ok:window.caseStore.syncOk, fields:window.caseStore.gaps.map(x=>x.field)}));
    assert.equal(state.sync.reviewed, false); assert.equal(state.ok, false);
    assert.ok(state.fields.includes('process.risk_assessment')); assert.ok(state.fields.includes('owner'));
    await release(page);
    state = await page.evaluate(() => ({sync:window.caseStore.readSync(), fields:window.caseStore.gaps.map(x=>x.field)}));
    assert.equal(state.sync.reviewed, false);
    assert.ok(state.fields.includes('process.risk_assessment'));
    await save(page);
    const got = await remote(id);
    assert.equal(got.facts.filter(x=>x.field==='process.risk_assessment').at(-1).status, 'unconfirmed');
    const gaps = await (await fetch(base + '/cases/' + id + '/gaps')).json();
    assert.ok(gaps.some(x=>x.field==='risk_assessment'));
  });

  await scenario('derived professional review keeps its hold while a save completes', async page => {
    await begin(page);
    await dispatch(page, {type:'setDetail', field:'owner', value:'Synthetic applicant', section:'A'});
    await hold(page, '/gaps', 'GET');
    await startSave(page); await waitHeld(page);
    await dispatch(page, {type:'notePractice', value:true});
    const id = await release(page);
    assert.ok(id);
    const state = await page.evaluate(() => ({sync:window.caseStore.readSync(), gaps:window.caseStore.readGaps()}));
    assert.equal(state.sync.reviewed, true);
    assert.ok(state.gaps.some(x=>x.field==='professional.role' || x.field==='professional_requirement'));
  });

  for (const suffix of ['/cases', '/facts', '/gaps']) {
    await scenario('reset isolates pending ' + suffix + ' and stale save closure', async page => {
      await begin(page);
      await dispatch(page, {type:'setProcess', field:'risk', value:'Synthetic old role risk'});
      await hold(page, suffix, suffix === '/gaps' ? 'GET' : 'POST');
      await page.evaluate(() => { window.oldSave = window.caseStore.saveDraft; });
      await startSave(page); await waitHeld(page);
      await page.evaluate(() => window.caseStore.resetToWho());
      await page.waitForFunction(() => window.caseStore.phase === 'who');
      await page.evaluate(() => window.caseStore.beginEmpty('contractor'));
      await page.waitForFunction(() => window.caseStore.c.applicantType === 'contractor');
      await dispatch(page, {type:'setDetail', field:'owner', value:'Synthetic new owner', section:'A'});
      const next = await save(page);
      const before = await page.evaluate(() => ({id:window.caseStore.engineId, epoch:window.caseStore.factsEpoch, sync:window.caseStore.readSync(), note:window.caseStore.savedNote}));
      assert.equal(await release(page), null);
      assert.equal(await page.evaluate(() => window.oldSave()), null);
      const after = await page.evaluate(() => ({id:window.caseStore.engineId, epoch:window.caseStore.factsEpoch, sync:window.caseStore.readSync(), note:window.caseStore.savedNote}));
      assert.deepEqual(after, before); assert.equal(after.id, next);
      assert.ok(!(await remote(next)).facts.some(x=>x.value==='Synthetic old role risk'));
    });
  }

  await scenario('evidence replacement survives a delete held before persistence', async page => {
    await begin(page);
    await dispatch(page, add('Synthetic removed report'));
    const id = await save(page);
    await hold(page, '/evidence/wall', 'DELETE', false);
    await dispatch(page, {type:'removeEvidence', id:'wall'});
    await startSave(page); await waitHeld(page);
    await dispatch(page, add('Synthetic replacement report'));
    const slot = await page.evaluate(() => window.caseStore.c.listedEvidence[0].id);
    assert.notEqual(slot, 'wall');
    await release(page); await save(page);
    const got = await remote(id);
    assert.ok(got.facts.some(x=>x.field===`evidence.${slot}.title` && x.value==='Synthetic replacement report'));
    assert.ok(!got.facts.some(x=>x.field.startsWith('evidence.wall.')));
    assert.deepEqual(await page.evaluate(() => window.caseStore.c.deletedEvidence), []);
  });

  await scenario('old deletion acknowledgement cannot clear the new case deletion', async page => {
    await begin(page); await dispatch(page, add('Synthetic old report')); await save(page);
    await hold(page, '/evidence/wall', 'DELETE');
    await dispatch(page, {type:'removeEvidence', id:'wall'});
    await startSave(page); await waitHeld(page);
    await page.evaluate(() => window.caseStore.beginEmpty('contractor'));
    await page.waitForFunction(() => window.caseStore.c.applicantType==='contractor');
    await dispatch(page, add('Synthetic new report')); await save(page);
    await dispatch(page, {type:'removeEvidence', id:'wall'});
    await release(page);
    assert.deepEqual(await page.evaluate(() => window.caseStore.c.deletedEvidence), ['wall']);
    await save(page);
    assert.deepEqual(await page.evaluate(() => window.caseStore.c.deletedEvidence), []);
  });
  console.log(`Provider integration: ${passed} passed`);
} finally { await browser.close(); }
