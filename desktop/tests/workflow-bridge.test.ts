import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { join } from "node:path";
import test from "node:test";
import { startEngine } from "../src/main/engine.ts";
import { ProviderDispatch } from "../src/main/provider-dispatch.ts";
import { ProviderRpc } from "../src/main/provider-rpc.ts";
import { KeyVault } from "../src/main/credentials.ts";
import { KeyProviders } from "../src/main/provider-http.ts";
import { unavailableProvider, type CompleteJsonRequest, type HostProvider } from "../src/main/providers.ts";
import { both, pythonCommand, REPO, scratch, text } from "./helpers.ts";

const program = String.raw`
import asyncio, hashlib, json, os
from engine.desktop import bridge, composition
from engine.intake import model, review
from engine.identify.providers import transports
from engine.identify.llm import OpenAIVerifier, prompt, _PICK_SCHEMA
from engine.identify.verify import SYSTEM as VERIFY_SYSTEM
from engine.routes_assist import call_model, AssistRequest, SYSTEM as ASSIST_SYSTEM
from engine.identify.jevkit import keystore
os.environ['BATATIS_PROVIDER'] = 'fake'
def forbidden(*a, **kw):
    raise AssertionError('ambient credential/provider access forbidden')
keystore.resolve = forbidden
from engine import llm_gate
llm_gate.provider_enabled = forbidden
llm_gate.fake_providers = forbidden

def run():
    transport, status = model.default_transport()
    intake = model.run('We propose an alternative wall.', 'We propose an alternative wall.', transport, skip=set(), status=status)
    rt, rs = review.default_transport()
    reviewed = review.run('SYNTHETIC large document ' + 'éç' * 40000, [], outbound=lambda s, own:s, transport=rt, status=rs)
    tp = transports(scoring={'jev'})
    assert tp.jev is not None
    judged = tp.jev({'proposal':'Synthetic wall'}, {'wall':{'type':'noul','instructions':'The proposal describes a wall.'}}, 5)
    arts = {'9.1.1.1.': {'part':9, 'section':'Fixture', 'subsection':'Synthetic', 'title':'Test article', 'text':'Synthetic article text.'}}
    checked = OpenAIVerifier(tp.openai, arts, model=composition.MODEL, effort=composition.EFFORT).verify('Synthetic wall', list(arts))
    body = AssistRequest(screen='describe', question='Explain this field.', history=[{'role':'assistant','text':'Untrusted history'}])
    answer = call_model(provider='desktop', model=composition.MODEL, context='{"screen":"describe","source":"synthetic"}', body=body, desktop_profile=composition.profile())
    return {'intake': intake.input_tokens, 'review':reviewed.input_tokens, 'answer':answer.text, 'picked':len(checked.picks), 'dropped':len(checked.dropped),
      'jev':judged['answers']['wall']['noul'], 'usd':tp.log.usd(), 'spend':tp.log.by_provider(),
      'systems':{k:hashlib.sha256(v.encode()).hexdigest() for k,v in [('intake', model.SYSTEM), ('document-review',review.SYSTEM), ('identify-picks',VERIFY_SYSTEM), ('assistant',ASSIST_SYSTEM)]},
      'schemas': {'intake': model.schema(), 'document-review':review.schema(), 'identify-picks':_PICK_SCHEMA},
      'verify_user': prompt('Synthetic wall',arts,list(arts),None)}

async def app(scope, receive, send):
    if scope['type'] == 'lifespan':
        while True:
            event = await receive()
            await send({'type':event['type']+'.complete'})
            if event['type'] == 'lifespan.shutdown':return
    await receive()
    result = await asyncio.to_thread(run)
    await send({'type':'http.response.start','status':200,'headers':[[b'content-type',b'application/json']]})
    await send({'type':'http.response.body','body':json.dumps(result).encode()})
bridge.run(app, hello={'workspace':{'kind':'local','id':'offline'},'codedb':{'available':False,'build':None,'expectedBuild':'synthetic'}}, control=None,body_limit=5000000)
`;

test("real Python choosers cross the private pipe with exact context, chunked documents and existing Jev validators", async (t) => {
  const userData = scratch(t); const calls: CompleteJsonRequest[] = [];
  const vault = new KeyVault(join(userData, "providers"), { available: async () => true, encrypt: async (s) => Buffer.from(s), decrypt: async (s) => s.toString() });
  await vault.save("jev", "offline-screen-synthetic");
  const provider: HostProvider = { ...unavailableProvider(), workflowReadiness: async () => ({ ready: true }), completeJson: async (r) => {
    calls.push(r);
    const payloads: Record<string, Record<string, unknown>> = {
      intake: { facts: [] },
      "document-review": { documents: [{ file: "absent", kind: "synthetic", title: "x".repeat(60_000), author: null, date: null, status: null }], flags: [], facts: [], conflicts: [], provisions: [], missing: [], questions: [] },
      "identify-picks": { picks: [{ article: "9.1.1.1.", quote: "Invented quotation must be dropped.", reason: "Synthetic", confidence: 0.9 }] },
      assistant: { answer: "Synthetic answer." },
    };
    return { ok: true, json: payloads[r.task], model: r.model, effort: r.effort, usage: null };
  } };
  const keys = new KeyProviders(vault, async (id, key, raw) => {
    assert.equal(id, "jev"); assert.equal(key, "offline-screen-synthetic");
    const body = JSON.parse(raw); assert.equal(body.model, "jev-1.13.0"); assert.deepEqual(Object.keys(body).sort(), ["model", "questions", "state"]);
    return { status: 200, body: JSON.stringify({ model: body.model, answers: { wall: { type: "noul", noul: 0.7 } }, usage: { input_tokens: 7, output_tokens: 3 } }) };
  });
  const dispatch = new ProviderDispatch({ account: () => provider, vault, keys, accepting: () => true });
  dispatch.select(both("chatgpt", true));
  const rpc = new ProviderRpc(dispatch.call, (lease) => dispatch.valid(lease));
  const command = pythonCommand(userData, "local");
  const started = await startEngine({ ...command, args: ["-c", program], cwd: REPO }, { onCall: rpc.call, log: () => {} });
  assert.equal(started.kind, "ready"); if (started.kind !== "ready") return;
  t.after(async () => { dispatch.invalidate(); await started.engine.stop(); });
  const reply = await started.engine.request({ method: "POST", path: "/api/test", query: "", headers: [], body: new Uint8Array() });
  assert.equal(reply.status, 200); const result = JSON.parse(await text(reply.body));
  assert.equal(result.intake, null); assert.equal(result.review, null); assert.equal(result.answer, "Synthetic answer.");
  assert.equal(result.picked, 0); assert.equal(result.dropped, 1); assert.equal(result.jev, 0.7); assert.equal(result.usd, null);
  assert.equal(result.spend.openai.billing, "subscription"); assert.equal(result.spend.openai.input_tokens, null); assert.equal(result.spend.openai.usd, null);
  assert.deepEqual(calls.map((r) => r.task), ["intake", "document-review", "identify-picks", "assistant"]);
  for (const request of calls) {
    assert.equal(createHash("sha256").update(request.system).digest("hex"), result.systems[request.task]);
    assert.equal(request.model, "gpt-6-luna"); assert.equal(request.effort, "medium");
    if (request.task !== "assistant") assert.deepEqual(request.schema, result.schemas[request.task]);
  }
  assert.equal(JSON.parse(calls[0].user).text, "We propose an alternative wall.");
  assert.equal(JSON.parse(calls[1].user).request, "SYNTHETIC large document " + "éç".repeat(40_000));
  assert.equal(calls[2].user, result.verify_user);
  assert.deepEqual(JSON.parse(calls[3].user), { context: { screen: "describe", source: "synthetic" }, history: [{ role: "assistant", text: "Untrusted history" }], question: "Explain this field." });
  assert.deepEqual(calls[3].schema, { type: "object", additionalProperties: false, required: ["answer"], properties: { answer: { type: "string", maxLength: 12000 } } });
});
