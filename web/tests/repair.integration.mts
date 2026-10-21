import assert from 'node:assert/strict';
import { createEngine } from '../src/api/client.ts';
import { canonicalRows } from '../src/api/sectionC.ts';
import { readSectionD } from '../src/api/sectionD.ts';
import { reconcileSectionC, confirmedProvisions } from '../src/provisions.ts';
import { reducer, getGaps, displayValue } from '../src/model.ts';
import { emptyCase } from '../src/intake.ts';
const base = process.env.SYNC_TEST_BASE;
assert.match(base ?? '', /^http:\/\/(127\.0\.0\.1|localhost):\d+/);
const realFetch = globalThis.fetch;
const requests = [];
globalThis.fetch = async (input, init) => {
  const url = String(input).replace(/^\/api/, base);
  assert.equal(new URL(url).origin, base);
  const entry = { url, method: init?.method, body: init?.body, ack: false };
  requests.push(entry);
  const response = await realFetch(url, init);
  entry.ack = response.ok;
  return response;
};
const api = createEngine(base);
const candidate = (provision, answer = null) => ({ id: `test-${provision}`, provision, answer, identified: true, suggestion: 'search', part: 3, benchmark: answer === 'yes', topic: 'Firestops', quote: {text:'',citation:'CodeDB'}, departure:'depart from this sentence', clarifyingQuestion:'Which part changes?' });
let count = 0;
async function test(name, fn) { await fn(); console.log('PASS', name); count++; }
const raw = await api.sectionC(['3.1.9.1.', '3.1.9.1.(5)']);
let c = emptyCase('contractor');
await test('real CodeDB article plus child maps once per canonical sentence without cross product', () => {
  c = reducer(c, {type:'addCandidate',candidate:candidate('3.1.9.1.', 'yes')});
  c = reducer(c, {type:'addCandidate',candidate:candidate('3.1.9.1.(5)', 'not-sure')});
  const rows = canonicalRows(raw, c.candidates.map(a => ({candidateId:a.id,provision:a.provision})));
  assert.equal(rows.length, 7); assert.equal(rows.filter(r=>r.provision==='3.1.9.1.(5)').length,1);
  c = reconcileSectionC(c, rows);
  assert.equal(c.candidates.length,7); assert.equal(c.candidates.filter(a=>a.answer==='yes').length,0);
  assert.equal(c.candidates.find(a=>a.provision==='3.1.9.1.(5)').answer,'not-sure');
  assert.equal(c.candidates.filter(a=>a.answer===null).length,6);
  assert.ok(getGaps(c).some(g=>g.severity==='blocking'));
  assert.deepEqual(confirmedProvisions(c),[]);
});
await test('sentence answer survives parent re-add and overlapping reference removal', async () => {
  const first = c.candidates.find(a=>a.provision==='3.1.9.1.(1)');
  c = reducer(c,{type:'answerCandidate',id:first.id,answer:'yes'});
  c = reducer(c,{type:'addCandidate',candidate:candidate('3.1.9.1.')});
  c = reconcileSectionC(c,canonicalRows(raw,c.candidates.map(a=>({candidateId:a.id,provision:a.provision}))));
  assert.equal(c.candidates.length,7); assert.deepEqual(confirmedProvisions(c),['3.1.9.1.(1)']);
  const child = c.candidates.find(a=>a.provision==='3.1.9.1.(5)');
  c = reducer(c,{type:'removeCandidate',id:child.id});
  assert.equal(c.sectionC.length,6); assert.deepEqual(confirmedProvisions(c),['3.1.9.1.(1)']);
  c = reducer(c,{type:'addCandidate',candidate:candidate('3.1.9.1.(5)')});
  const lookup=await api.sectionC(c.candidates.map(a=>a.provision));
  c = reconcileSectionC(c,canonicalRows(lookup,c.candidates.map(a=>({candidateId:a.id,provision:a.provision}))));
  assert.equal(c.candidates.length,7); assert.equal(c.candidates.find(a=>a.provision==='3.1.9.1.(5)').answer,null);
});
const id = (await api.createCase({title:'Synthetic R4 regression'})).id;
await test('real engine persists only selected sentence then reads issues from its acknowledged plan', async () => {
  requests.length=0;
  const result=await readSectionD(id,c,()=>true);
  assert.ok(result.plan.items.length>0);
  assert.ok(result.issues.every(i=>i.provision?.provision_id==='3.1.9.1.(1)'));
  assert.ok(requests[0].url.endsWith('/section-d') && requests[0].method==='POST' && requests[0].ack);
  assert.ok(requests[1].url.endsWith('/section-d/issues'));
  const stored=await api.getCase(id);
  assert.deepEqual(stored.provisions,['3.1.9.1.(1)']);
  assert.equal(new Set(stored.section_c.map(r=>r.provision_id)).size,stored.section_c.length);
});
await test('late Section D write cannot publish or fetch mixed-revision issues', async () => {
  let current=true;
  globalThis.fetch=async (input,init)=>{ const response=await realFetch(String(input).replace(/^\/api/,base),init); if(String(input).endsWith('/section-d')) current=false; return response; };
  assert.equal(await readSectionD(id,c,()=>current),null);
  globalThis.fetch=(input,init)=>realFetch(String(input).replace(/^\/api/,base),init);
});
await test('last-reference withdrawal reports missing backend clear support, never serves stale plan', async () => {
  const cleared={...c,candidates:c.candidates.map(a=>({...a,answer:'no'}))};
  await assert.rejects(readSectionD(id,cleared,()=>true),/could not clear/);
});
await test('unlabelled address fact posts unconfirmed and preserves full original description', async () => {
  const text='The site is 0000 Example Way NW, Calgary. The firestop at the level 2 riser was installed by the plumbing sub.';
  const draft=reducer(emptyCase('contractor'),{type:'setDescription',text});
  for(const f of draft.facts) await api.addFact(id,f);
  const stored=await api.getCase(id);
  const address=stored.facts.find(f=>f.field==='municipalAddress');
  assert.equal(address.value,'0000 Example Way NW, Calgary'); assert.equal(address.status,'unconfirmed');
  assert.equal(stored.facts.find(f=>f.field==='project.description').value,text);
});
await test('unfinished evidence is not a confirmed fact, survives edits, and clears on explicit save/reset', () => {
  let draft=reducer(c,{type:'editEvidenceDraft',itemId:'task',patch:{document:'unfinished',responsible:'author'}});
  assert.deepEqual(draft.facts,c.facts);
  draft=reducer(draft,{type:'setProcess',field:'risk',value:'Synthetic risk text'});
  assert.equal(draft.evidenceDrafts.task.document,'unfinished');
  draft=reducer(draft,{type:'saveEvidence',itemId:'task',document:'unfinished',responsible:'author',date:'',evidenceType:'' ,provisionId:''});
  assert.equal(draft.evidenceDrafts.task.document,'unfinished');
  draft=reducer(draft,{type:'saveEvidence',itemId:'task',document:'unfinished',responsible:'author',date:'',evidenceType:'evaluation',provisionId:'3.1.9.1.(1)'});
  assert.equal(draft.evidenceDrafts.task,undefined);
  draft=reducer(draft,{type:'reset',to:emptyCase('homebuilder')}); assert.equal(draft.evidenceDrafts,undefined);
});
await test('professional unknown labels in text record are human readable', () => {
  assert.equal(displayValue({field:'professional.role',value:'not_sure'}),'Not sure');
  assert.equal(displayValue({field:'professional.role',value:'not_engaged_yet'}),'Not engaged yet');
});
await test('storey count is an explicit count and Not sure withdraws it', () => {
  let draft=reducer(emptyCase('contractor'),{type:'setDescription',text:'Synthetic firestop review'});
  draft=reducer(draft,{type:'setStoreyCount',value:'2'});
  assert.equal(draft.facts.find(f=>f.field==='building.storeys').value,2);
  draft=reducer(draft,{type:'setStoreyCount',value:''});
  assert.equal(draft.facts.some(f=>f.field==='building.storeys'),false);
  assert.equal(draft.candidates.find(a=>a.id==='desc-storeys').answer,'not-sure');
});
console.log(`R4 real API/reducer: ${count} passed`);
