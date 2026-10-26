/**
 * Push the browser case to the engine.
 * Changed facts, jurisdiction, selection and unfinished editors share one versioned draft PATCH.
 * Never recreate a case when a route is unavailable or the
 * case is gone; keep the draft and report the unacknowledged update.
 *
 * Versions: each content/workflow write increments the stored Case version by one. Messages
 * and read receipts use an atomic thread-only write and leave that version unchanged. `known`
 * is the last version reached through this visit's own consecutive content writes. A response that
 * skips a number means another writer changed the case, so `known` stays put and the next versioned
 * write (plan or jurisdiction) is rejected by the engine with 409. Only an explicit reconcile
 * adopts a version the visit did not write itself.
 */
import { engine, EngineError, isCaseConflict, isCaseGone, type DraftPatch, type SavedCase } from "./client";
import type { EngineGap, EvidenceWrite } from "./client";
import type { Case as EngineCase, SelectedArticleInput } from "./types.gen";
import { factSignature, jurisdictionBody, jurisdictionForCreate } from "../rules";
import type { AuthorityId, Fact, ListedEvidence } from "../types";
import { evidenceSlot } from "../model";
import { answerWithdrawn, latestLocalFacts } from "../intakeFields";
import { accountRequestSignal } from "./requestLifetime";
import type { ApplicantDraft } from "../calm/applicantDraft";

const ID_KEY = "batatis-engine-case-id";
const POSTED_KEY = "batatis-engine-posted";
/** Older builds recorded unacknowledged evidence POSTs here. Cleared, never read. */
const LEGACY_EVIDENCE_KEY = "batatis-engine-evidence";

let inflight: Promise<string> | null = null;
let generation = 0;
const factQueues = new Map<string, Promise<unknown>>();
const known = new Map<string, number>();
const conflicts = new Set<string>();
const jurisdictions = new Map<string, string | null>();
/** The code-check selection the engine acknowledged (or holds as of opening), as `selectionKey`. */
const selections = new Map<string, string>();
/** Opened cases their owner cannot edit (sent, in review or closed): their selection is never written. Cards
 * shown on them change only by derived display (a lookup expanding an article), recorded with noteShownSelection. */
const readOnly = new Set<string>();
/** Evidence slots the engine has shown for each case, from acknowledged writes and explicit reads. */
const ledgerSlots = new Map<string, Set<string>>();
/** Listing revisions the engine acknowledged, so a repeated push never writes them twice. */
const ackedRevs = new Map<string, Map<string, number>>();
/** Slots this visit tried to create; a removal of one never tried needs no request. */
const attempted = new Map<string, Set<string>>();
const latestLedger = new Map<string, Fact[]>();
const postedFacts = new Map<string, Record<string, PostedFact>>();
const drafts = new Map<string, ApplicantDraft | null>();
let currentCaseId: string | null = null;

export const draftKey = (value: ApplicantDraft | null | undefined) => JSON.stringify(value, (_key, item: unknown) =>
  item && typeof item === "object" && !Array.isArray(item) ? Object.fromEntries(Object.entries(item).sort(([a], [b]) => a.localeCompare(b))) : item) ?? "null";
export const acknowledgedDraft = (caseId: string) => drafts.get(caseId);
export const acknowledgedDraftKey = (caseId: string) => drafts.has(caseId) ? draftKey(drafts.get(caseId)) : undefined;
export const acknowledgedAuthority = (caseId: string) => jurisdictions.get(caseId);
export const acknowledgedSelectionKey = (caseId: string) => selections.get(caseId);
export const acknowledgedEvidenceFacts = (caseId: string) => latestLedger.get(caseId) ?? [];

/** The version to send as `expected_version`, or null before the case is acknowledged. */
export function acknowledgedVersion(caseId: string): number | null {
  return known.get(caseId) ?? null;
}

/** True after the engine rejected a versioned write; only an explicit reconcile clears it. */
export function needsReconcile(caseId: string): boolean {
  return conflicts.has(caseId);
}

/** Record the engine's answer to one of this visit's writes. */
export function acknowledgeWrite(caseId: string, version: unknown) {
  if (typeof version !== "number" || !Number.isInteger(version) || version < 1) return;
  const previous = known.get(caseId);
  if (previous === undefined || version === previous + 1) known.set(caseId, version);
}

export function noteConflict(caseId: string) {
  conflicts.add(caseId);
}

export const CONFLICT_TEXT = "The saved case changed somewhere else. Your answers are still here.";

/** Captured by callers before starting work; a reset invalidates every continuation. */
export const engineGeneration = () => generation;
export const isEngineGeneration = (value: number) => value === generation;

export class StaleEngineSession extends Error {
  constructor() {
    super("The application changed while saving.");
    this.name = "StaleEngineSession";
  }
}

function assertGeneration(value: number, signal?: AbortSignal) {
  if (!isEngineGeneration(value)) throw new StaleEngineSession();
  signal?.throwIfAborted();
}

export function engineCaseId(): string | null {
  return currentCaseId;
}

export function clearEngineSession() {
  generation += 1;
  factQueues.clear();
  known.clear();
  conflicts.clear();
  jurisdictions.clear();
  selections.clear();
  readOnly.clear();
  ledgerSlots.clear();
  ackedRevs.clear();
  attempted.clear();
  latestLedger.clear();
  postedFacts.clear();
  drafts.clear();
  currentCaseId = null;
  sessionStorage.removeItem(ID_KEY);
  sessionStorage.removeItem(POSTED_KEY);
  sessionStorage.removeItem(LEGACY_EVIDENCE_KEY);
  inflight = null;
}

type PostedFact = { id: string; signature: string };

function postedFor(caseId: string): Record<string, PostedFact> {
  return postedFacts.get(caseId) ?? {};
}

function remember(caseId: string, fields: Record<string, PostedFact>) {
  postedFacts.set(caseId, fields);
}

/**
 * One create at a time. A second caller waits on the same promise, so two
 * keystrokes cannot open two cases and strand facts on the first.
 */
export function ensureEngineCase(title: string | null, authority: AuthorityId, parent?: AbortSignal): Promise<string> {
  const signal = accountRequestSignal(parent);
  signal.throwIfAborted();
  const existing = engineCaseId();
  if (existing) return Promise.resolve(existing);
  if (inflight) return inflight;
  const token = generation;
  const request = engine
    .createCase({ ...(title ? { title } : {}), jurisdiction: jurisdictionForCreate(authority) }, signal)
    .then((created) => {
      assertGeneration(token, signal);
      sessionStorage.setItem(ID_KEY, created.id);
      currentCaseId = created.id;
      acknowledgeWrite(created.id, created.version);
      jurisdictions.set(created.id, created.jurisdiction?.id ?? null);
      return created.id;
    })
    .finally(() => {
      if (inflight === request) inflight = null;
    });
  inflight = request;
  return request;
}

/**
 * PUT `{ jurisdiction, expected_version }` only when the authority differs from the last
 * acknowledged value. An engine without the route (404/405) counts as saved only when its
 * stored value already matches. A missing case or a conflict is never retried here.
 */
export async function syncJurisdiction(caseId: string, authority: AuthorityId, _title: string, parent?: AbortSignal): Promise<string> {
  const token = generation;
  const signal = accountRequestSignal(parent);
  assertGeneration(token, signal);
  const wanted = authority || null;
  if (jurisdictions.has(caseId) && jurisdictions.get(caseId) === wanted) return caseId;
  const jurisdiction = authority ? jurisdictionBody(authority) : null;
  const unsaved = wanted
    ? "The reviewing authority could not be saved. Your draft is still open."
    : "The cleared reviewing authority could not be saved. Your draft is still open.";
  const expected = known.get(caseId);
  if (conflicts.has(caseId) || expected === undefined) throw new EngineError(409, CONFLICT_TEXT, "No acknowledged case version to send.");
  try {
    const saved = await engine.setJurisdiction(caseId, { jurisdiction, expected_version: expected }, signal);
    assertGeneration(token, signal);
    acknowledgeWrite(caseId, saved.version);
    jurisdictions.set(caseId, saved.jurisdiction?.id ?? null);
    return caseId;
  } catch (e) {
    assertGeneration(token, signal);
    if (isCaseConflict(e)) {
      noteConflict(caseId);
      throw new EngineError(409, CONFLICT_TEXT, (e as EngineError).technical);
    }
    if (isCaseGone(e) || !(e instanceof EngineError) || ![404, 405].includes(e.status)) throw e;
    const current = await engine.getCase(caseId, signal);
    assertGeneration(token, signal);
    const stored = current.jurisdiction?.id ?? null;
    if (stored === wanted) {
      jurisdictions.set(caseId, stored);
      return caseId;
    }
    throw new EngineError(e.status, unsaved, e.technical);
  }
}

/**
 * Explicit reconcile after a conflict: read the saved case, adopt its version, and re-base
 * this visit's posted-answer record on the saved values so the next save re-sends any local
 * answer that differs. Answers this visit never wrote are left alone. A missing case throws.
 */
export async function reconcileEngineCase(caseId: string): Promise<EngineCase> {
  const token = generation;
  const signal = accountRequestSignal();
  const saved = await engine.getCase(caseId, signal);
  assertGeneration(token, signal);
  known.set(caseId, saved.version);
  jurisdictions.set(caseId, saved.authority ?? saved.jurisdiction?.id ?? null);
  if (saved.selected_articles) selections.set(caseId, selectionKey(saved.selected_articles));
  noteEditable(saved);
  const latest = new Map(latestLocalFacts(saved.facts).map((fact) => [fact.field, fact]));
  const posted = postedFor(caseId);
  for (const field of Object.keys(posted)) {
    const stored = latest.get(field);
    if (stored && !answerWithdrawn(stored)) posted[field] = { id: stored.id, signature: factSignature(stored) };
    else delete posted[field];
  }
  remember(caseId, posted);
  conflicts.delete(caseId);
  noteLedger(caseId, saved);
  return saved;
}

/**
 * Open a saved case as this visit's engine case (multi-application list). Call right after
 * clearEngineSession(): adopts the saved version and jurisdiction, and records the saved latest
 * answer per field as already posted, so the next save sends only what the applicant changes.
 */
export function adoptEngineCase(saved: EngineCase, selection?: SelectedArticleInput[]) {
  sessionStorage.setItem(ID_KEY, saved.id);
  currentCaseId = saved.id;
  known.set(saved.id, saved.version);
  jurisdictions.set(saved.id, saved.authority ?? saved.jurisdiction?.id ?? null);
  // The cards the opened case shows count as saved: a legacy case (no saved selection) is not rewritten
  // until the applicant changes a card.
  const opened = selection ?? saved.selected_articles;
  if (opened) selections.set(saved.id, selectionKey(opened));
  noteEditable(saved);
  const posted: Record<string, PostedFact> = {};
  for (const fact of latestLocalFacts(saved.facts)) {
    if (fact.field.startsWith("evidence.") || answerWithdrawn(fact)) continue;
    posted[fact.field] = { id: fact.id, signature: factSignature(fact) };
  }
  remember(saved.id, posted);
  noteLedger(saved.id, saved);
  if ("applicant_draft" in saved) drafts.set(saved.id, saved.applicant_draft ?? null);
}

/** Local revisions relative to the last acknowledgement, including removals. Used to merge our job's output. */
export function pendingFactChanges(caseId: string, values: Fact[]): Map<string, Fact | null> {
  const posted = postedFor(caseId);
  const latest = new Map(latestLocalFacts(values).map(fact => [fact.field, fact]));
  const changes = new Map<string, Fact | null>();
  for (const fact of latest.values()) {
    if (!fact.field.startsWith("evidence.") && posted[fact.field]?.signature !== factSignature(fact)) changes.set(fact.field, fact);
  }
  for (const field of Object.keys(posted)) if (!field.startsWith("evidence.") && !latest.has(field)) changes.set(field, null);
  return changes;
}

/** Only our persisted job's exact output (or our already acknowledged newer version) may advance this baseline. */
export function acknowledgeJobCase(saved: EngineCase, outputVersion: number | null | undefined): boolean {
  const knownVersion = known.get(saved.id);
  if (knownVersion === undefined || saved.version < knownVersion || saved.version !== knownVersion && saved.version !== outputVersion) return false;
  const ownOutput = saved.version === outputVersion;
  if (needsReconcile(saved.id) && !ownOutput) return false;
  adoptEngineCase(saved);
  if (ownOutput) conflicts.delete(saved.id);
  return true;
}

/** One atomic acknowledgement for only the changed fields. CAS conflicts retain the local draft. */
export type DraftSnapshot = {
  facts: Fact[]; authority: AuthorityId; selected: SelectedArticleInput[]; draft: ApplicantDraft;
};

export function pushDraft(caseId: string, snapshot: DraftSnapshot, parent?: AbortSignal): Promise<SavedCase | null> {
  return writeDraft(caseId, snapshot, parent);
}

/** Explicitly reviewed merge only. Do not adopt the read version or discard local bytes before its CAS acknowledgement. */
export function pushReconciledDraft(against: EngineCase, snapshot: DraftSnapshot): Promise<SavedCase | null> {
  return writeDraft(against.id, snapshot, undefined, against);
}

async function writeDraft(caseId: string, snapshot: DraftSnapshot, parent?: AbortSignal, against?: EngineCase): Promise<SavedCase | null> {
  const token = generation, signal = accountRequestSignal(parent);
  assertGeneration(token, signal);
  const expected = against?.version ?? known.get(caseId);
  if ((!against && conflicts.has(caseId)) || expected === undefined) throw new EngineError(409, CONFLICT_TEXT);
  const posted: Record<string, PostedFact> = against ? Object.fromEntries(latestLocalFacts(against.facts)
    .filter(fact => !answerWithdrawn(fact) && !fact.field.startsWith("evidence."))
    .map(fact => [fact.field, { id: fact.id, signature: factSignature(fact) }])) : postedFor(caseId);
  const latest = new Map(latestLocalFacts(snapshot.facts).map(fact => [fact.field, fact]));
  const facts = [...latest.values()].filter(fact => !fact.field.startsWith("evidence.") && posted[fact.field]?.signature !== factSignature(fact));
  for (const [field, old] of Object.entries(posted)) {
    if (latest.has(field) || field.startsWith("evidence.")) continue;
    facts.push({ id: `${old.id}-withdrawn`, field, value: "", kind: "pointed", status: "unconfirmed",
      source: { type: "user_click", ref: "Answer withdrawn by applicant", quote: "" } });
  }
  const body: DraftPatch = { expected_version: expected };
  if (facts.length) body.facts = facts;
  const jurisdiction = snapshot.authority || null;
  const previousAuthority = against ? against.authority ?? against.jurisdiction?.id ?? null : jurisdictions.get(caseId);
  if (previousAuthority !== jurisdiction) body.jurisdiction = jurisdiction ? jurisdictionBody(jurisdiction) : null;
  const selected = selectionKey(snapshot.selected);
  const previousSelection = against ? selectionKey(against.selected_articles ?? []) : selections.get(caseId);
  if (previousSelection !== selected && !(previousSelection === undefined && !snapshot.selected.length)) body.selected_articles = snapshot.selected;
  const draft = draftKey(snapshot.draft);
  // A reviewed decision still needs CAS acknowledgement when the user chooses every saved value.
  if (against || acknowledgedDraftKey(caseId) !== draft) body.applicant_draft = snapshot.draft;
  if (Object.keys(body).length === 1) return null;
  try {
    const saved = await engine.patchDraft(caseId, body, signal);
    assertGeneration(token, signal);
    if (saved.id !== caseId || !Number.isInteger(saved.version) || saved.version < expected) throw new EngineError(0, "The save acknowledgement could not be verified. Your work is still here.");
    const returnedFacts = new Map(latestLocalFacts(saved.facts).map(fact => [fact.field, fact]));
    const returnedAuthority = saved.authority ?? saved.jurisdiction?.id ?? null;
    if (facts.some(fact => { const returned = returnedFacts.get(fact.field); return !returned || factSignature(returned) !== factSignature(fact); })
      || body.applicant_draft && draftKey(saved.applicant_draft) !== draft
      || body.selected_articles && selectionKey(saved.selected_articles ?? []) !== selected
      || "jurisdiction" in body && returnedAuthority !== jurisdiction) {
      throw new EngineError(0, "The server did not acknowledge all of your latest changes. Your work is still here.");
    }
    known.set(caseId, saved.version);
    const acknowledged: Record<string, PostedFact> = {};
    for (const fact of latestLocalFacts(saved.facts)) {
      if (fact.field.startsWith("evidence.") || answerWithdrawn(fact)) continue;
      acknowledged[fact.field] = { id: fact.id, signature: factSignature(fact) };
    }
    remember(caseId, acknowledged);
    jurisdictions.set(caseId, saved.authority ?? saved.jurisdiction?.id ?? null);
    if (body.selected_articles) selections.set(caseId, selected);
    if (body.applicant_draft) drafts.set(caseId, snapshot.draft);
    noteLedger(caseId, saved);
    if (against) { adoptEngineCase(saved); conflicts.delete(caseId); }
    return saved;
  } catch (error) {
    assertGeneration(token, signal);
    if (isCaseConflict(error)) noteConflict(caseId);
    throw error;
  }
}

/**
 * Facts an engine route wrote itself (intake, its answers, the scope click), adopted by the browser
 * under its own field names: recorded as already posted so a save never sends them back. `forget`
 * lists browser fields whose posted entry the engine removed (a re-run dropped its unconfirmed facts),
 * so no withdrawal is sent for them.
 */
export function notePosted(caseId: string, facts: Fact[], forget: string[] = []) {
  const done = postedFor(caseId);
  for (const field of forget) delete done[field];
  for (const fact of facts) done[fact.field] = { id: fact.id, signature: factSignature(fact) };
  remember(caseId, done);
}

/** The owner edits only a draft or a returned application (engine/access.py); a case without a status is a draft. */
function noteEditable(saved: EngineCase) {
  if (saved.status && saved.status !== "draft" && saved.status !== "returned") readOnly.add(saved.id);
  else readOnly.delete(saved.id);
}

/** True when the opened case is read-only for its owner: its code cards are not the applicant's to change. */
export const isReadOnlyCase = (caseId: string | null) => Boolean(caseId && readOnly.has(caseId));

/**
 * On a read-only case, cards a lookup derives from the shown (saved) cards are shown too: nothing to save.
 * Only a change on top of exactly the shown cards moves them; an unsaved change of the applicant's never does.
 */
export function noteShownSelection(caseId: string | null, before: SelectedArticleInput[], after: SelectedArticleInput[]) {
  if (caseId && readOnly.has(caseId) && selections.get(caseId) === selectionKey(before)) selections.set(caseId, selectionKey(after));
}

const READ_ONLY_SELECTION = "This application is read-only, so the code check change wasn’t saved.";

/** Equal selections, order included. */
export const selectionKey = (list: SelectedArticleInput[]) => JSON.stringify(list.map((s) => [s.id, s.provision, s.answer ?? null, Boolean(s.pending)]));

const SELECTION_REFUSED: Record<number, string> = {
  404: "A code reference wasn’t found, so your code check wasn’t saved. Your cards are still here.",
  422: "Your code check couldn’t be saved. Your cards are still here.",
};

/**
 * PUT the complete code-check selection with the acknowledged version, only when it differs from the
 * last one the engine acknowledged. Runs inside the save queue, so versions advance one at a time.
 * Resolves to an error text, or null when saved. A conflict (another write, or a read-only case)
 * throws and waits for an explicit reconcile; a deleted, expired or inaccessible case is reported as
 * "case not found" and never recreated. Nothing is retried here.
 */
export async function pushSelectedArticles(caseId: string, list: SelectedArticleInput[], parent?: AbortSignal): Promise<string | null> {
  const token = generation;
  // Like every other write here: a replaced sign-in cancels it rather than reporting a save problem.
  const signal = accountRequestSignal(parent);
  const key = selectionKey(list);
  const acked = selections.get(caseId);
  if (acked === key || (acked === undefined && !list.length)) return null;
  // Never written, and never reported as saved: the owner cannot change a read-only case's cards.
  if (readOnly.has(caseId)) return READ_ONLY_SELECTION;
  const expected = known.get(caseId);
  if (conflicts.has(caseId) || expected === undefined) throw new EngineError(409, CONFLICT_TEXT, "No acknowledged case version to send.");
  try {
    const saved = await engine.setSelectedArticles(caseId, { selected_articles: list, expected_version: expected }, signal);
    assertGeneration(token, signal);
    acknowledgeWrite(caseId, saved.version);
    // The engine canonicalizes provisions; what it acknowledged is this visit's list.
    selections.set(caseId, key);
    return null;
  } catch (e) {
    assertGeneration(token, signal);
    if (isCaseConflict(e)) {
      noteConflict(caseId);
      throw new EngineError(409, CONFLICT_TEXT, (e as EngineError).technical);
    }
    if (isCaseGone(e)) return (e as EngineError).detail;
    if (e instanceof EngineError) return SELECTION_REFUSED[e.status] ?? e.detail;
    return String(e);
  }
}

/** Reconcile a complete browser fact snapshot, including withdrawals. Serialize writes
 * so a slower older save cannot become the engine's latest revision. Keep the originating
 * account signal through the loop: cancellation must never continue under a replacement login. */
export function pushFacts(caseId: string, facts: Fact[], parent?: AbortSignal): Promise<string | null> {
  const token = generation;
  const signal = accountRequestSignal(parent);
  const previous = factQueues.get(caseId) ?? Promise.resolve();
  const request = previous.catch(() => {}).then(() => reconcileFacts(caseId, facts, token, signal));
  factQueues.set(caseId, request);
  return request;
}

async function reconcileFacts(caseId: string, facts: Fact[], token: number, signal: AbortSignal): Promise<string | null> {
  assertGeneration(token, signal);
  const done = postedFor(caseId);
  const latest = new Map(facts.map((fact) => [fact.field, fact]));
  const revisions = [...latest.values()];
  for (const [field, posted] of Object.entries(done)) {
    // Evidence is written only through its own atomic route; see pushListedEvidence.
    if (latest.has(field) || field.startsWith("evidence.")) continue;
    revisions.push({
      id: `${posted.id}-withdrawn`, field, value: "", kind: "pointed", status: "unconfirmed",
      source: { type: "user_click", ref: "Answer withdrawn by applicant", quote: "" },
    });
  }
  let error: string | null = null;
  for (const fact of revisions) {
    assertGeneration(token, signal);
    // Browser evidence facts mirror what the evidence route already saved. Never re-post them.
    if (fact.field.startsWith("evidence.")) continue;
    const signature = factSignature(fact);
    if (done[fact.field]?.signature === signature) continue;
    try {
      const saved = await engine.addFact(caseId, fact, signal);
      assertGeneration(token, signal);
      acknowledgeWrite(caseId, saved.version);
      if (latest.has(fact.field)) done[fact.field] = { id: fact.id, signature };
      else delete done[fact.field];
      remember(caseId, done);
    } catch (e) {
      assertGeneration(token, signal);
      error = e instanceof EngineError ? e.detail : String(e);
      // A deleted or expired case stays gone; do not keep posting into it.
      if (isCaseGone(e)) break;
    }
  }
  return error;
}

/** The engine's evidence ledger facts from a saved Case. The browser mirrors exactly these. */
export function evidenceFacts(saved: EngineCase): Fact[] {
  return saved.facts.filter((fact) => fact.field.startsWith("evidence.")) as Fact[];
}

function noteLedger(caseId: string, saved: EngineCase) {
  const facts = evidenceFacts(saved);
  latestLedger.set(caseId, facts);
  const slots = new Set(saved.evidence.map((item) => item.id));
  for (const fact of facts) {
    const slot = evidenceSlot(fact.field);
    if (slot) slots.add(slot);
  }
  ledgerSlots.set(caseId, slots);
}

const setFor = <T,>(map: Map<string, T>, caseId: string, make: () => T) => {
  if (!map.has(caseId)) map.set(caseId, make());
  return map.get(caseId)!;
};

export type EvidenceRejection = { id: string; rev?: number; reason: string };

/** What the engine acknowledged. `facts` is its evidence ledger after the latest acknowledged write. */
export interface EvidenceOutcome {
  acked: { id: string; rev: number }[];
  deleted: string[];
  rejected: EvidenceRejection[];
  facts: Fact[] | null;
  error: string | null;
}

const REJECTED: [RegExp, string][] = [
  [/scope must resolve/i, "This task changed, so the document could not be added to it. Your text is still here."],
  [/attachment workflow/i, "This slot holds an attached file. Your text is still here."],
  [/ambiguous/i, "Couldn’t remove this document. It shares its name with another saved entry."],
  [/evidence not found/i, "This document was removed somewhere else. Your text is still here."],
];

function rejection(e: unknown): string {
  const text = e instanceof EngineError ? `${e.detail} ${e.technical}` : String(e);
  return REJECTED.find(([pattern]) => pattern.test(text))?.[1] ?? "This document could not be saved. Your text is still here.";
}

function listingBody(item: ListedEvidence, expected: number): EvidenceWrite {
  const body: EvidenceWrite = {
    operation: item.operation,
    evidence_id: item.id,
    expected_version: expected,
    title: item.description,
    description: item.description,
    evidence_type: item.evidenceType,
  };
  // A string is saved; null withdraws a saved value (update only); undefined retains or omits.
  if (typeof item.responsible === "string" || (item.responsible === null && item.operation === "update")) body.responsible_party = item.responsible;
  if (typeof item.date === "string" || (item.date === null && item.operation === "update")) body.date = item.date;
  if (item.fileRef !== undefined) body.file_ref = item.fileRef;
  // Only a new listing names its task. An edit omits scope, so withdrawn links are never restored.
  if (item.operation === "create" && item.taskId) body.scope = { item_id: item.taskId };
  return body;
}

/**
 * Save each staged listing with POST /cases/{id}/evidence and the acknowledged version. A listing
 * counts as saved only for the exact revision the engine acknowledged. A conflict waits for an
 * explicit refresh, a deleted or expired case stops the queue, and a refused listing is returned
 * so its text can go back to the form. No automatic retry, upsert or replacement case.
 */
export async function pushListedEvidence(caseId: string, items: ListedEvidence[], parent?: AbortSignal): Promise<EvidenceOutcome> {
  const token = generation;
  const signal = accountRequestSignal(parent);
  const outcome: EvidenceOutcome = { acked: [], deleted: [], rejected: [], facts: latestLedger.get(caseId) ?? null, error: null };
  const revs = setFor(ackedRevs, caseId, () => new Map<string, number>());
  for (const item of items) {
    assertGeneration(token, signal);
    if (revs.get(item.id) === item.rev) {
      outcome.acked.push({ id: item.id, rev: item.rev });
      continue;
    }
    const expected = known.get(caseId);
    if (conflicts.has(caseId) || expected === undefined) {
      outcome.error = CONFLICT_TEXT;
      break;
    }
    if (item.operation === "create") setFor(attempted, caseId, () => new Set<string>()).add(item.id);
    try {
      const saved = await engine.saveEvidence(caseId, listingBody(item, expected), signal);
      assertGeneration(token, signal);
      acknowledgeWrite(caseId, saved.case_version);
      noteLedger(caseId, saved.case);
      revs.set(item.id, item.rev);
      outcome.acked.push({ id: item.id, rev: item.rev });
      outcome.facts = latestLedger.get(caseId) ?? null;
    } catch (e) {
      assertGeneration(token, signal);
      if (isCaseConflict(e)) {
        noteConflict(caseId);
        outcome.error = CONFLICT_TEXT;
        break;
      }
      if (e instanceof EngineError && (e.status === 422 || (e.status === 404 && !isCaseGone(e)))) {
        outcome.rejected.push({ id: item.id, rev: item.rev, reason: rejection(e) });
        continue;
      }
      // Gone, unreachable or an unanswered request: unknown or failed, never saved.
      outcome.error = e instanceof EngineError ? e.detail : String(e);
      break;
    }
  }
  return outcome;
}

/**
 * DELETE one evidence slot with `{ expected_version }`. Only the engine's answer acknowledges a
 * removal. A slot this visit never sent and the engine never showed needs no request. A 404 for
 * the slot is checked with a read, never taken as success. Ambiguous older slots are refused
 * once and not retried.
 */
export async function pushDeletedEvidence(caseId: string, ids: string[], parent?: AbortSignal): Promise<EvidenceOutcome> {
  const token = generation;
  const signal = accountRequestSignal(parent);
  const outcome: EvidenceOutcome = { acked: [], deleted: [], rejected: [], facts: latestLedger.get(caseId) ?? null, error: null };
  for (const id of ids) {
    assertGeneration(token, signal);
    if (!id.trim()) continue;
    if (!attempted.get(caseId)?.has(id) && !ledgerSlots.get(caseId)?.has(id)) {
      outcome.deleted.push(id);
      continue;
    }
    const expected = known.get(caseId);
    if (conflicts.has(caseId) || expected === undefined) {
      outcome.error = CONFLICT_TEXT;
      break;
    }
    try {
      const saved = await engine.deleteEvidence(caseId, id, expected, signal);
      assertGeneration(token, signal);
      acknowledgeWrite(caseId, saved.version);
      noteLedger(caseId, saved);
      outcome.deleted.push(id);
      outcome.facts = latestLedger.get(caseId) ?? null;
    } catch (e) {
      assertGeneration(token, signal);
      if (isCaseConflict(e)) {
        noteConflict(caseId);
        outcome.error = CONFLICT_TEXT;
        break;
      }
      if (e instanceof EngineError && e.status === 422) {
        outcome.rejected.push({ id, reason: rejection(e) });
        continue;
      }
      if (e instanceof EngineError && e.status === 404 && !isCaseGone(e)) {
        // Confirm absence with a read. The version is not adopted from it.
        try {
          const current = await engine.getCase(caseId, signal);
          assertGeneration(token, signal);
          const present = current.evidence.some((item) => item.id === id)
            || current.facts.some((fact) => evidenceSlot(fact.field) === id);
          if (!present) {
            ledgerSlots.get(caseId)?.delete(id);
            attempted.get(caseId)?.delete(id);
            outcome.deleted.push(id);
            continue;
          }
        } catch (read) {
          assertGeneration(token, signal);
          outcome.error = read instanceof EngineError ? read.detail : String(read);
          break;
        }
      }
      outcome.error = e instanceof EngineError ? e.detail : String(e);
      if (isCaseGone(e) || !(e instanceof EngineError) || e.status === 0) break;
    }
  }
  return outcome;
}

export async function refreshGaps(caseId: string): Promise<{ gaps: EngineGap[]; error: string | null }> {
  try {
    return { gaps: await engine.gaps(caseId), error: null };
  } catch (e) {
    return { gaps: [], error: e instanceof EngineError ? e.detail : String(e) };
  }
}
