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
 }catch(e){failed++;console.log('FAIL',name,e.stack);}finally{await page.close();}
}

await scenario('R6 sentence clear withdraws confirmation, refreshes saved plan, and the final clear persists an empty selection',async p=>{
 for(const ref of ['3.1.9.1.(1)','3.1.9.1.(2)']) await act(p,candidate(ref,'yes'));
 await p.waitForFunction(()=>window.caseStore.c.sectionC.length===2);
 await nav(p,'/application?tab=D');await p.getByRole('button',{name:'Evidence',exact:true}).click();await p.locator('#evidence-choice').waitFor();
 const id=await p.evaluate(()=>window.caseStore.engineId);
 const saved=async()=>await (await fetch(base+'/cases/'+id)).json();
 assert.deepEqual((await saved()).provisions,['3.1.9.1.(1)','3.1.9.1.(2)']);
 await nav(p,'/section-c');await p.locator('#reference-choice').selectOption('3.1.9.1.(2)');
 assert.equal(await p.locator('#sentence-decision option[value=""]').isDisabled(),false);
 await p.locator('#sentence-decision').selectOption('');assert.equal(await p.locator('#sentence-decision').inputValue(),'');
 assert.equal(await p.evaluate(()=>window.caseStore.c.candidates.find(c=>c.provision==='3.1.9.1.(2)').benchmark),false);
 await nav(p,'/application?tab=D');await p.getByRole('button',{name:'Evidence',exact:true}).click();await p.locator('#evidence-choice').waitFor();
 assert.deepEqual((await saved()).provisions,['3.1.9.1.(1)']);
 assert.ok((await (await fetch(base+'/cases/'+id+'/section-d/issues')).json()).items.every(i=>i.provision?.provision_id==='3.1.9.1.(1)'));
 await nav(p,'/section-c');await p.locator('#reference-choice').selectOption('3.1.9.1.(1)');await p.locator('#sentence-decision').selectOption('');
 await nav(p,'/application?tab=D');await p.getByRole('button',{name:'Evidence',exact:true}).click();
 await p.getByText('No code references selected.',{exact:false}).waitFor();
 assert.equal(await p.locator('#evidence-choice').count(),0);assert.deepEqual([(await saved()).provisions,(await saved()).section_c],[[],[]]);
 await nav(p,'/section-c');await p.locator('#reference-choice').selectOption('3.1.9.1.(1)');assert.equal(await p.locator('#sentence-decision').inputValue(),'');
 await p.locator('#sentence-decision').selectOption('yes');await nav(p,'/application?tab=D');await p.getByRole('button',{name:'Evidence',exact:true}).click();await p.locator('#evidence-choice').waitFor();
 assert.deepEqual((await saved()).provisions,['3.1.9.1.(1)']);
});
await scenario('R6 seven real tasks across two sentences and two building objectives stay distinct with per-key drafts',async p=>{
 for(const ref of ['3.1.9.1.(1)','3.1.9.1.(2)']) await act(p,candidate(ref,'yes'));
 await p.waitForFunction(()=>window.caseStore.c.sectionC.length===2);await nav(p,'/application?tab=D');await p.getByRole('button',{name:'Evidence',exact:true}).click();await p.locator('#evidence-choice').waitFor();
 const options=await p.locator('#evidence-choice option').evaluateAll(es=>es.map(e=>({id:e.value,label:e.textContent})));
 assert.equal(options.length,7);assert.equal(new Set(options.map(o=>o.label)).size,7);assert.equal(new Set(options.map(o=>o.id)).size,7);
 const id=await p.evaluate(()=>window.caseStore.engineId);const issues=(await (await fetch(base+'/cases/'+id+'/section-d/issues')).json()).items;
 const collision=issues.filter(i=>i.provision?.provision_id==='3.1.9.1.(2)'&&['OP3.1','OP1.2'].includes(i.objective));assert.equal(collision.length,2);
 assert.notEqual(options.find(o=>o.id===collision[0].id).label,options.find(o=>o.id===collision[1].id).label);
 for(const [n,o] of options.entries()) {await p.locator('#evidence-choice').selectOption(o.id);assert.equal(await p.locator('input[id^=evidence-doc-]').count(),1);await p.locator('input[id^=evidence-doc-]').fill('TEST draft '+n);}
 for(const [n,o] of options.entries()) {await p.locator('#evidence-choice').selectOption(o.id);assert.equal(await p.locator('input[id^=evidence-doc-]').inputValue(),'TEST draft '+n);}
 assert.equal(await p.locator('details[open]').count(),0);
 assert.equal(await p.getByText('Recommend evidence that addresses',{exact:false}).isVisible(),false);
 await p.getByRole('button',{name:'Save this evidence',exact:true}).click();assert.ok(await p.getByText('Add the document, person responsible and evidence type.',{exact:true}).isVisible());
 assert.equal(await p.evaluate(()=>window.caseStore.c.facts.some(f=>String(f.value).startsWith('TEST draft'))),false);
});
await scenario('R6 occupancy and numeric clearing remove actual persisted facts; known and Not sure still work',async p=>{
 await nav(p,'/application?tab=D');await p.locator('#prof-role').selectOption('not_sure');await p.getByRole('button',{name:'Add more details',exact:true}).click();
 await p.locator('#prof-occupancy').selectOption('single_family');await p.evaluate(()=>window.caseStore.saveDraft());
 const id=await p.evaluate(()=>window.caseStore.engineId);const facts=async()=> (await (await fetch(base+'/cases/'+id)).json()).facts;
 const withdrawn=async field=>{const f=[...(await facts())].reverse().find(f=>f.field===field);assert.equal(f.value,'');assert.equal(f.status,'unconfirmed');assert.equal(f.source.ref,'Answer withdrawn by applicant');};
 assert.equal([...(await facts())].reverse().find(f=>f.field==='professional.occupancy').value,'single_family');
 assert.equal(await p.locator('#prof-occupancy option[value=""]').isDisabled(),false);
 await p.locator('#prof-occupancy').selectOption('');assert.equal(await p.locator('#prof-occupancy').inputValue(),'');
 assert.equal(await p.evaluate(()=>window.caseStore.c.facts.some(f=>f.field==='professional.occupancy')),false);await p.evaluate(()=>window.caseStore.saveDraft());
 await withdrawn('professional.occupancy');
 await p.locator('#prof-occupancy').selectOption('multi_family');await p.evaluate(()=>window.caseStore.saveDraft());assert.equal([...(await facts())].reverse().find(f=>f.field==='professional.occupancy').value,'multi_family');
 await nav(p,'/application?tab=D&focus=prof-building_area_m2');await p.locator('#prof-building_area_m2').fill('120.5');await p.evaluate(()=>window.caseStore.saveDraft());assert.equal([...(await facts())].reverse().find(f=>f.field==='professional.building_area_m2').value,120.5);
 await p.locator('#prof-building_area_m2').fill('');await p.evaluate(()=>window.caseStore.saveDraft());await withdrawn('professional.building_area_m2');
 await nav(p,'/application?tab=D&focus=prof-part4_design');await p.locator('#prof-part4_design').selectOption('yes');await p.evaluate(()=>window.caseStore.saveDraft());assert.equal([...(await facts())].reverse().find(f=>f.field==='professional.part4_design').value,true);
 await p.locator('#prof-part4_design').selectOption('not-sure');await p.evaluate(()=>window.caseStore.saveDraft());await withdrawn('professional.part4_design');assert.equal(await p.locator('#prof-part4_design').inputValue(),'not-sure');
});

await scenario('U8 deferral makes evidence primary and optional questions remain reachable',async p=>{
 await nav(p,'/application?tab=D');await p.locator('#prof-role').selectOption('not_sure');
 const primary=p.locator('.field-step .btn-primary');assert.equal(await primary.count(),1);assert.equal(await primary.innerText(),'Add evidence');await primary.click();await p.getByRole('button',{name:'Evidence',exact:true}).getAttribute('aria-pressed').then(v=>assert.equal(v,'true'));
 await p.getByRole('button',{name:'Professional',exact:true}).click();await p.getByRole('button',{name:'Add more details',exact:true}).click();await p.locator('#prof-occupancy').waitFor();assert.equal(await p.locator('#prof-registration_number').count(),0);
 await p.getByRole('button',{name:'Previous',exact:true}).click();assert.equal(await p.locator('#prof-role').inputValue(),'not_sure');assert.equal(await p.locator('.field-step .btn-primary').innerText(),'Add evidence');
});
await scenario('N4 real manual article add closes search and focuses the new sentence with results retained',async p=>{
 await nav(p,'/code-check');await p.locator('.manual-search > summary').click();await p.locator('#code-search').fill('firestop');await p.locator('.manual-search').getByRole('button',{name:'Search',exact:true}).click();
 const result=p.locator('.manual-search li').filter({has:p.locator('.article-id').getByText('3.1.9.1.',{exact:true})});
 await result.getByRole('button',{name:'Add to this check',exact:true}).click();
 await p.waitForFunction(()=>window.caseStore.c.sectionC.length===7);
 assert.equal(await p.locator('.manual-search').getAttribute('open'),null);
 const card=p.locator('article[id^="cand-"]');assert.equal(await card.count(),1);assert.ok((await card.innerText()).includes('3.1.9.1.(1)'));
 assert.equal(await card.evaluate(e=>e===document.activeElement),true);const box=await card.boundingBox();assert.ok(box.y>=0&&box.y<568);
 await p.locator('.manual-search > summary').click();assert.equal(await p.locator('.manual-search li').count(),8);
 // Re-adding an expanded article also returns to its existing sentence, not a duplicate.
 await result.getByRole('button',{name:'Add to this check',exact:true}).click();await p.waitForFunction(()=>document.activeElement?.id.startsWith('cand-'));
 assert.equal(await p.locator('.manual-search').getAttribute('open'),null);await p.waitForFunction(()=>window.caseStore.c.candidates.filter(c=>c.provision.startsWith('3.1.9.1.')).length===7);
 // A single existing child must not prevent adding the article's other sentences.
 const siblings=await p.evaluate(()=>window.caseStore.c.candidates.filter(c=>c.provision.startsWith('3.1.9.1.')&&c.provision!=='3.1.9.1.(1)').map(c=>c.id));
 for(const id of siblings) await act(p,{type:'removeCandidate',id});
 await p.waitForFunction(()=>window.caseStore.c.sectionC.length===1);
 await p.locator('.manual-search > summary').click();await result.getByRole('button',{name:'Add to this check',exact:true}).click();
 await p.waitForFunction(()=>window.caseStore.c.sectionC.length===7&&window.caseStore.c.candidates.filter(c=>c.provision.startsWith('3.1.9.1.')).length===7);
});
await scenario('N5 officer keeps six distinct departure questions and copy references',async p=>{
 await act(p,candidate('3.1.9.1.'));await p.waitForFunction(()=>window.caseStore.c.sectionC.length===7);await nav(p,'/section-c');await p.locator('#sentence-decision').selectOption('yes');await nav(p,'/officer');
 await p.locator('#request-text').waitFor({state:'attached'});const request=await p.locator('#request-text').inputValue();
 const labels=await p.locator('a[href^="#/code-check"]').allTextContents();
 for(let n=2;n<=7;n++){assert.ok(labels.some(s=>s.includes(`3.1.9.1.(${n})`)&&/depart/i.test(s)));assert.ok(request.includes(`3.1.9.1.(${n})`));}
 assert.equal(request.includes('relies on firestops'),false);
 await p.locator('a[href^="#/code-check"]').filter({hasText:'depart from 3.1.9.1.(6)'}).click();
 assert.ok((await p.locator('article[id^="cand-"]').innerText()).includes('3.1.9.1.(6)'));
});
await browser.close();console.log(`R6 mounted UI: ${passed} passed, ${failed} failed`);process.exitCode=failed?1:0;
