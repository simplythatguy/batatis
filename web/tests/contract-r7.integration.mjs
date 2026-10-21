// R7 mounted UI against the real engine: final clear with retained documents, a real stale 409,
// expiry 404 and no automatic assistance. Test data is labelled SYNTHETIC.
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {chromium} from 'playwright-core';
const web=process.env.SYNC_WEB_BASE, base=process.env.SYNC_TEST_BASE, db=process.env.SYNC_TEST_DB;
for(const url of [web,base]) assert.match(url??'',/^http:\/\/(127\.0\.0\.1|localhost):\d+/);
assert.ok(db,'SYNC_TEST_DB names the disposable store');
const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
let passed=0,failed=0;
const nav=(p,hash)=>p.evaluate(h=>location.hash='#'+h,hash);
const act=async(p,a)=>{await p.evaluate(a=>window.caseStore.dispatch(a),a);await p.evaluate(()=>new Promise(requestAnimationFrame));};
const candidate=(provision,answer=null)=>({type:'addCandidate',candidate:{id:'probe-'+provision,provision,answer,identified:true,suggestion:'search',part:3,benchmark:answer==='yes',topic:'Firestops',quote:{text:'',citation:'CodeDB'},departure:'depart from this sentence',clarifyingQuestion:'Which part changes?'}});
const remote=async id=>(await fetch(base+'/cases/'+id)).json();
const posts=(p,suffix)=>p.evaluate(s=>window.requests.filter(r=>r.path.endsWith(s)&&r.method==='POST').length,suffix);
const assistance=p=>p.evaluate(()=>window.requests.filter(r=>/identify|completeness|information-request/.test(r.path)).length);
async function evidence(p){await nav(p,'/application?tab=D');await p.getByRole('button',{name:'Evidence',exact:true}).click();}
async function scenario(name,run){
 const page=await browser.newPage({viewport:{width:390,height:844},reducedMotion:'reduce'});page.setDefaultTimeout(8000);
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',r=>['127.0.0.1','localhost'].includes(new URL(r.request().url()).hostname)?r.continue():r.abort());
 await page.addInitScript(({base})=>{
  const original=window.fetch;
  window.requests=[];
  window.fetch=async(input,init)=>{
   const u=new URL(String(input),location.href);const target=base+u.pathname.replace(/^\/api/,'')+u.search;
   const entry={path:u.pathname.replace(/^\/api/,''),method:init?.method??'GET',body:init?.body,ack:false,status:0};window.requests.push(entry);
   const response=await original(target,init);entry.ack=response.ok;entry.status=response.status;return response;
  };
 },{base});
 try{
  await page.goto(web+'/tests/check.html');await page.waitForFunction(()=>!!window.caseStore);
  await page.evaluate(()=>window.caseStore.beginEmpty('contractor'));
  await page.locator('#description').fill('SYNTHETIC firestop review for an R7 regression.');
  await page.evaluate(()=>window.caseStore.saveDraft());
  await run(page);assert.deepEqual(errors,[]);passed++;console.log('PASS',name);
 }catch(e){failed++;console.log('FAIL',name,e.stack);}finally{await page.close();}
}

await scenario('R7 last clear persists empty C/D, keeps the listed document unscoped, and reselect does not relink it',async p=>{
 await act(p,candidate('3.1.9.1.(1)','yes'));await p.waitForFunction(()=>window.caseStore.c.sectionC.length===1);
 await evidence(p);await p.locator('#evidence-choice').waitFor();
 const task=await p.locator('#evidence-choice').inputValue();
 await p.locator(`#evidence-type-${task}`).selectOption({index:1});
 await p.locator(`#evidence-doc-${task}`).fill('SYNTHETIC firestop listing');
 await p.locator(`#evidence-who-${task}`).fill('SYNTHETIC designer');
 await p.getByRole('button',{name:'Save this evidence',exact:true}).click();
 await p.getByText('Documents already on this case',{exact:true}).waitFor();
 const id=await p.evaluate(()=>window.caseStore.engineId);
 await p.waitForFunction(()=>window.caseStore.saveStatus==='saved');
 await p.evaluate(()=>window.caseStore.saveDraft());
 assert.ok((await remote(id)).facts.some(f=>f.field===`evidence.${task}.title`));
 await nav(p,'/section-c');await p.locator('#sentence-decision').selectOption('');
 await evidence(p);
 await p.getByText('No code references selected.',{exact:false}).waitFor();
 assert.equal(await p.locator('#evidence-choice').count(),0);
 assert.equal(await p.getByText('No Section D issues returned.',{exact:true}).count(),0,'one empty state, not two');
 await p.getByText('Kept documents (1)',{exact:false}).click();
 assert.ok(await p.getByText('SYNTHETIC firestop listing',{exact:false}).first().isVisible());
 let saved=await remote(id);
 assert.deepEqual([saved.provisions,saved.section_c,saved.gaps],[[],[],[]]);
 assert.ok(saved.facts.some(f=>f.field===`evidence.${task}.auto_link`&&f.value===false));
 assert.ok(saved.facts.some(f=>f.field===`evidence.${task}.title`&&f.value==='SYNTHETIC firestop listing'),'document metadata retained');
 await nav(p,'/section-c');await p.locator('#sentence-decision').selectOption('yes');
 await evidence(p);await p.locator('#evidence-choice').waitFor();
 assert.equal(await p.locator('#evidence-choice').inputValue(),task,'stable task id returns');
 assert.equal(await p.getByText('Documents already on this case',{exact:true}).count(),0,'old listing is not silently relinked');
 assert.equal(await p.getByText('Added: SYNTHETIC firestop listing',{exact:false}).count(),0,'no stale "Added" note implies a link');
 assert.match(await p.locator('article.card .label-pill').first().innerText(),/open/);
 assert.equal(await p.getByText('Kept documents (1)',{exact:false}).count(),1,'still kept, still unlinked');
 saved=await remote(id);assert.deepEqual(saved.provisions,['3.1.9.1.(1)']);
 const bodies=await p.evaluate(()=>window.requests.filter(r=>r.path.endsWith('/section-d')&&r.method==='POST').map(r=>JSON.parse(r.body)));
 assert.ok(bodies.some(b=>Array.isArray(b.provisions)&&b.provisions.length===0&&Number.isInteger(b.expected_version)));
 assert.ok(bodies.every(b=>b.provisions!==null&&(b.provisions===undefined||b.expected_version>0)));
 assert.equal(await assistance(p),0);
});

await scenario('R7 real stale 409 keeps the draft, never retries by itself, and reconciles only when asked',async p=>{
 await act(p,candidate('3.1.9.1.(1)','yes'));await p.waitForFunction(()=>window.caseStore.c.sectionC.length===1);
 await evidence(p);await p.locator('#evidence-choice').waitFor();
 const id=await p.evaluate(()=>window.caseStore.engineId);
 const other=await fetch(base+`/cases/${id}/facts`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({field:'process.maintenance_operation',value:'SYNTHETIC second writer answer',kind:'pointed',status:'confirmed',source:{type:'user_text',ref:'SYNTHETIC second writer',quote:'x'}})});
 assert.equal(other.status,200);
 await act(p,{type:'setProcess',field:'risk',value:'SYNTHETIC local draft kept through a conflict'});
 await p.getByRole('button',{name:'Refresh case and retry',exact:true}).waitFor();
 const rejected=await p.evaluate(()=>window.requests.filter(r=>r.path.endsWith('/section-d')&&r.method==='POST').map(r=>r.status));
 assert.equal(rejected.at(-1),409,'the engine, not the client, reported the conflict');
 const writes=await posts(p,'/section-d');
 await nav(p,'/application?tab=A');await evidence(p);await p.getByRole('button',{name:'Refresh case and retry',exact:true}).waitFor();
 assert.equal(await posts(p,'/section-d'),writes,'no automatic retry');
 assert.equal(await p.evaluate(()=>window.caseStore.c.process.risk),'SYNTHETIC local draft kept through a conflict');
 const serverVersion=(await remote(id)).version;
 await p.evaluate(()=>window.requests=[]);
 await p.getByRole('button',{name:'Refresh case and retry',exact:true}).click();await p.locator('#evidence-choice').waitFor();
 const retry=await p.evaluate(()=>window.requests);
 assert.equal(retry[0].method,'GET');assert.match(retry[0].path,/^\/cases\/[^/]+$/);
 const plan=retry.find(r=>r.path.endsWith('/section-d')&&r.method==='POST');
 assert.ok(JSON.parse(plan.body).expected_version>=serverVersion);assert.equal(plan.status,200);
 const saved=await remote(id);
 assert.ok(saved.facts.some(f=>f.value==='SYNTHETIC second writer answer'),'other writer preserved');
 assert.ok(saved.facts.some(f=>f.value==='SYNTHETIC local draft kept through a conflict'),'local draft saved after reconcile');
 assert.equal(await assistance(p),0);
});

await scenario('R7 expired case: save and Section D say so plainly, never recreate, never retry, answers stay',async p=>{
 await act(p,candidate('3.1.9.1.(1)','yes'));await p.waitForFunction(()=>window.caseStore.c.sectionC.length===1);
 await evidence(p);await p.locator('#evidence-choice').waitFor();
 const id=await p.evaluate(()=>window.caseStore.engineId);
 const store=new DatabaseSync(db);store.prepare("UPDATE cases SET json=json_set(json,'$.created_at','2020-01-01T00:00:00+00:00') WHERE id=?").run(id);store.close();
 await p.evaluate(()=>window.requests=[]);
 await act(p,{type:'setProcess',field:'risk',value:'SYNTHETIC answer kept after expiry'});
 await p.getByText('This saved case is no longer available',{exact:false}).first().waitFor();
 await p.getByText('Case deleted or expired. Your answers stay here.',{exact:true}).waitFor();
 assert.equal(await p.getByRole('link',{name:'Keep a draft',exact:true}).count(),1,'one draft action, not a stack');
 assert.equal(await p.getByRole('button',{name:'Try saving again',exact:true}).count(),0);
 assert.equal(await p.getByRole('button',{name:'Refresh case and retry',exact:true}).count(),0);
 await nav(p,'/application?tab=A');await p.getByText('Case deleted or expired. Your answers stay here.',{exact:true}).waitFor();
 assert.equal(await p.evaluate(()=>window.caseStore.saveStatus),'gone');
 assert.equal(await p.evaluate(()=>window.caseStore.engineId),id);
 assert.equal(await p.evaluate(()=>window.caseStore.c.process.risk),'SYNTHETIC answer kept after expiry');
 assert.equal(await p.evaluate(()=>window.requests.some(r=>r.path==='/cases'&&r.method==='POST')),false,'no replacement case');
 assert.equal((await fetch(base+'/cases/'+id)).status,404);
 assert.equal(await assistance(p),0);
});

await browser.close();console.log(`R7 mounted UI: ${passed} passed, ${failed} failed`);process.exitCode=failed?1:0;
