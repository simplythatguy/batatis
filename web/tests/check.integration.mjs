import assert from 'node:assert/strict';
import { chromium } from 'playwright-core';

const web = process.env.SYNC_WEB_BASE;
assert.match(web ?? '', /^http:\/\/(127\.0\.0\.1|localhost):\d+/);
const browser = await chromium.launch({ ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}), headless: true });
let passed = 0;
let failed = 0;
async function scenario(name, run) {
  const page = await browser.newPage();
  page.setDefaultTimeout(5000);
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  // Deny external network. The fake live adapter below succeeds on identify;
  // zero dispatch assertions therefore cannot pass merely because a key is absent.
  await page.route('**/*', route => new URL(route.request().url()).origin === new URL(web).origin ? route.continue() : route.abort());
  await page.addInitScript(() => {
    window.spy = { requests: [], providerCalls: 0, cases: {}, next: 0, fail: '', hold: '', held: false };
    window.fetch = async (input, init = {}) => {
      const s = window.spy;
      const u = new URL(String(input), location.href);
      const path = u.pathname.replace(/^\/api/, '');
      const method = init.method ?? 'GET';
      const body = init.body ? JSON.parse(init.body) : undefined;
      const req = { path, url: u.href, method, body, ack: false };
      s.requests.push(req);
      if (s.hold && path.endsWith(s.hold) && !s.held) {
        s.held = true;
        await new Promise(resolve => { window.release = resolve; });
        // Deliberately ignores AbortSignal: tests the publication guard as well.
      }
      const reply = (data, status = 200) => { req.ack = status < 400; return new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } }); };
      if (s.fail && path.endsWith(s.fail)) return reply({detail:'Synthetic unavailable route'}, 404);
      if (path === '/cases' && method === 'POST') {
        const c = { id: 'fake-' + ++s.next, facts: [], jurisdiction: body.jurisdiction };
        s.cases[c.id] = c;
        return reply(c);
      }
      const id = path.split('/')[2];
      if (/\/identify(?:\/stream)?$/.test(path) && (method === 'POST' || path.endsWith('/stream'))) {
        s.providerCalls++;
        return reply({ mode:s.cached ? 'cached_demo' : 'live', cached:!!s.cached, articles:[{provision:'9.25.2.2.(1)', title:'Synthetic ranked provision', part:9, reason:'Fake provider result'}], open_questions:[] });
      }
      if (path.endsWith('/identify')) return reply({articles:[]});
      if (path.endsWith('/facts')) { s.cases[id].facts.push(body); return reply(body); }
      if (path.endsWith('/jurisdiction')) return reply({detail:'Not Found'}, 404);
      if (/\/cases\/[^/]+$/.test(path)) return reply(s.cases[id]);
      if (path === '/code/search') return reply([{id:'9.25.2.2.(1)', division:'B', text:'Synthetic code wording', citation:'Synthetic citation', article_title:'Insulation', title:'Insulation'}]);
      if (path.endsWith('/gaps')) return reply([{id:'owner',field:'owner_name',section:'A',severity:'blocking',message:'Owner is missing.'}]);
      if (path.endsWith('/section-d')) return reply({items:[],notices:[]});
      if (path.endsWith('/professional')) return reply({required:'depends',reasons:[],questions:[]});
      if (path.includes('/code/')) return reply({id:'9.25.2.2.(1)',text:'Synthetic code wording',citation:'Synthetic citation', children:[]});
      return reply([]);
    };
  });
  await page.goto(web + '/tests/check.html');
  await page.waitForFunction(() => !!window.caseStore);
  try { await run(page); assert.deepEqual(errors, []); passed++; console.log('PASS', name); }
  catch (e) { failed++; console.error('FAIL', name, e.stack); }
  finally { await page.close(); }
}
const dispatch = async (page, action) => { await page.evaluate(a => window.caseStore.dispatch(a), action); await page.evaluate(() => new Promise(requestAnimationFrame)); };
const begin = async page => { await page.evaluate(() => window.caseStore.beginEmpty('homebuilder')); await page.waitForFunction(() => window.caseStore.phase === 'case'); };
const describe = page => dispatch(page, {type:'setDescription',text:'Synthetic insulated wall. Owner: PRIVATE PERSON. Permit: PRIVATE-123. Address: 123 PRIVATE ROAD.'});
const nav = async (page, path) => { await page.evaluate(p => {location.hash = '#' + p;}, path); await page.evaluate(() => new Promise(requestAnimationFrame)); };
const count = page => page.evaluate(() => window.spy.providerCalls);
const save = page => page.evaluate(() => window.caseStore.saveDraft());
const check = page => page.evaluate(() => window.caseStore.requestCheck());
try {
  await scenario('load, type, paste, pause, save, navigation, deep links and reload never identify', async page => {
    await begin(page);
    await page.locator('#description').fill('Synthetic wall');
    await describe(page);
    await page.getByText('Add text from plans', {exact:true}).click();
    await page.locator('#paste-plans').fill('PRIVATE plan text pasted by applicant.');
    await page.getByRole('button', {name:'Add text',exact:true}).click();
    await page.waitForTimeout(650);
    await save(page);
    assert.equal(await count(page), 0, 'typing/save triggered identify');
    for (const path of ['/code-check', '/section-c', '/application?tab=A', '/describe', '/code-check']) {
      await nav(page, path); await page.waitForTimeout(120);
    }
    assert.equal(await count(page), 0, 'navigation triggered fake live provider');
    const gets = await page.evaluate(() => window.spy.requests.filter(r => r.method === 'GET').map(r => r.url));
    assert.ok(gets.every(u => !/PRIVATE|prose=|Synthetic/i.test(u)), JSON.stringify(gets));
    await page.reload(); await page.waitForFunction(() => !!window.caseStore);
    assert.equal(await count(page), 0);
    assert.equal(await page.evaluate(() => window.caseStore.c.description), '');
    assert.equal(await page.evaluate(() => window.caseStore.phase), 'who');
  });
  await scenario('unsupported jurisdiction update never creates a second case', async page => {
    await begin(page); await describe(page); const id = await save(page);
    await dispatch(page, {type:'setAuthority',authority:'calgary'});
    await save(page);
    assert.equal(await page.evaluate(() => window.spy.next), 1, 'orphan copy created');
    assert.equal(await page.evaluate(() => window.caseStore.engineId), id);
    assert.equal(await page.evaluate(() => window.caseStore.saveStatus), 'failed');
    assert.match(await page.evaluate(() => window.caseStore.c.description), /PRIVATE/);
    await check(page); assert.equal(await count(page), 0);
  });
  await scenario('clearing a saved authority cannot claim acknowledgement or create a copy', async page => {
    await begin(page);
    await dispatch(page, {type:'setAuthority',authority:'calgary'});
    await describe(page); await save(page);
    assert.equal(await page.evaluate(() => window.caseStore.saveStatus), 'saved');
    await dispatch(page, {type:'setAuthority',authority:''});
    await check(page);
    assert.equal(await page.evaluate(() => window.caseStore.saveStatus), 'failed');
    assert.equal(await count(page), 0);
    assert.equal(await page.evaluate(() => window.spy.next), 1);
    assert.equal(await page.evaluate(() => window.caseStore.c.authority), '');
  });
  await scenario('cached demonstration output cannot populate a real case', async page => {
    await begin(page); await describe(page);
    const before = await page.evaluate(() => window.caseStore.c.candidates);
    await page.evaluate(() => { window.spy.cached = true; });
    await check(page);
    assert.equal(await page.evaluate(() => window.caseStore.checkStatus), 'unavailable');
    assert.deepEqual(await page.evaluate(() => window.caseStore.c.candidates), before);
    assert.equal(await page.evaluate(() => window.caseStore.syncOk), false);
  });
  await scenario('one explicit check waits for the latest save; double click, remount and reconnect do not duplicate', async page => {
    await begin(page);
    await page.evaluate(() => { window.spy.hold = '/facts'; });
    await describe(page);
    await page.evaluate(() => { window.pendingCheck = window.caseStore.requestCheck(); window.secondCheck = window.caseStore.requestCheck(); });
    await page.waitForFunction(() => window.spy.held);
    assert.equal(await count(page), 0);
    assert.equal(await page.evaluate(() => window.spy.requests.some(r => /\/identify$/.test(r.path))), false);
    await page.evaluate(() => window.release());
    await page.evaluate(() => window.pendingCheck);
    assert.equal(await count(page), 1);
    const seq = await page.evaluate(() => window.spy.requests);
    const identify = seq.findIndex(r => r.path.endsWith('/identify') && r.method === 'POST');
    assert.ok(seq.slice(0, identify).filter(r => r.path.endsWith('/facts')).every(r => r.ack));
    assert.equal(await page.evaluate(() => window.caseStore.checkStatus), 'needs_answers');
    for (const path of ['/code-check','/describe','/section-c','/code-check']) await nav(page, path);
    await page.evaluate(() => { window.dispatchEvent(new Event('online')); window.dispatchEvent(new Event('offline')); });
    await check(page);
    assert.equal(await count(page), 1, 'unchanged result was rerun');
    assert.equal(await page.evaluate(() => window.spy.requests.some(r => /export|submit|publish/.test(r.path))), false);
  });
  await scenario('edits mark results stale without recheck, late revision results never publish', async page => {
    await begin(page); await describe(page); await save(page);
    await page.evaluate(() => { window.spy.hold = '/identify'; window.pendingCheck = window.caseStore.requestCheck(); });
    await page.waitForFunction(() => window.spy.held);
    await dispatch(page, {type:'setDetail',field:'owner',value:'Updated owner',section:'A'});
    await page.evaluate(() => window.release()); await page.evaluate(() => window.pendingCheck);
    assert.equal(await page.evaluate(() => window.caseStore.checkStatus), 'stale');
    assert.equal(await page.evaluate(() => window.caseStore.c.candidates.some(c => c.topic === 'Synthetic ranked provision')), false);
    const requests = await page.evaluate(() => window.spy.requests.filter(r => r.path.endsWith('/identify')).length);
    await save(page); await nav(page, '/code-check'); await page.waitForTimeout(650);
    assert.equal(await page.evaluate(() => window.spy.requests.filter(r => r.path.endsWith('/identify')).length), requests);
    assert.equal(await page.evaluate(() => window.caseStore.syncOk), false);
  });
  await scenario('reset isolates late check output and clears intent; cold visits never restore', async page => {
    await begin(page); await describe(page); await save(page);
    await page.evaluate(() => { window.spy.hold = '/identify'; window.pendingCheck = window.caseStore.requestCheck(); });
    await page.waitForFunction(() => window.spy.held);
    await page.evaluate(() => window.caseStore.resetToWho()); await begin(page);
    await dispatch(page, {type:'setDetail',field:'owner',value:'New visitor',section:'A'}); await save(page);
    await page.evaluate(() => window.release()); await page.evaluate(() => window.pendingCheck);
    assert.equal(await page.evaluate(() => window.caseStore.checkStatus), 'not_requested');
    assert.equal(await page.evaluate(() => window.caseStore.c.description), '');
    assert.equal(await page.evaluate(() => window.caseStore.c.candidates.length), 0);
  });
  await scenario('missing identify route never starts a GET fallback or retries until explicit Try check again', async page => {
    await begin(page); await describe(page);
    await page.evaluate(() => { window.spy.fail = '/identify'; });
    await check(page);
    assert.equal(await page.evaluate(() => window.caseStore.checkStatus), 'unavailable');
    await nav(page, '/code-check');
    assert.equal(await page.getByRole('button', {name:'Try check again',exact:true}).count(), 1);
    await save(page); await check(page); await nav(page, '/section-c'); await nav(page, '/code-check');
    await page.evaluate(() => window.dispatchEvent(new Event('online')));
    assert.equal(await page.evaluate(() => window.spy.requests.filter(r => r.path.endsWith('/identify')).length), 1);
    assert.equal(await page.evaluate(() => window.spy.requests.some(r => r.path.includes('/stream') || r.url.includes('prose='))), false);
    await page.evaluate(() => { window.spy.fail = ''; });
    await page.getByRole('button', {name:'Try check again',exact:true}).click();
    await page.waitForFunction(() => window.caseStore.checkStatus === 'needs_answers');
    assert.equal(await count(page), 1);
  });
  await scenario('failed saves stop before identification and never show stale save success', async page => {
    await begin(page); await describe(page); await save(page);
    await page.evaluate(() => { window.spy.fail = '/facts'; });
    await dispatch(page, {type:'setProcess',field:'risk',value:'Keep this local answer'});
    await check(page);
    assert.equal(await count(page), 0);
    assert.equal(await page.evaluate(() => window.caseStore.saveStatus), 'failed');
    assert.equal(await page.evaluate(() => window.caseStore.readSync().saved), false);
    assert.doesNotMatch(await page.evaluate(() => window.caseStore.savedNote), /Draft saved|Saved for/);
    assert.equal(await page.evaluate(() => window.caseStore.c.process.risk), 'Keep this local answer');
  });
  await scenario('manual keyword search and explicit provision selection remain provider-free', async page => {
    await begin(page); await describe(page); await save(page); await nav(page, '/section-c');
    assert.equal(await page.locator('#section-c-search').inputValue(), '');
    await page.locator('#section-c-search').fill('insulation');
    await page.getByRole('button', {name:'Search',exact:true}).click();
    await page.getByRole('button', {name:'Use this provision',exact:true}).click();
    await page.waitForFunction(() => window.spy.requests.some(r => r.path === '/section-c'));
    assert.equal(await count(page), 0);
    const urls = await page.evaluate(() => window.spy.requests.filter(r => r.method === 'GET').map(r => r.url));
    assert.ok(urls.every(u => !/PRIVATE|prose=|Synthetic/i.test(u)), JSON.stringify(urls));
    assert.ok(urls.some(u => u.includes('insulation')));
  });
  await scenario('save does not claim a review, current lookup failure removes previous check success', async page => {
    await begin(page); await describe(page); await save(page);
    assert.equal(await page.evaluate(() => window.caseStore.checkStatus), 'not_requested');
    assert.equal(await page.evaluate(() => window.spy.requests.some(r => r.path.endsWith('/gaps'))), false);
    assert.equal(await page.evaluate(() => window.caseStore.readSync().reviewed), false);
    await check(page);
    await nav(page, '/code-check');
    await page.locator('.manual-search > summary').click();
    await page.evaluate(() => { window.spy.fail = '/code/search'; });
    await page.locator('#code-search').fill('firestop');
    await page.getByRole('button', {name:'Search',exact:true}).click();
    await page.waitForFunction(() => window.caseStore.checkStatus === 'stale');
    assert.equal(await page.evaluate(() => window.caseStore.syncOk), false);
    assert.ok(!(await page.locator('body').innerText()).includes('Online administrative review finished'));
  });
  await scenario('Ready to submit checks incomplete draft but never exports, submits or downloads', async page => {
    let downloads = 0; page.on('download', () => downloads++);
    await begin(page); await describe(page); await nav(page, '/application?tab=A');
    await page.getByRole('button', {name:'Ready to submit',exact:true}).click();
    await page.waitForFunction(() => window.caseStore.checkStatus === 'needs_answers');
    assert.equal(await count(page), 1);
    assert.equal(downloads, 0);
    assert.equal(await page.evaluate(() => window.spy.requests.some(r => /export|submit|publish/.test(r.path))), false);
    const official = page.getByRole('button', {name:'Download application PDF',exact:true});
    if (await official.count()) assert.equal(await official.isDisabled(), true);
  });
  await scenario('product UI has no example launchers; role and field groups stay small at 390px', async page => {
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.getByRole('heading', {name:'Your role',exact:true}).count(), 1);
    assert.equal(await page.locator('.role-option').count(), 3);
    assert.doesNotMatch(await page.locator('body').innerText(), /example|NorthCore|corridor|Roles:/i);
    await page.getByRole('button', {name:'Homebuilder',exact:true}).click();
    await page.getByRole('button', {name:'Continue',exact:true}).click();
    assert.equal(await page.locator('textarea:visible').count(), 1);
    assert.equal(await page.locator('.btn-primary:visible').count(), 1);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await nav(page, '/application?tab=B&focus=field-municipalAddress');
    await page.locator('#field-municipalAddress').waitFor({state:'visible'});
    assert.ok(await page.locator('.field-step input:visible,.field-step textarea:visible,.field-step select:visible').count() <= 2);
    await nav(page, '/application?tab=D');
    await page.locator('#prof-role').waitFor({state:'visible'});
    assert.equal(await page.locator('.field-step select:visible').count(), 1);
    assert.equal(await page.getByRole('combobox', {name:'Application section',exact:true}).count(), 1);
    assert.equal(await page.getByRole('combobox', {name:'Who is the registered professional for this scope?',exact:true}).count(), 1);
    assert.equal(await count(page), 0);
  });
} finally { await browser.close(); }
console.log(`Explicit check integration: ${passed} passed, ${failed} failed`);
process.exitCode = failed ? 1 : 0;
