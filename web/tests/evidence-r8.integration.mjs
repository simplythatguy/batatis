// R8 mounted document entry against the real engine: one step at a time (name, type, optional
// details), one atomic save per document, honest unsaved/conflict/gone states, edit and removal.
// No assistance is requested by typing, saving or recovery. Test data is labelled SYNTHETIC.
import assert from 'node:assert/strict';
import {chromium} from 'playwright-core';
const web=process.env.SYNC_WEB_BASE, base=process.env.SYNC_TEST_BASE;
for(const url of [web,base]) assert.match(url??'',/^http:\/\/(127\.0\.0\.1|localhost):\d+/);
const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
let passed=0,failed=0;
const nav=(p,hash)=>p.evaluate(h=>location.hash='#'+h,hash);
const act=async(p,a)=>{await p.evaluate(a=>window.caseStore.dispatch(a),a);await p.evaluate(()=>new Promise(requestAnimationFrame));};
const candidate=(provision,answer=null)=>({type:'addCandidate',candidate:{id:'probe-'+provision,provision,answer,identified:true,suggestion:'search',part:3,benchmark:answer==='yes',topic:'Firestops',quote:{text:'',citation:'CodeDB'},departure:'depart from this sentence',clarifyingQuestion:'Which part changes?'}});
const remote=async id=>(await fetch(base+'/cases/'+id)).json();
const sent=(p,method,re)=>p.evaluate(([m,s])=>window.requests.filter(r=>r.method===m&&new RegExp(s).test(r.path)).map(r=>({body:r.body?JSON.parse(r.body):null,status:r.status})),[method,re]);
const assistance=p=>p.evaluate(()=>window.requests.filter(r=>/identify|completeness|information-request|\/gaps/.test(r.path)).length);
const entry=p=>p.locator('.doc-entry');
const visibleFields=p=>entry(p).locator('input:visible, select:visible, textarea:visible').evaluateAll(es=>es.map(e=>e.id.replace(/-ev_.*$/,'')));
const row=(p,title)=>p.locator('.doc-list li').filter({hasText:title});
async function evidence(p){await nav(p,'/application?tab=D');await p.getByRole('button',{name:'Evidence',exact:true}).click();await p.locator('#evidence-choice').waitFor();}
async function enter(p,{name,type,who='',date=''}){
 await entry(p).getByLabel('Document name').fill(name);await entry(p).getByRole('button',{name:'Continue',exact:true}).click();
 await entry(p).getByLabel('Document type').selectOption(type);await entry(p).getByRole('button',{name:'Continue',exact:true}).click();
 if(who) await entry(p).getByLabel('Prepared by (optional)').fill(who);
 if(date) await entry(p).getByLabel('Date or revision (optional)').fill(date);
 await entry(p).getByRole('button',{name:'Save document',exact:true}).click();
}
async function scenario(name,run,viewport={width:390,height:844}){
 const page=await browser.newPage({viewport,reducedMotion:'reduce'});page.setDefaultTimeout(8000);
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',r=>['127.0.0.1','localhost'].includes(new URL(r.request().url()).hostname)?r.continue():r.abort());
 await page.addInitScript(({base})=>{
  const original=window.fetch;
  window.requests=[];window.dropNext=null;
  window.fetch=async(input,init)=>{
   const u=new URL(String(input),location.href);const path=u.pathname.replace(/^\/api/,'');const method=init?.method??'GET';
   const entry={path,method,body:init?.body,status:0};window.requests.push(entry);
   if(window.dropNext&&window.dropNext.method===method&&path.endsWith(window.dropNext.suffix)){window.dropNext=null;entry.status=-1;throw new TypeError('SYNTHETIC network failure before the engine');}
   const response=await original(base+path+u.search,init);entry.status=response.status;return response;
  };
 },{base});
 try{
  await page.goto(web+'/tests/check.html');await page.waitForFunction(()=>!!window.caseStore);
  await page.evaluate(()=>window.caseStore.beginEmpty('contractor'));
  await page.locator('#description').fill('SYNTHETIC firestop review for an R8 regression.');
  await page.evaluate(()=>window.caseStore.saveDraft());
  await act(page,candidate('3.1.9.1.(1)','yes'));await page.waitForFunction(()=>window.caseStore.c.sectionC.length===1);
  await evidence(page);
  await run(page);assert.deepEqual(errors,[]);passed++;console.log('PASS',name);
 }catch(e){failed++;console.log('FAIL',name,e.stack);}finally{await page.close();}
}

await scenario('R8 guided entry shows one step at a time, keeps answers on Back, saves once and is edited and removed through the real engine',async p=>{
 const task=await p.locator('#evidence-choice').inputValue();
 const id=await p.evaluate(()=>window.caseStore.engineId);
 assert.deepEqual(await visibleFields(p),['evidence-doc'],'step 1 asks for the name only');
 await p.evaluate(()=>window.requests=[]);
 await entry(p).getByRole('button',{name:'Continue',exact:true}).click();
 await entry(p).getByText('Enter the document name.',{exact:true}).waitFor();
 await entry(p).getByLabel('Document name').fill('SYNTHETIC firestop test report');
 await entry(p).getByRole('button',{name:'Continue',exact:true}).click();
 assert.deepEqual(await visibleFields(p),['evidence-type'],'step 2 asks for the type only');
 await entry(p).getByRole('button',{name:'Back',exact:true}).click();
 assert.equal(await entry(p).getByLabel('Document name').inputValue(),'SYNTHETIC firestop test report');
 assert.equal(await p.evaluate(()=>document.activeElement?.id.startsWith('evidence-doc-')),true,'focus follows the step');
 await entry(p).getByRole('button',{name:'Continue',exact:true}).click();
 await entry(p).getByRole('button',{name:'Continue',exact:true}).click();
 await entry(p).getByText('Choose a document type.',{exact:true}).waitFor();
 await entry(p).getByLabel('Document type').selectOption('evaluation');
 await entry(p).getByRole('button',{name:'Continue',exact:true}).click();
 assert.deepEqual(await visibleFields(p),['evidence-who','evidence-date'],'step 3 holds only optional details');
 assert.equal(await entry(p).getByRole('button',{name:'Save document',exact:true}).count(),1);
 assert.equal(await p.locator('.doc-entry .btn-primary:visible').count(),1,'one primary action per step');
 await entry(p).getByLabel('Prepared by (optional)').fill('SYNTHETIC designer');
 await entry(p).getByRole('button',{name:'Save document',exact:true}).click();
 await row(p,'SYNTHETIC firestop test report').getByText(/^Saved/).waitFor();
 assert.match(await row(p,'SYNTHETIC firestop test report').innerText(),/no file/i);
 assert.deepEqual(await visibleFields(p),['evidence-doc'],'ready for another document');
 assert.equal(await entry(p).getByLabel('Document name').inputValue(),'');
 const created=await sent(p,'POST','/evidence$');
 assert.equal(created.length,1);
 const known=created[0].body.expected_version;
 assert.deepEqual(created[0].body,{operation:'create',evidence_id:task,expected_version:known,title:'SYNTHETIC firestop test report',description:'SYNTHETIC firestop test report',evidence_type:'evaluation',responsible_party:'SYNTHETIC designer',scope:{item_id:task}});
 assert.equal(created[0].status,200);
 assert.equal((await sent(p,'POST','/facts$')).filter(r=>String(r.body.field).startsWith('evidence.')).length,0);
 let saved=await remote(id);
 assert.equal(saved.version,known+1);assert.deepEqual(saved.evidence.map(e=>[e.id,e.kind]),[[task,'text']]);
 // Edit: the same steps, prefilled; the save is an update without scope.
 await row(p,'SYNTHETIC firestop test report').getByRole('button',{name:'Edit SYNTHETIC firestop test report'}).click();
 assert.equal(await entry(p).getByLabel('Document name').inputValue(),'SYNTHETIC firestop test report');
 await entry(p).getByLabel('Document name').fill('SYNTHETIC firestop test report rev 2');
 await entry(p).getByRole('button',{name:'Continue',exact:true}).click();
 assert.equal(await entry(p).getByLabel('Document type').inputValue(),'evaluation');
 await entry(p).getByRole('button',{name:'Continue',exact:true}).click();
 assert.equal(await entry(p).getByLabel('Prepared by (optional)').inputValue(),'SYNTHETIC designer');
 await entry(p).getByRole('button',{name:'Save document',exact:true}).click();
 await row(p,'SYNTHETIC firestop test report rev 2').getByText(/^Saved/).waitFor();
 const update=(await sent(p,'POST','/evidence$')).at(-1);
 assert.equal(update.body.operation,'update');assert.equal(update.body.evidence_id,task);assert.equal('scope' in update.body,false);
 assert.equal(await p.locator('.doc-list li').count(),1,'edited, not duplicated');
 // Remove: versioned DELETE, gone only after the engine answers.
 await row(p,'SYNTHETIC firestop test report rev 2').getByRole('button',{name:'Remove SYNTHETIC firestop test report rev 2'}).click();
 await p.waitForFunction(()=>!document.querySelector('.doc-list li'));
 const del=(await sent(p,'DELETE','/evidence/'))[0];
 assert.ok(Number.isInteger(del.body.expected_version));assert.equal(del.status,200);
 saved=await remote(id);assert.deepEqual(saved.evidence,[]);
 assert.equal(await assistance(p),0,'no assistance on type, save, edit or removal');
});

await scenario('R8 a failed save is never shown as saved; the labelled retry saves it once',async p=>{
 await p.evaluate(()=>window.dropNext={method:'POST',suffix:'/evidence'});
 await enter(p,{name:'SYNTHETIC unsent report',type:'evaluation'});
 await row(p,'SYNTHETIC unsent report').getByText('Not saved yet',{exact:true}).waitFor();
 await p.waitForFunction(()=>window.caseStore.saveStatus==='failed');
 assert.equal(await row(p,'SYNTHETIC unsent report').getByText('Not saved yet',{exact:true}).count(),1);
 assert.equal(await row(p,'SYNTHETIC unsent report').getByText(/^Saved/).count(),0);
 await p.locator('.doc-list').getByRole('button',{name:'Try saving again',exact:true}).click();
 await row(p,'SYNTHETIC unsent report').getByText(/^Saved/).waitFor();
 const posts=await sent(p,'POST','/evidence$');
 assert.deepEqual(posts.map(r=>r.status),[-1,200]);
 const id=await p.evaluate(()=>window.caseStore.engineId);
 assert.equal((await remote(id)).evidence.length,1);
 assert.equal(await assistance(p),0);
});

await scenario('R8 a second writer is a real 409: the document stays unsaved until the explicit refresh, and nothing is overwritten',async p=>{
 const id=await p.evaluate(()=>window.caseStore.engineId);
 const other=await fetch(base+`/cases/${id}/facts`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({field:'process.maintenance_operation',value:'SYNTHETIC second writer',kind:'pointed',status:'confirmed',source:{type:'user_text',ref:'SYNTHETIC second writer',quote:'x'}})});
 assert.equal(other.status,200);
 await enter(p,{name:'SYNTHETIC conflict report',type:'evaluation'});
 await row(p,'SYNTHETIC conflict report').getByText('Not saved yet',{exact:true}).waitFor();
 await p.waitForFunction(()=>window.caseStore.saveStatus==='failed');
 assert.deepEqual((await sent(p,'POST','/evidence$')).map(r=>r.status),[409]);
 await p.waitForTimeout(900);
 assert.equal((await sent(p,'POST','/evidence$')).length,1,'no automatic retry');
 await p.evaluate(()=>window.requests=[]);
 await p.locator('.doc-list').getByRole('button',{name:'Try saving again',exact:true}).click();
 await row(p,'SYNTHETIC conflict report').getByText(/^Saved/).waitFor();
 const order=await p.evaluate(()=>window.requests.map(r=>`${r.method} ${r.path.replace(/\/cases\/[^/]+/,'/cases/:id')}`));
 assert.equal(order[0],'GET /cases/:id','refresh before writing again');
 const saved=await remote(id);
 assert.ok(saved.facts.some(f=>f.value==='SYNTHETIC second writer'));
 assert.equal(saved.evidence.length,1);
 assert.equal(await assistance(p),0);
});

await scenario('R8 deleted case: the document stays here unsaved, one honest next action, no Ready button, never recreated',async p=>{
 const id=await p.evaluate(()=>window.caseStore.engineId);
 assert.equal((await fetch(base+'/cases/'+id,{method:'DELETE'})).status,204);
 await p.evaluate(()=>window.requests=[]);
 await enter(p,{name:'SYNTHETIC report after deletion',type:'evaluation'});
 await p.getByText('Case deleted or expired. Your answers stay here.',{exact:true}).waitFor();
 await row(p,'SYNTHETIC report after deletion').getByText('Not saved',{exact:false}).waitFor();
 assert.equal(await p.getByRole('button',{name:'Ready to submit',exact:true}).count(),0,'no action that cannot work');
 assert.equal(await p.getByRole('button',{name:'Try saving again',exact:true}).count(),0);
 assert.equal(await p.getByRole('link',{name:'Keep a draft',exact:true}).count(),1);
 assert.equal(await p.evaluate(()=>window.requests.some(r=>r.path==='/cases'&&r.method==='POST')),false);
 assert.equal((await fetch(base+'/cases/'+id)).status,404);
 assert.equal(await assistance(p),0);
},{width:320,height:568});

await scenario('R8 at 320x568 the gone footer is one compact line and leaves the step action on screen',async p=>{
 const id=await p.evaluate(()=>window.caseStore.engineId);
 assert.equal((await fetch(base+'/cases/'+id,{method:'DELETE'})).status,204);
 await act(p,{type:'setProcess',field:'risk',value:'SYNTHETIC answer after deletion'});
 await p.getByText('This saved case is no longer available',{exact:false}).first().waitFor();
 await nav(p,'/application?tab=A');await p.locator('.field-step').waitFor();
 await p.getByText('Case deleted or expired. Your answers stay here.',{exact:true}).waitFor();
 assert.equal(await p.getByRole('button',{name:'Ready to submit',exact:true}).count(),0);
 const button=p.locator('.field-step .step-controls .btn-primary');
 const box=await button.boundingBox();const footer=await p.locator('.footer-bar').first().boundingBox();
 assert.ok(box.y>=0&&box.y+box.height<=footer.y,`Continue (${box.y}+${box.height}) sits above the footer (${footer.y})`);
 assert.ok(footer.height<=96,`compact footer (${footer.height}px)`);
 assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
},{width:320,height:568});

await browser.close();console.log(`R8 mounted UI: ${passed} passed, ${failed} failed`);process.exitCode=failed?1:0;
