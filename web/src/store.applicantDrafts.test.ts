/** Real CaseProvider/reducer over a controlled versioned engine seam. No server, ports or provider. */
import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness } from "../scripts/component-harness.mjs";
import { drafting, pointed, savedDraftCase } from "../tests/applicant-drafts.fixture.ts";
import * as draftHelpers from "./applicantDrafts.ts";
import * as model from "./model.ts";
import * as open from "./calm/openCase.ts";
import * as rules from "./rules.ts";
import * as checkState from "./checkState.ts";
import * as visit from "./visit.ts";
import * as intake from "./intake.ts";
import { asLocal, latestLocalFacts } from "./intakeFields.ts";
import { readOnly } from "./calm/applications.ts";
import * as applicationEditing from "./calm/applicationEditing.ts";
import * as savedDraft from "./calm/applicantDraft.ts";
import * as questionDrafts from "./calm/questionDrafts.ts";
import * as reconcileDraft from "./calm/reconcileDraft.ts";
import * as jobs from "./api/jobs.ts";
import type { Fact } from "./types.ts";

class EngineError extends Error {
  readonly technical: string;
  readonly status: number;
  readonly detail: string;
  constructor(status: number, detail: string) { super(detail); this.status = status; this.detail = detail; this.technical = detail; }
}
function deferred() {
  let resolve: () => void = () => {};
  const promise = new Promise<void>(done => { resolve = done; });
  return { promise, resolve };
}

async function provider() {
  let remote = await savedDraftCase();
  let generation = 0, id: string | null = null, known: number | null = null, session = 1, conflicted = false;
  let generateFailure: EngineError | null = null;
  let draftReadFailure: EngineError | null = null;
  let gate: { entered: ReturnType<typeof deferred>; release: ReturnType<typeof deferred> } | null = null;
  let saveGate: typeof gate = null;
  const writes: { kind: string; expected: number | null; field?: string }[] = [];
  const posted = new Map<string, string>();
  const listeners = new Set<() => void>();
  const user = { id: "unit-owner", role: "applicant", name: "Unit owner" };
  const account = { phase: "signed-in", user, applications: [{ id: remote.id, status: remote.status, authority: "edmonton" }] };
  const acknowledgeWrite = (_id: string, next: number) => { if (known === null || next === known + 1) known = next; };
  const notePosted = (_id: string, facts: Fact[]) => { for (const fact of facts) posted.set(asLocal(fact).field, rules.factSignature(asLocal(fact))); };
  const checkVersion = (expected: number) => { if (expected !== remote.version) throw new EngineError(409, "updated concurrently"); };
  const wait = async () => { const pending = gate; gate = null; if (pending) { pending.entered.resolve(); await pending.release.promise; } };
  const engine = {
    getCase: async () => structuredClone(remote),
    jobs: async () => [], files: async () => [],
    applicantDrafts: async () => { if (draftReadFailure) throw draftReadFailure; return structuredClone(remote.drafting); },
    generateApplicantDrafts: async (_id: string, expected: number) => {
      writes.push({ kind: "generate", expected });
      if (generateFailure) throw generateFailure;
      checkVersion(expected);
      remote = { ...remote, version: remote.version + 1, drafting: structuredClone(drafting) };
      const response = structuredClone(remote);
      await wait();
      return response;
    },
    decideApplicantDraft: async (_id: string, draftId: string, expected: number, decision: "accept" | "reject") => {
      writes.push({ kind: decision, expected });
      checkVersion(expected);
      const draft = remote.drafting.drafts.find(d => d.id === draftId);
      if (!draft) throw new EngineError(404, "draft not found");
      draft.status = decision === "accept" ? "accepted" : "rejected";
      if (decision === "accept") remote.facts.push({ ...pointed(draft.field, draft.text, `accepted-${draft.id}`),
        source: { type: "user_click", ref: `applicant-draft:${draft.id}`, quote: draft.text } });
      remote.version++;
      const response = structuredClone(remote);
      await wait();
      return response;
    },
  };
  const sync = {
    engineGeneration: () => generation, isEngineGeneration: (token: number) => token === generation,
    engineCaseId: () => id, acknowledgedVersion: () => known, acknowledgeWrite, notePosted,
    clearEngineSession: () => { generation++; id = null; known = null; posted.clear(); conflicted = false; },
    adoptEngineCase: (saved: typeof remote) => { id = saved.id; known = saved.version; notePosted(id, latestLocalFacts(saved.facts)); },
    isReadOnlyCase: () => readOnly(remote.status), needsReconcile: () => conflicted,
    noteConflict: () => { conflicted = true; },
    // Stands in for the applicant finishing the save-conflict review.
    resolveConflict: () => { known = remote.version; conflicted = false; }, CONFLICT_TEXT: "The saved case changed somewhere else. Your answers are still here.",
    evidenceFacts: () => [], selectionKey: (values: unknown[]) => JSON.stringify(values),
    ensureEngineCase: async () => id, syncJurisdiction: async (selected: string) => selected,
    draftKey: (draft: unknown) => JSON.stringify(draft ?? null), acknowledgedDraftKey: () => "null", acknowledgedDraft: () => null,
    acknowledgedAuthority: () => "edmonton", acknowledgedSelectionKey: () => "[]", acknowledgedEvidenceFacts: () => [],
    pendingFactChanges: () => new Map(), acknowledgeJobCase: () => true, noteShownSelection() {},
    // One atomic acknowledgement of only the changed facts, like the real draft save.
    pushDraft: async (_id: string, snapshot: { facts: Fact[] }) => {
      const pending = saveGate; saveGate = null;
      if (pending) { pending.entered.resolve(); await pending.release.promise; }
      const changed = latestLocalFacts(snapshot.facts).filter(fact => posted.get(fact.field) !== rules.factSignature(fact));
      if (!changed.length) return null;
      checkVersion(known ?? -1);
      for (const fact of changed) {
        writes.push({ kind: "fact", expected: known, field: fact.field });
        remote.facts.push(structuredClone(fact));
      }
      remote.version++;
      acknowledgeWrite(remote.id, remote.version);
      notePosted(remote.id, changed);
      return structuredClone(remote);
    },
    pushSelectedArticles: async () => null, pushReconciledDraft: async () => null,
    pushListedEvidence: async () => ({ acked: [], deleted: [], rejected: [] }),
    pushDeletedEvidence: async () => ({ acked: [], deleted: [], rejected: [] }),
    refreshGaps: async () => ({ gaps: [], error: null }),
  };
  const h = await componentHarness(new URL("./store.tsx", import.meta.url), "CaseProvider", {
    "./api/client": { engine, EngineError, failureText: (error: unknown) => String(error instanceof EngineError ? error.detail : error),
      isCaseConflict: (error: unknown) => error instanceof EngineError && error.status === 409,
      isCaseGone: (error: unknown) => error instanceof EngineError && error.status === 404 && /case not found/.test(error.detail) },
    "./api/sync": sync, "./applicantDrafts": draftHelpers, "./rules": rules, "./model": model,
    "./checkState": checkState, "./intake": intake, "./intakeFields": { asLocal }, "./visit": visit,
    "./provisions": { sameCards: () => true },
    "./calm/openCase": open,
    "./calm/account": { useAccount: () => account, getAccountState: () => account, accountSession: () => session,
      subscribeAccount: (listener: () => void) => { listeners.add(listener); return () => listeners.delete(listener); },
      patchApplication: (_id: string, patch: object) => Object.assign(account.applications[0], patch), refreshApplications: async () => {} },
    "./calm/session": { getSession: () => ({ held: [], uploading: [] }), resetSavedSession() {}, updateSavedSession() {}, subscribeSession: () => () => {} },
    "./calm/applicationEditing": { ...applicationEditing, useApplicationEditsPaused: applicationEditing.applicationEditsPaused }, "./calm/applicantDraft": savedDraft, "./calm/questionDrafts": questionDrafts,
    "./calm/reconcileDraft": reconcileDraft, "./api/jobs": jobs,
    "./calm/auth/signOutGuard": { registerSignOutGuard: () => () => {}, resetSignOutStatus() {} },
    "./calm/caseExtras": { resetExtras() {} }, "./calm/applications": { readOnly },
    "./api/sectionC": { useSectionC: () => ({ source: "idle", rows: [] }) },
    "./api/accounts": { accounts: { submit: async (_id: string, expected: number) => {
      writes.push({ kind: "submit", expected }); checkVersion(expected); remote.version++; remote.status = "submitted"; return structuredClone(remote);
    } } },
  }, { sessionStorage: { removeItem() {} }, window: { setTimeout: () => 0, clearTimeout() {}, addEventListener() {}, removeEventListener() {} }, location: { hash: "#/review" } });
  const store = async () => (await h.render({ children: null })).props.value;
  await (await store()).openCase(remote.id, "homebuilder");
  await store();
  return {
    h, store, writes, get remote() { return remote; }, get known() { return known; },
    hold() { gate = { entered: deferred(), release: deferred() }; return gate; },
    holdSave() { saveGate = { entered: deferred(), release: deferred() }; return saveGate; },
    fail(error: EngineError | null) { generateFailure = error; },
    failRead(error: EngineError | null) { draftReadFailure = error; },
    changeAccount() { session++; for (const listener of listeners) listener(); },
    resolveConflict() { sync.resolveConflict(); },
  };
}

test("generation is queued after saving, metadata stays separate, and reopen restores sources without generating", async () => {
  const p = await provider();
  let s = await p.store();
  assert.equal(s.drafting.drafts[0].id, "draft-risk");
  assert.equal(p.writes.length, 0);
  await s.requestCheck();
  s = await p.store();
  const check = s.checkStatus;
  await s.generateApplicantDrafts();
  s = await p.store();
  assert.equal(p.writes.at(-1)?.expected, 1);
  assert.equal(p.known, 2);
  assert.equal(s.c.process.risk, "My manual risk answer.");
  assert.equal(s.saveStatus, "saved");
  assert.equal(s.checkStatus, check, "drafting-only writes do not invalidate the content check");
  s.dispatch({ type: "setDetail", field: "owner", value: "Edited owner", section: "A" });
  s = await p.store();
  await s.generateApplicantDrafts();
  assert.deepEqual(p.writes.slice(-2).map(w => [w.kind, w.expected]), [["fact", 2], ["generate", 3]]);
  p.h.unmount();
});

test("acceptance adopts process values without clearing unrelated local work or re-posting the accepted fact", async () => {
  const p = await provider();
  let s = await p.store();
  s.dispatch({ type: "editEvidenceDraft", itemId: "unfinished", patch: { document: "Unfinished document", step: 1 } });
  s = await p.store();  // An evidence draft edit is an unsaved edit: check from the current render.
  await s.requestCheck();
  s = await p.store();
  const files = s.c.files, cards = s.c.candidates;
  await s.decideApplicantDraft("draft-risk", "accept");
  s = await p.store();
  assert.equal(s.c.process.risk, drafting.drafts[0].text);
  assert.equal(s.c.evidenceDrafts.unfinished.document, "Unfinished document");
  assert.equal(s.c.files, files);
  assert.equal(s.c.candidates, cards);
  assert.equal(s.drafting.drafts[0].status, "accepted");
  assert.equal(s.checkStatus, "stale");
  assert.equal(s.gapsSource, "idle");
  assert.equal(s.saveStatus, "saved", "server acceptance is acknowledged content, not an unsaved local fact");
  await s.saveDraft();
  assert.equal(p.writes.filter(w => w.kind === "fact").length, 0);
  await (await p.store()).openCase(p.remote.id, "homebuilder");
  s = await p.store();
  assert.equal(s.c.process.risk, drafting.drafts[0].text);
  assert.equal(s.drafting.sources[0].text, drafting.sources[0].text);
  p.h.unmount();
});

test("a late generation advances the same-case version but preserves newer input and becomes stale", async () => {
  const p = await provider();
  const gate = p.hold();
  const running = (await p.store()).generateApplicantDrafts();
  await gate.entered.promise;
  let s = await p.store();
  s.dispatch({ type: "setProcess", field: "risk", value: "New answer while drafting" });
  gate.release.resolve(); await running;
  s = await p.store();
  assert.equal(p.known, 2, "acknowledgement cannot be dropped because the local revision changed");
  assert.equal(s.c.process.risk, "New answer while drafting");
  assert.equal(s.draftingStale, true);
  await s.saveDraft();
  assert.deepEqual(p.writes.at(-1), { kind: "fact", expected: 2, field: "process.risk_assessment" });
  assert.equal(p.remote.facts.at(-1)?.value, "New answer while drafting");
  p.h.unmount();
});

test("a late acceptance preserves a newer manual answer and the next save uses the acknowledged version", async () => {
  const p = await provider();
  const gate = p.hold();
  const running = (await p.store()).decideApplicantDraft("draft-risk", "accept");
  await gate.entered.promise;
  let s = await p.store();
  s.dispatch({ type: "setProcess", field: "risk", value: "Keep this newer manual answer" });
  gate.release.resolve(); await running;
  s = await p.store();
  assert.equal(p.known, 2);
  assert.equal(s.c.process.risk, "Keep this newer manual answer");
  assert.equal(s.draftingStale, true);
  await s.saveDraft();
  assert.deepEqual(p.writes.at(-1), { kind: "fact", expected: 2, field: "process.risk_assessment" });
  p.h.unmount();
});

test("acceptance preserves unrelated edits and invalidates queued snapshots that predate the accepted answer", async () => {
  const p = await provider();
  const gate = p.hold();
  const running = (await p.store()).decideApplicantDraft("draft-risk", "accept");
  await gate.entered.promise;
  let s = await p.store();
  s.dispatch({ type: "setDetail", field: "owner", value: "A newer owner name", section: "A" });
  const pendingSave = (await p.store()).saveDraft();
  gate.release.resolve(); await running; await pendingSave;
  s = await p.store();
  assert.equal(s.c.process.risk, drafting.drafts[0].text);
  assert.equal(s.c.facts.find(f => f.field === "owner")?.value, "A newer owner name");
  assert.equal(s.draftingStale, true);
  await s.saveDraft();
  assert.deepEqual(p.writes.filter(w => w.kind === "fact"), [{ kind: "fact", expected: 2, field: "owner" }]);
  p.h.unmount();
});

test("reopening verifies current staleness and read failures keep source history inspectable without enabling decisions", async () => {
  const p = await provider();
  p.remote.drafting.stale = true;
  await (await p.store()).openCase(p.remote.id, "homebuilder");
  assert.equal((await p.store()).draftingStale, true);
  p.remote.drafting.stale = false;
  p.failRead(new EngineError(503, "staleness unavailable"));
  await (await p.store()).openCase(p.remote.id, "homebuilder");
  const s = await p.store();
  assert.equal(s.draftingStale, true);
  assert.equal(s.drafting.sources[0].text, drafting.sources[0].text);
  assert.equal(p.writes.length, 0, "reading never generates writing");
  p.h.unmount();
});

test("case/account replacement drops late output and a changed revision during preparation never generates", async () => {
  for (const change of ["case", "account"]) {
    const p = await provider();
    const gate = p.hold();
    const running = (await p.store()).generateApplicantDrafts();
    await gate.entered.promise;
    if (change === "case") (await p.store()).resetToWho(); else p.changeAccount();
    gate.release.resolve(); await running;
    const s = await p.store();
    assert.equal(s.drafting, null);
    assert.equal(s.draftActivity.kind, "idle");
    if (change === "case") assert.equal(p.known, null);
    else assert.equal(p.known, 1);
    p.h.unmount();
  }
  const p = await provider();
  const gate = p.holdSave();
  const running = (await p.store()).generateApplicantDrafts();
  await gate.entered.promise;
  (await p.store()).dispatch({ type: "setProcess", field: "risk", value: "Changed while saving" });
  gate.release.resolve(); await running;
  assert.equal(p.writes.filter(w => w.kind === "generate").length, 0);
  assert.match((await p.store()).draftingError, /changed while saving/);
  p.h.unmount();
});

test("a failed generation reads in plain words and Try again sends the request again", async () => {
  const p = await provider();
  p.fail(new EngineError(503, "Drafting unavailable: generation or grounding validation failed; no writing was saved."));
  await (await p.store()).generateApplicantDrafts();
  assert.equal((await p.store()).draftingError, "We couldn't draft this part. Try again.");
  p.fail(null);
  const before = p.writes.filter(w => w.kind === "generate").length;
  await (await p.store()).retryApplicantDrafts();
  assert.equal(p.writes.filter(w => w.kind === "generate").length, before + 1);
  assert.equal((await p.store()).draftingError, "");
  p.h.unmount();
});

test("a conflict waits for the save-conflict review, gone cases stay gone, and submitted cases refuse generation", async () => {
  const p = await provider();
  p.fail(new EngineError(409, "updated concurrently"));
  await (await p.store()).generateApplicantDrafts();
  assert.match((await p.store()).draftingError, /Review the save conflict/);
  p.fail(null);
  const before = p.writes.length;
  await (await p.store()).retryApplicantDrafts();
  assert.equal(p.writes.length, before, "drafting never reconciles a conflict by itself");
  assert.match((await p.store()).draftingError, /Review the save conflict/);
  p.resolveConflict();
  await (await p.store()).retryApplicantDrafts();
  assert.equal((await p.store()).draftingError, "");
  p.fail(new EngineError(404, "case not found"));
  await (await p.store()).generateApplicantDrafts();
  const writes = p.writes.length;
  assert.equal((await p.store()).saveStatus, "gone");
  await (await p.store()).retryApplicantDrafts();
  assert.equal(p.writes.length, writes);
  p.h.unmount();
  const locked = await provider();
  locked.remote.status = "submitted";
  await (await locked.store()).generateApplicantDrafts();
  assert.equal(locked.writes.length, 0);
  assert.match((await locked.store()).draftingError, /editable application/);
  locked.h.unmount();
});

test("a submit queued during acceptance cannot submit an earlier displayed revision", async () => {
  const p = await provider();
  const gate = p.hold();
  const decision = (await p.store()).decideApplicantDraft("draft-risk", "accept");
  await gate.entered.promise;
  const submit = (await p.store()).submitDraft(p.remote.id);
  const refused = assert.rejects(submit, /changed while submitting/);
  gate.release.resolve(); await decision; await refused;
  assert.equal(p.writes.filter(w => w.kind === "submit").length, 0);
  p.h.unmount();
});

test("question-only drafts cannot be accepted but rejection writes no applicant answer", async () => {
  const p = await provider();
  p.remote.drafting.drafts[0].text = "";
  p.remote.drafting.drafts[0].claims = [];
  await (await p.store()).openCase(p.remote.id, "homebuilder");
  await (await p.store()).decideApplicantDraft("draft-risk", "accept");
  assert.equal(p.writes.length, 0);
  assert.match((await p.store()).draftingError, /No wording to accept/);
  await (await p.store()).decideApplicantDraft("draft-risk", "reject");
  const s = await p.store();
  assert.equal(s.drafting.drafts[0].status, "rejected");
  assert.equal(s.c.process.risk, "My manual risk answer.");
  assert.deepEqual(p.writes, [{ kind: "reject", expected: 1 }]);
  p.h.unmount();
});
