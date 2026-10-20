import assert from 'node:assert/strict';
import {chromium} from 'playwright-core';
const web=process.env.SYNC_WEB_BASE, base=process.env.SYNC_TEST_BASE;
for(const url of [web,base]) assert.match(url??'',/^http:\/\/(127\.0\.0\.1|localhost):\d+/);
const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
let passed=0,failed=0;
const nav=(p,hash)=>p.evaluate(h=>location.hash='#'+h,hash);
const act=async(p,a)=>{await p.evaluate(a=>window.caseStore.dispatch(a),a);await p.evaluate(()=>new Promise(requestAnimationFrame));};
const candidate=(provision,answer=null)=>({type:'addCandidate',candidate:{id:'probe-'+provision,provision,answer,identified:true,suggestion:'search',part:3,benchmark:answer==='yes',topic:'Firestops',quote:{text:'',citation:'CodeDB'},departure:'depart from this sentence',clarifyingQuestion:'Which part changes?'}});
async function scenario(name,run){
 const page=await browser.newPage({viewport:{width:320,height:568},reducedMotion:'reduce'});page.setDefaultTimeout(6000);
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',r=>['127.0.0.1','localhost'].includes(new URL(r.request().url()).hostname)?r.continue():r.abort());
 await page.addInitScript(({base})=>{
  const original=window.fetch;
  window.requests=[];
  window.fetch=async(input,init)=>{
   const u=new URL(String(input),location.href);const target=base+u.pathname.replace(/^\/api/,'')+u.search;
   const entry={path:u.pathname.replace(/^\/api/,''),method:init?.method,body:init?.body,ack:false};window.requests.push(entry);
   const hold=window.hold;const match=hold&&!hold.used&&entry.path.endsWith(hold.suffix)&&entry.method===hold.method;
   if(match){hold.used=true;hold.ready=true;await new Promise(resolve=>window.release=resolve);}
   if(window.fail&&entry.path.endsWith(window.fail))return new Response(JSON.stringify({detail:'Synthetic unavailable response'}),{status:503});
   if(window.rejectPlan&&entry.path.endsWith('/section-d')&&entry.method==='POST'){
    const status=window.rejectPlan;window.rejectPlan=null;
    return new Response(JSON.stringify({detail:status===409?'case was updated concurrently':'case not found'}),{status});
   }
   const response=await original(target,init);entry.ack=response.ok;return response;
  };
 },{base});
 try{
  await page.goto(web+'/tests/check.html');await page.waitForFunction(()=>!!window.caseStore);
  await page.evaluate(()=>window.caseStore.beginEmpty('homebuilder'));
  await page.locator('#description').fill('Synthetic firestop review.');
  await page.evaluate(()=>window.caseStore.saveDraft());
  await run(page);assert.deepEqual(errors,[]);passed++;console.log('PASS',name);
 }catch(e){failed++;console.log('FAIL',name,e.message);}finally{await page.close();}
}
await scenario('A2 actual Enter/Tab, previous, jump, deep link and typing focus at 320px',async p=>{
 await nav(p,'/application?tab=A');await p.locator('#field-owner').fill('Synthetic Owner');await p.locator('#field-representative').fill('Synthetic Rep');
 await p.locator('.field-step').getByRole('button',{name:'Continue',exact:true}).focus();await p.keyboard.press('Enter');
 assert.equal(await p.evaluate(()=>document.activeElement.tagName),'H2');await p.keyboard.press('Tab');assert.equal(await p.evaluate(()=>document.activeElement.id),'field-mailingAddress');
 await p.locator('#field-mailingAddress').fill('Synthetic mailing address');await p.waitForTimeout(650);assert.equal(await p.evaluate(()=>document.activeElement.id),'field-mailingAddress');
 assert.ok(await p.locator('.scroll-body').evaluate(e=>e.scrollTop)<80);
 await p.getByRole('button',{name:'Previous',exact:true}).click();assert.equal(await p.evaluate(()=>document.activeElement.tagName),'H2');
 await p.locator('.jump-menu summary').click();await p.locator('.jump-menu').getByRole('button',{name:'Mailing address',exact:true}).click();assert.equal(await p.evaluate(()=>document.activeElement.tagName),'H2');
 await nav(p,'/application?tab=A&focus=field-owner');await p.waitForFunction(()=>document.activeElement.id==='field-owner');
});
await scenario('A3 320/390/desktop useful pane, six named destinations, help/error and short viewport',async p=>{
 await nav(p,'/application?tab=A');
 for(const size of [{width:320,height:568},{width:390,height:844},{width:1280,height:800}]){
  await p.setViewportSize(size);
  assert.ok(await p.locator('.scroll-body').evaluate(e=>e.clientHeight)>=220);
  assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 }
 await p.setViewportSize({width:320,height:568});await p.getByRole('button',{name:'Navigation',exact:true}).click();
 assert.equal(await p.locator('.navigation-dialog nav a').count(),6);assert.equal(await p.locator('.navigation-dialog nav a').evaluateAll(es=>es.every(e=>e.textContent.trim().length>0)),true);await p.keyboard.press('Escape');
 await p.locator('.draft-options > summary').click();await p.locator('.save-help > summary').click();
 assert.ok(await p.locator('.scroll-body').evaluate(e=>e.clientHeight)>=220);
 const bounds=await p.locator('.draft-options-body').boundingBox();assert.ok(bounds.y>=0&&bounds.y+bounds.height<=568);
 await p.evaluate(()=>window.fail='/facts');await p.locator('#field-owner').fill('Changed owner for synthetic failure');await p.waitForTimeout(750);
 await p.getByRole('button',{name:'Save draft',exact:true}).click();await p.getByRole('button',{name:'Try saving again',exact:true}).waitFor();
 await p.setViewportSize({width:320,height:340});assert.ok(await p.locator('.scroll-body').evaluate(e=>e.clientHeight)>=90);
 await p.getByRole('button',{name:'Try saving again',exact:true}).scrollIntoViewIfNeeded();const retry=await p.getByRole('button',{name:'Try saving again',exact:true}).boundingBox();assert.ok(retry.y>=0&&retry.y+retry.height<=340);
});
await scenario('U2 real CodeDB canonical UI and independent sentence answers',async p=>{
 await act(p,candidate('3.1.9.1.','yes'));await p.waitForFunction(()=>window.caseStore.c.sectionC.length===7&&window.caseStore.c.candidates.filter(a=>a.provision.startsWith('3.1.9.1.')).length===7);
 assert.equal(await p.evaluate(()=>window.caseStore.c.candidates.filter(a=>a.provision&&a.answer==='yes').length),0);
 await act(p,candidate('3.1.9.1.(5)'));await nav(p,'/section-c');await p.locator('#reference-choice').waitFor();assert.equal(await p.locator('#reference-choice option').count(),7);
 await p.locator('#reference-choice').selectOption('3.1.9.1.(5)');await p.locator('#sentence-decision').selectOption('yes');
 assert.equal(await p.evaluate(()=>window.caseStore.c.candidates.filter(a=>a.provision&&a.answer==='yes').length),1);
 await p.locator('#reference-choice').selectOption('3.1.9.1.(1)');assert.equal(await p.locator('#sentence-decision').inputValue(),'');
 await p.locator('#sentence-decision').selectOption('not-sure');await nav(p,'/application?tab=D');await p.getByRole('button',{name:'Evidence',exact:true}).click();await p.locator('#evidence-choice').waitFor();
 const id=await p.evaluate(()=>window.caseStore.engineId);const remote=await (await fetch(base+'/cases/'+id)).json();assert.deepEqual(remote.provisions,['3.1.9.1.(5)']);
});
await scenario('A1/N2 unfinished evidence survives view, item, route and refresh with one task per ID',async p=>{
 await act(p,candidate('3.1.9.1.(1)','yes'));await p.waitForFunction(()=>window.caseStore.c.sectionC.length===1);await nav(p,'/application?tab=D');await p.getByRole('button',{name:'Evidence',exact:true}).click();await p.locator('#evidence-choice').waitFor();
 const options=await p.locator('#evidence-choice option').evaluateAll(es=>es.map(e=>({id:e.value,label:e.textContent})));
 assert.ok(options.length>1);assert.equal(new Set(options.map(e=>e.id)).size,options.length);assert.ok(options.every(e=>!/^3\.|issue \d|evidence \d/.test(e.label)));
 assert.equal(new Set(options.map(e=>e.label)).size,options.length);
 await p.locator('input[id^=evidence-doc-]').fill('Unfinished synthetic report');await p.locator('input[id^=evidence-who-]').fill('Synthetic organisation');await p.locator('input[id^=evidence-date-]').fill('Revision pending');await p.locator('select[id^=evidence-type-]').selectOption('evaluation');
 await p.getByRole('button',{name:'Professional',exact:true}).click();await p.getByRole('button',{name:'Evidence',exact:true}).click();assert.equal(await p.locator('input[id^=evidence-doc-]').inputValue(),'Unfinished synthetic report');
 await p.locator('#evidence-choice').selectOption(options[1].id);await p.locator('#evidence-choice').selectOption(options[0].id);assert.equal(await p.locator('input[id^=evidence-who-]').inputValue(),'Synthetic organisation');
 await nav(p,'/application?tab=A');await nav(p,'/application?tab=D');await p.getByRole('button',{name:'Evidence',exact:true}).click();await p.locator('input[id^=evidence-doc-]').waitFor();assert.equal(await p.locator('input[id^=evidence-doc-]').inputValue(),'Unfinished synthetic report');
 assert.equal(await p.evaluate(()=>window.caseStore.c.facts.some(f=>f.value==='Unfinished synthetic report')),false);
 await p.getByRole('button',{name:'Save this evidence',exact:true}).click();assert.equal(await p.locator('input[id^=evidence-doc-]').inputValue(),'');
 await p.evaluate(()=>window.caseStore.resetToWho());await p.evaluate(()=>window.caseStore.beginEmpty('homebuilder'));assert.equal(await p.evaluate(()=>Object.keys(window.caseStore.c.evidenceDrafts??{}).length),0);
});
await scenario('U5 held plan write then changed provision is serialized and publishes latest real-engine model',async p=>{
 await act(p,candidate('3.1.9.1.(1)','yes'));await p.waitForFunction(()=>window.caseStore.c.sectionC.length===1);
 await p.evaluate(()=>window.hold={suffix:'/section-d',method:'POST'});await nav(p,'/application?tab=D');await p.waitForFunction(()=>window.hold?.ready);
 await act(p,{type:'answerCandidate',id:'probe-3.1.9.1.(1)',answer:'no'});await act(p,candidate('3.1.9.1.(5)','yes'));await p.waitForFunction(()=>window.caseStore.c.sectionC.length===2);
 await p.evaluate(()=>window.release());await p.getByRole('button',{name:'Evidence',exact:true}).click();await p.locator('#evidence-choice').waitFor();
 const id=await p.evaluate(()=>window.caseStore.engineId);const remote=await(await fetch(base+'/cases/'+id)).json();assert.deepEqual(remote.provisions,['3.1.9.1.(5)']);
 const reqs=await p.evaluate(()=>window.requests.filter(r=>/section-d/.test(r.path)));assert.equal(reqs.at(-1).method,'GET');assert.ok(reqs.filter(r=>r.method==='POST').every(r=>r.ack));
 assert.equal(await p.locator('#evidence-choice option').count(),1);assert.doesNotMatch(await p.locator('main').innerText(),/No provision yet/);
 await p.evaluate(()=>window.fail='/section-d/issues');await act(p,{type:'setProcess',field:'risk',value:'A new synthetic answer'});await p.getByText('Couldn’t load this information.',{exact:true}).waitFor();assert.equal(await p.locator('#evidence-choice').count(),0);
});
await scenario('U5 latest fact acknowledgement precedes plan; reset rejects held plan output',async p=>{
 await act(p,candidate('3.1.9.1.(1)','yes'));await p.waitForFunction(()=>window.caseStore.c.sectionC.length===1);
 await p.evaluate(()=>{window.requests=[];window.hold={suffix:'/facts',method:'POST'};});
 await act(p,{type:'setProcess',field:'risk',value:'Current synthetic risk answer'});await nav(p,'/application?tab=D');await p.waitForFunction(()=>window.hold?.ready);
 assert.equal(await p.evaluate(()=>window.requests.filter(r=>r.path.endsWith('/section-d')).length),0);
 await p.evaluate(()=>window.release());await p.getByRole('button',{name:'Evidence',exact:true}).click();await p.locator('#evidence-choice').waitFor();
 const id=await p.evaluate(()=>window.caseStore.engineId);const remote=await(await fetch(base+'/cases/'+id)).json();assert.ok(remote.facts.some(f=>f.value==='Current synthetic risk answer'));
 await p.evaluate(()=>window.hold={suffix:'/section-d',method:'POST'});await act(p,{type:'setProcess',field:'risk',value:'Withdraw this visit'});await p.waitForFunction(()=>window.hold?.ready);
 await p.evaluate(()=>window.caseStore.resetToWho());await p.evaluate(()=>window.caseStore.beginEmpty('contractor'));await p.evaluate(()=>window.release());await p.waitForTimeout(300);
 assert.equal(await p.evaluate(()=>window.caseStore.engineId),null);assert.equal(await p.evaluate(()=>window.caseStore.c.facts.length),0);assert.equal(await p.locator('#evidence-choice').count(),0);
});
await scenario('N1 continuous forward/back includes all six alternative groups before professional details',async p=>{
 const next=async()=>{const action=p.locator('.field-step').getByText('Continue',{exact:true});await action.click();};
 await next();await next();await p.locator('#field-owner').waitFor();await p.getByRole('link',{name:'Previous',exact:true}).click();await p.locator('#authority').waitFor();await next();
 await next();await next();await p.locator('#field-scope').waitFor();await p.getByRole('link',{name:'Previous',exact:true}).click();await p.locator('#field-mailingAddress').waitFor();await next();
 await next();await next();await next();await p.getByRole('button',{name:'Continue',exact:true}).click();await p.getByRole('button',{name:'Continue',exact:true}).click();
 const visited=[];for(let i=0;i<6;i++){await p.locator('.field-step textarea').waitFor();visited.push(await p.locator('.field-step textarea').getAttribute('id'));await next();}
 assert.deepEqual(visited,['field-rationale','field-risk','field-mitigation','field-assumptions','field-maintenance','field-qualifications']);await p.locator('#prof-role').waitFor();
 await p.locator('#prof-role').selectOption('not_sure');await p.getByRole('button',{name:'Continue to evidence',exact:true}).waitFor();await next();await p.locator('#prof-occupancy').waitFor();assert.equal(await p.locator('#prof-registration_number').count(),0);
});
await scenario('N3 failure has a visible first-item recovery; officer copy is above the fold at 390px',async p=>{
 await p.setViewportSize({width:390,height:844});await nav(p,'/application?tab=A');await p.getByRole('button',{name:'Ready to submit',exact:true}).click();await p.locator('#completeness-description').filter({hasText:'Check unavailable. Your work is still here.'}).waitFor();
 await p.getByRole('button',{name:'Continue filling missing details',exact:true}).click();await p.waitForFunction(()=>!document.querySelector('dialog[open]'));assert.ok(await p.locator('.field-step').count());
 await nav(p,'/officer');const button=p.getByRole('button',{name:'Copy request',exact:true});await button.waitFor();await p.waitForFunction(()=>!Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='Copy request')?.disabled);const box=await button.boundingBox();assert.ok(box.y+box.height<844);
});
await scenario('U5 conflict needs explicit fresh-case retry; deleted case is terminal with client answers retained',async p=>{
 await act(p,candidate('3.1.9.1.(1)','yes'));await p.waitForFunction(()=>window.caseStore.c.sectionC.length===1);
 await p.evaluate(()=>window.rejectPlan=409);await nav(p,'/application?tab=D');await p.getByRole('button',{name:'Evidence',exact:true}).click();
 await p.getByRole('button',{name:'Refresh case and retry',exact:true}).waitFor();
 const writes=await p.evaluate(()=>window.requests.filter(r=>r.path.endsWith('/section-d')&&r.method==='POST').length);
 await act(p,{type:'setProcess',field:'risk',value:'Retained unsaved answer'});await nav(p,'/application?tab=A');await nav(p,'/application?tab=D');await p.getByRole('button',{name:'Evidence',exact:true}).click();
 await p.getByRole('button',{name:'Refresh case and retry',exact:true}).waitFor();
 assert.equal(await p.evaluate(()=>window.requests.filter(r=>r.path.endsWith('/section-d')&&r.method==='POST').length),writes);
 await p.evaluate(()=>window.requests=[]);await p.getByRole('button',{name:'Refresh case and retry',exact:true}).click();await p.locator('#evidence-choice').waitFor();
 const retry=await p.evaluate(()=>window.requests);assert.match(retry[0].path,/^\/cases\/[^/]+$/);assert.equal(retry[0].method,'GET');assert.equal(retry[0].ack,true);
 assert.ok(retry.findIndex(r=>r.path.endsWith('/section-d')&&r.method==='POST')>0);
 await p.locator('input[id^=evidence-doc-]').fill('Unfinished retained document');
 const caseId=await p.evaluate(()=>window.caseStore.engineId);await p.evaluate(()=>window.rejectPlan=404);await act(p,{type:'setProcess',field:'risk',value:'Another retained answer'});
 await p.getByText('This saved case is no longer available.',{exact:false}).waitFor();
 assert.equal(await p.getByRole('button',{name:'Refresh case and retry',exact:true}).count(),0);
 await p.evaluate(()=>window.requests=[]);await nav(p,'/application?tab=A');await nav(p,'/application?tab=D');await p.getByRole('button',{name:'Evidence',exact:true}).click();
 await p.getByText('This saved case is no longer available.',{exact:false}).waitFor();
 assert.equal(await p.evaluate(()=>window.caseStore.engineId),caseId);
 assert.equal(await p.evaluate(()=>window.requests.some(r=>r.path==='/cases'&&r.method==='POST')),false);
 assert.equal(await p.evaluate(()=>window.requests.some(r=>r.path.endsWith('/section-d'))),false);
 assert.ok(await p.evaluate(()=>Object.values(window.caseStore.c.evidenceDrafts).some(d=>d.document==='Unfinished retained document')));
 assert.equal(await p.evaluate(()=>window.requests.some(r=>/identify|completeness/.test(r.path))),false);
});
await browser.close();console.log(`R4 mounted UI: ${passed} passed, ${failed} failed`);process.exitCode=failed?1:0;
