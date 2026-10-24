import assert from 'node:assert/strict';
import { createEngine } from '../src/api/client.ts';
import * as sync from '../src/api/sync.ts';
import { emptyCase } from '../src/intake.ts';
import { reducer } from '../src/model.ts';
import { professionalRouteNote } from '../src/humanReview.ts';
import { professionalConfirmed } from '../src/professional.ts';
import { checkSavedAliases } from './aliases.integration.ts';
import { checkPreparation } from './preparation.integration.ts';
const raw=process.env.SYNC_TEST_BASE;
assert.ok(raw, 'Set SYNC_TEST_BASE to an isolated local engine with a code database; never production.');
assert.match(raw, /^http:\/\/(127\.0\.0\.1|localhost):\d+/);
const originalFetch=globalThis.fetch;
globalThis.sessionStorage={data:new Map(),getItem(k){return this.data.get(k)??null},setItem(k,v){this.data.set(k,String(v))},removeItem(k){this.data.delete(k)},clear(){this.data.clear()}};
globalThis.fetch=(input,init)=>originalFetch(typeof input==='string'&&input.startsWith('/api')?raw+input.slice(4):input,init);
const plain=createEngine(raw);
const results=[];
async function check(name,work){try{await work();results.push({name,status:'PASS'});}catch(e){results.push({name,status:'FAIL',error:String(e)});}}
let c=emptyCase('homebuilder');
let cid;
await check('setup synthetic case and confirmed professional',async()=>{
 cid=await sync.ensureEngineCase('SYNTHETIC withdrawal case','edmonton');
 c=reducer(c,{type:'setProfessionalFact',field:'role',value:'engineer'});
 c=reducer(c,{type:'setProfessionalFact',field:'registration_number',value:'SYNTHETIC-000'});
 c=reducer(c,{type:'answerScope',field:'part4_design',answer:'yes'});
 assert.equal(await sync.pushFacts(cid,c.facts),null);
 const got=await plain.getCase(cid); assert.equal(professionalConfirmed(got.facts),true);
});
await check('Not answered removes professional from persisted engine state',async()=>{
 c=reducer(c,{type:'answerScope',field:'role',answer:'clear'});
 assert.equal(professionalConfirmed(c.facts),false);
 assert.equal(await sync.pushFacts(cid,c.facts),null);
 const got=await plain.getCase(cid);
 const role=got.facts.filter(x=>x.field==='professional.role');
 console.log('withdrawal persisted role',JSON.stringify(role));
 assert.equal(professionalConfirmed(got.facts),false,'engine still treats the withdrawn role as confirmed');
});
await check('Not sure removes the prior confirmed Part 4 decision on engine',async()=>{
 c=reducer(c,{type:'answerScope',field:'part4_design',answer:'not-sure'});
 assert.equal(await sync.pushFacts(cid,c.facts),null);
 const got=await plain.getCase(cid);
 const latest=[...got.facts].reverse().find(x=>x.field==='professional.part4_design');
 console.log('Not sure persisted decision',JSON.stringify(latest));
 assert.ok(!latest||latest.status!=='confirmed','engine retained the prior confirmed yes after Not sure');
});
await check('clearing a process answer removes it from engine completeness',async()=>{
 c=reducer(c,{type:'setProcess',field:'risk',value:'SYNTHETIC risk passage intentionally withdrawn'});
 assert.equal(await sync.pushFacts(cid,c.facts),null);
 c=reducer(c,{type:'setProcess',field:'risk',value:''});
 assert.equal(await sync.pushFacts(cid,c.facts),null);
 const got=await plain.getCase(cid);
 const risk=[...got.facts].reverse().find(x=>x.field==='process.risk_assessment');
 const gaps=await plain.gaps(cid);
 console.log('cleared risk persisted',JSON.stringify(risk),'reported missing=',gaps.some(x=>x.field==='risk_assessment'));
 assert.ok(!risk||risk.status!=='confirmed','the deleted risk answer remains confirmed on the engine');
 assert.ok(gaps.some(x=>x.field==='risk_assessment'));
 assert.equal((await plain.processFields(cid)).find(x=>x.id==='risk_assessment').answer,null);
});
await check('evidence second item survives removing first, and typed evidence never becomes a file',async()=>{
 const created=await plain.createCase({title:'SYNTHETIC multiple evidence listings'});
 sync.adoptEngineCase(created);
 const plan=await plain.sectionD(created.id,{provisions:['9.25.2.2.(1)'],expected_version:created.version});
 sync.acknowledgeWrite(created.id,plan.case_version);
 const task=plan.items[0]; assert.ok(task);
 let e=emptyCase('contractor');
 for (const document of ['SYNTHETIC First report','SYNTHETIC Second report']) e=reducer(e,{type:'saveEvidence',itemId:task.id,document,responsible:'SYNTHETIC Author',date:'2026-10-20',evidenceType:'evaluation',provisionId:task.provision_id});
 assert.equal(await sync.pushFacts(created.id,e.facts),null);
 const listed=await sync.pushListedEvidence(created.id,e.listedEvidence);
 assert.equal(listed.error,null); assert.deepEqual(listed.rejected,[]); assert.equal(listed.acked.length,2);
 e=reducer(e,{type:'removeEvidence',id:task.id});
 const deleted=await sync.pushDeletedEvidence(created.id,e.deletedEvidence); assert.equal(deleted.error,null);
 const got=await plain.getCase(created.id);
 assert.ok(!got.facts.some(x=>x.field.startsWith(`evidence.${task.id}.`)));
 assert.ok(got.facts.some(x=>x.field===`evidence.${task.id}~2.title`&&x.value==='SYNTHETIC Second report'));
 assert.ok(!got.facts.some(x=>x.field.startsWith(`evidence.${task.id}`)&&(x.field.endsWith('.file_ref')||x.source.type==='file')));
});
await check('removing then replacing an evidence item before sync preserves the replacement',async()=>{
 const created=await plain.createCase({title:'SYNTHETIC replacement evidence listing'});
 sync.adoptEngineCase(created);
 const plan=await plain.sectionD(created.id,{provisions:['9.25.2.2.(1)'],expected_version:created.version});
 sync.acknowledgeWrite(created.id,plan.case_version);
 const task=plan.items[0]; assert.ok(task);
 let e=emptyCase('contractor');
 const add=document=>({type:'saveEvidence',itemId:task.id,document,responsible:'SYNTHETIC Author',date:'2026-10-20',evidenceType:'evaluation',provisionId:task.provision_id});
 e=reducer(e,add('SYNTHETIC Removed report')); await sync.pushFacts(created.id,e.facts);
 e=reducer(e,{type:'removeEvidence',id:task.id});
 e=reducer(e,add('SYNTHETIC Replacement report'));
 await sync.pushFacts(created.id,e.facts);
 const listed=await sync.pushListedEvidence(created.id,e.listedEvidence); assert.equal(listed.error,null); assert.deepEqual(listed.rejected,[]);
 const deleted=await sync.pushDeletedEvidence(created.id,e.deletedEvidence); assert.equal(deleted.error,null);
 const got=await plain.getCase(created.id);
 console.log('replacement evidence local=',JSON.stringify(e.listedEvidence),'persisted=',JSON.stringify(got.facts.filter(x=>x.field.startsWith(`evidence.${task.id}`))));
 assert.ok(got.facts.some(x=>x.field===`evidence.${e.listedEvidence[0].id}.title`&&x.value==='SYNTHETIC Replacement report'),'queued deletion erased the newly added replacement');
});
await check('an old in-flight create cannot restore a prior role engine case after reset',async()=>{
 sync.clearEngineSession(); let release; let created; const ready=new Promise(resolve=>created=resolve); const held=new Promise(resolve=>release=resolve); let first=true;
 globalThis.fetch=async(input,init)=>{const target=typeof input==='string'&&input.startsWith('/api')?raw+input.slice(4):input;const response=await originalFetch(target,init); if(first&&init?.method==='POST'&&String(input).endsWith('/cases')){first=false;created();await held;}return response;};
 const old=sync.ensureEngineCase('SYNTHETIC old role','calgary'); await ready;
 sync.clearEngineSession(); const next=await sync.ensureEngineCase('SYNTHETIC new role','edmonton');
 release(); const previous=await old.catch(e=>e.name);
 console.log('role-reset engine ids',JSON.stringify({previous,next,active:sync.engineCaseId()}));
 assert.equal(sync.engineCaseId(),next,'old role create overwrote the new role engine case id');
});
await check('c996677 delta: GC paste requires an explicit proposed alternative in engine completeness',async()=>{
 const description=['Owner: SYNTHETIC Example Owner','Representative: SYNTHETIC Example Rep','Municipal address: 000 Example Way NW, Edmonton','Legal description: Lot 0, Block 0, Plan EXAMPLE','We are replacing a firestop at a corridor wall.'].join('\n');
 let gc=reducer(emptyCase('contractor'),{type:'setDescription',text:description});
 assert.equal(gc.facts.find(x=>x.field==='project.description')?.value,description);
 assert.equal(gc.facts.some(x=>x.field==='alternative'),false);
 const created=await plain.createCase({title:'SYNTHETIC c996677 GC delta',jurisdiction:{id:'edmonton',name:'Edmonton',authority:null}});
 assert.equal(await sync.pushFacts(created.id,gc.facts),null);
 assert.ok((await plain.gaps(created.id)).some(x=>x.field==='alternative_description'));
 gc=reducer(gc,{type:'setDetail',field:'alternative',value:'SYNTHETIC explicit applicant proposal',section:'B'});
 assert.equal(await sync.pushFacts(created.id,gc.facts),null);
 assert.ok(!(await plain.gaps(created.id)).some(x=>x.field==='alternative_description'));
 assert.equal((await plain.getCase(created.id)).facts.find(x=>x.field==='permit'||x.field==='permit_number')?.value,undefined,'an application without a supplied permit never receives an invented one');
});
await check('c996677 delta: professional next step preserves an official-PDF hold',async()=>{
 const note=professionalRouteNote([{id:'professional:professional_requirement',field:'professional_requirement'}]);
 assert.match(note,/routed to the officer/);assert.match(note,/does not open the official PDF/);assert.match(note,/draft PDF/);assert.match(note,/Do not invent a number/);
});

globalThis.fetch=(input,init)=>originalFetch(typeof input==='string'&&input.startsWith('/api')?raw+input.slice(4):input,init);
for (const [field, engineField] of [['mitigation','mitigating_measures'], ['assumptions','assumptions_and_limits']]) {
 await check(`blank ${field} persists and reopens the actual API gap`,async()=>{
  const id=(await plain.createCase({title:'SYNTHETIC process withdrawal'})).id;
  let c=reducer(emptyCase('homebuilder'),{type:'setProcess',field,value:'SYNTHETIC passage'});
  assert.equal(await sync.pushFacts(id,c.facts),null);
  c=reducer(c,{type:'setProcess',field,value:'  '});
  assert.equal(await sync.pushFacts(id,c.facts),null);
  assert.equal((await plain.processFields(id)).find(x=>x.id===engineField).answer,null);
  assert.ok((await plain.gaps(id)).some(x=>x.field===engineField));
 });
}
await check('a failed withdrawal retries, then the original same-id answer can be restored',async()=>{
 const id=(await plain.createCase({title:'SYNTHETIC retry'})).id;
 const c=reducer(emptyCase('homebuilder'),{type:'setDetail',field:'owner',value:'SYNTHETIC owner',section:'A'});
 await sync.pushFacts(id,c.facts);
 const mapped=globalThis.fetch;
 globalThis.fetch=async(input,init)=>String(input).endsWith('/facts')?new Response(JSON.stringify({detail:'synthetic failure'}),{status:503}):mapped(input,init);
 assert.ok(await sync.pushFacts(id,[]));
 globalThis.fetch=mapped;
 assert.equal(await sync.pushFacts(id,[]),null);
 assert.ok((await plain.gaps(id)).some(x=>x.field==='owner_name'));
 await sync.pushFacts(id,c.facts);
 assert.ok(!(await plain.gaps(id)).some(x=>x.field==='owner_name'));
});
await check('overlapping fact saves persist the newest revision after an older delayed POST',async()=>{
 const id=(await plain.createCase({title:'SYNTHETIC overlapping facts'})).id;
 const first=reducer(emptyCase('homebuilder'),{type:'setProcess',field:'risk',value:'SYNTHETIC old risk'});
 const second=reducer(first,{type:'setProcess',field:'risk',value:'SYNTHETIC new risk'});
 const mapped=globalThis.fetch; let release, ready;
 const entered=new Promise(resolve=>ready=resolve); const wait=new Promise(resolve=>release=resolve); let held=false;
 globalThis.fetch=async(input,init)=>{if(!held&&String(input).endsWith('/facts')){held=true;ready();await wait;}return mapped(input,init);};
 const old=sync.pushFacts(id,first.facts); await entered;
 const next=sync.pushFacts(id,second.facts); release(); await Promise.all([old,next]);
 globalThis.fetch=mapped;
 assert.equal((await plain.processFields(id)).find(x=>x.id==='risk_assessment').answer.value,'SYNTHETIC new risk');
});
await check('reset invalidates unsupported jurisdiction acknowledgement and preserves new case',async()=>{
 sync.clearEngineSession(); const before=await sync.ensureEngineCase('SYNTHETIC unknown jurisdiction','');
 const mapped=globalThis.fetch; let release, ready;
 const entered=new Promise(resolve=>ready=resolve); const wait=new Promise(resolve=>release=resolve); let held=false;
 globalThis.fetch=async(input,init)=>{const response=await mapped(input,init);if(!held&&String(input).endsWith('/jurisdiction')&&init?.method==='PUT'){held=true;ready();await wait;}return response;};
 const old=sync.syncJurisdiction(before,'calgary','SYNTHETIC old jurisdiction'); await entered;
 sync.clearEngineSession(); const next=await sync.ensureEngineCase('SYNTHETIC new role','edmonton');
 const rejected=assert.rejects(old,{name:'StaleEngineSession'}); release(); await rejected;
 globalThis.fetch=mapped;
 assert.equal(sync.engineCaseId(),next);
 assert.equal((await plain.getCase(next)).jurisdiction.id,'edmonton');
});
await check('old create cleanup cannot clear a newer in-flight create',async()=>{
 sync.clearEngineSession();
 const mapped=globalThis.fetch; const releases=[], ready=[];
 const entered=[0,1].map(i=>new Promise(resolve=>ready[i]=resolve));
 let count=0;
 globalThis.fetch=async(input,init)=>{
  const response=await mapped(input,init);
  if(String(input).endsWith('/cases')&&init?.method==='POST'){
   const i=count++; if(i<2){const held=new Promise(resolve=>releases[i]=resolve);ready[i]();await held;}
  }
  return response;
 };
 const old=sync.ensureEngineCase('SYNTHETIC old create',''); await entered[0];
 sync.clearEngineSession();
 const next=sync.ensureEngineCase('SYNTHETIC next create',''); await entered[1];
 const rejected=assert.rejects(old,{name:'StaleEngineSession'});releases[0]();await rejected;
 assert.equal(sync.ensureEngineCase('SYNTHETIC same next create',''),next);
 releases[1]();const id=await next;assert.equal(sync.engineCaseId(),id);assert.equal(count,2);
 globalThis.fetch=mapped;
});
await checkSavedAliases(check, plain);
await checkPreparation(check, plain);
console.log(JSON.stringify({results},null,2));
process.exitCode=results.some(x=>x.status==='FAIL')?1:0;
