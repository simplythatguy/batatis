/** P13: real offline intake/identify/lookup and saved-fact callers, on disposable SQLite only. */
import assert from "node:assert/strict";
import type { Engine } from "../src/api/client.ts";
import { canonicalRows } from "../src/api/sectionC.ts";
import * as sync from "../src/api/sync.ts";
import { caseFromEngine } from "../src/calm/openCase.ts";
import { buildDeck, choicesFor, deckCompletion } from "../src/calm/deck.ts";
import { preparationGaps } from "../src/calm/preparation.ts";
import { emptyCase } from "../src/intake.ts";
import { asLocal } from "../src/intakeFields.ts";
import { DETAIL_FIELDS, PROCESS_FIELDS, getGaps, reducer } from "../src/model.ts";
import { confirmedProvisions, keywordGroups } from "../src/provisions.ts";

type Check = (name: string, run: () => Promise<void>) => Promise<void>;
const description = "SYNTHETIC one-storey single-family test house, alternate penetration assembly through a fire-separation. Test data only.";

export async function checkPreparation(check: Check, api: Engine) {
  await check("P13: confirmed storeys satisfy legacy code questions after real sync and reload", async () => {
    let saved = await api.createCase({ title: "SYNTHETIC P13 storeys" });
    let c = reducer(emptyCase("homebuilder"), { type: "setDescription", text: description });
    sync.adoptEngineCase(saved);
    assert.equal(await sync.pushFacts(saved.id, c.facts), null);
    const intake = await api.intake(saved.id, { text: description });
    sync.acknowledgeWrite(saved.id, intake.case_version);
    c = reducer(c, { type: "noteIntake", text: description, result: intake });
    sync.notePosted(saved.id, intake.facts.map(asLocal));
    const storeys = c.facts.find((f) => f.field === "storeys")!;
    assert.ok(storeys, "intake reads the one-storey words as an unconfirmed proposal");
    assert.equal(storeys.status, "unconfirmed");
    c = reducer(c, { type: "confirmFacts", ids: [storeys.id] });
    assert.equal(await sync.pushFacts(saved.id, c.facts), null);
    saved = await api.getCase(saved.id);
    c = caseFromEngine(saved, "homebuilder");
    c = reducer(c, { type: "restoreIntake", text: description, result: await api.storedIntake(saved.id) });
    c = reducer(c, { type: "noteIdentifyQuestions", questions: [{ field: "building.storeys", text: "How many storeys?" }] });
    assert.equal(buildDeck(c, getGaps(c)).some((i) => i.title === "How many storeys?"), false, "the same confirmed fact answers a question under its legacy alias");
    assert.equal(await sync.pushFacts(saved.id, c.facts), null);
    assert.deepEqual((await api.getCase(saved.id)).facts, saved.facts, "reopening and resolving a question must not synthesize another confirmation");
    for (const replacement of [
      { value: 3, status: "unconfirmed", kind: "pointed" },
      { value: 3, status: "confirmed", kind: "proposed" },
      { value: 3, status: "confirmed", kind: "computed" },
      { value: "Not sure", status: "confirmed", kind: "pointed" },
      { value: "", status: "unconfirmed", kind: "pointed" },
    ] as const) {
      const uncertain = { ...c, facts: [...c.facts, { ...storeys, ...replacement, id: "SYNTHETIC newer answer", field: "building.storeys" }] };
      assert.ok(buildDeck(uncertain, getGaps(uncertain)).some((i) => i.title === "How many storeys?"), JSON.stringify(replacement));
    }
    const legacy = reducer(c, { type: "addCandidate", candidate: { id: "desc-storeys", topic: "Storey count", provision: "", part: 0, benchmark: false, identified: false, quote: { text: "", citation: "" }, departure: "", clarifyingQuestion: "How many storeys?", answer: null } });
    assert.ok(!buildDeck(legacy, getGaps(legacy)).some((i) => i.kind === "storeys"), "confirmed intake also satisfies the legacy count card without choosing a technical No");
    assert.equal(legacy.candidates.find((a) => a.id === "desc-storeys")!.answer, null);
    // The engine planner also recognizes the older persisted alias after a decision re-plans intake.
    saved = await api.addFact(saved.id, { field: "building.storeys", value: 2, kind: "pointed", status: "confirmed", source: { type: "user_text", ref: "SYNTHETIC explicit correction" } });
    assert.ok(!(await api.intakePlan(saved.id, saved.version)).record.plan!.questions.some((q) => q.field === "storeys"));
  });
  await check("P13: real no-provider fire-separation fallback becomes grouped optional triage", async () => {
    const saved = await api.createCase({ title: "SYNTHETIC P13 fallback" });
    const result = await api.identify(saved.id, description);
    assert.equal(result.mode, "bm25_fallback");
    assert.ok(result.articles.length > 0);
    let c = reducer(emptyCase("homebuilder"), { type: "setDescription", text: description });
    c = reducer(c, { type: "noteIdentify", result });
    const wanted = c.candidates.map((a) => ({ candidateId: a.id, provision: a.provision }));
    const rows = await api.sectionC(wanted.map((a) => a.provision));
    c = reducer(c, { type: "reconcileSectionC", rows: canonicalRows(rows, wanted) });
    const deck = buildDeck(c, getGaps(c));
    console.log("P13 fallback receipt", JSON.stringify({ articles: result.articles.length, choices: result.choices.length, candidates: c.candidates.length, codeQuestions: deck.filter((i) => i.kind === "candidate").length }));
    assert.equal(deck.filter((i) => i.kind === "candidate" && !i.optional).length, 0, "keyword-only matches must not force technical Yes/No on every sentence");
    assert.equal(deck.filter((i) => i.kind === "code-triage").length, 1);
    const groups = keywordGroups(c);
    assert.equal(groups.length, result.articles.length, "the complete returned ranking is reachable");
    assert.equal(groups.flatMap((g) => g.candidates).length, c.candidates.length);
    for (const candidate of c.candidates) {
      const card = buildDeck(c, getGaps(c), { focusedCandidate: `cand-${candidate.id}` }).find((i) => i.ref === candidate.id)!;
      assert.ok(card, "each candidate can still be opened directly");
      assert.deepEqual(choicesFor(card).map((o) => o.value), ["yes", "no", "not-sure"], "selection, dismissal and abstention remain explicit");
      assert.ok(card.provision, "every card retains its code detail link");
      assert.match(card.context, /keyword match only/i);
    }
    assert.ok(c.candidates.every((a) => a.answer === null), "grouping never decides on behalf of the applicant");
    const promoted = reducer(c, { type: "addCandidate", candidate: { ...c.candidates[0], id: `search-${c.candidates[0].provision}`, suggestion: "search" } });
    assert.equal(promoted.candidates.length, c.candidates.length);
    const optedIn = buildDeck(promoted, getGaps(promoted)).find((i) => i.ref === c.candidates[0].id)!;
    assert.ok(optedIn && !optedIn.optional && !optedIn.done, "manually choosing an existing keyword lead opens an ordinary decision card");
    assert.equal(reducer(promoted, { type: "noteIdentify", result }).candidates.length, c.candidates.length, "a later result does not duplicate the manually selected candidate");
    assert.deepEqual((await api.getCase(saved.id)).provisions, [], "keyword retrieval never creates Section C confirmations");

    // Exercise the older article caller too: deterministic lookup really expands this returned
    // shortlist into many sentences. The grouped deck still asks one triage, not each sentence.
    let expanded = reducer({ ...emptyCase("homebuilder"), identify: result }, { type: "addIdentified", articles: result.articles.map((a) => ({ provision: a.provision, title: a.title, part: a.part, quote: a.quote, reason: a.reason })) });
    const articleWanted = expanded.candidates.map((a) => ({ candidateId: a.id, provision: a.provision }));
    expanded = reducer(expanded, { type: "reconcileSectionC", rows: canonicalRows(await api.sectionC(articleWanted.map((a) => a.provision)), articleWanted) });
    assert.ok(expanded.candidates.length > result.articles.length, "the real article-to-sentence path is exercised");
    assert.equal(buildDeck(expanded, getGaps(expanded)).filter((i) => i.kind === "candidate").length, 0);
    assert.equal(keywordGroups(expanded).flatMap((g) => g.candidates).length, expanded.candidates.length, "grouping loses no expanded sentence");
    assert.ok(expanded.candidates.every((a) => a.answer === null));

    for (const article of result.articles.slice(0, 3)) {
      const decided = await api.decide(saved.id, article.provision, "not_sure");
      c = reducer(c, { type: "noteIdentify", result: decided });
      const candidate = c.candidates.find((a) => a.provision === article.provision_id)!;
      c = reducer(c, { type: "answerCandidate", id: candidate.id, answer: "not-sure" });
    }
    const questions = getGaps(c).filter((g) => g.id.startsWith("question-"));
    assert.equal(questions.length, 3);
    assert.equal(new Set(questions.map((g) => g.label)).size, 3, "officer questions name the topic and provision, not three identical prompts");
    assert.equal(preparationGaps(c, questions).applicant.length, 0, "applicants are not told to answer their own saved abstentions");
    assert.equal(confirmedProvisions(c).length, 0, "looked-up Not sure sentences are never counted as confirmed rules");
    const stored = await api.getCase(saved.id);
    const reopened = reducer(caseFromEngine(stored, "homebuilder"), { type: "noteIdentify", result: await api.storedIdentify(saved.id) });
    assert.equal(reopened.candidates.filter((a) => a.answer === "not-sure").length, 3);
    assert.equal(buildDeck(reopened, getGaps(reopened)).some((i) => i.kind === "candidate"), false);

    // A manually chosen sentence keeps deterministic lookup and explicit Yes, independently of leads.
    const provision = "9.10.9.2.(2)";
    let manual = reducer(c, { type: "addCandidate", candidate: { id: `search-${provision}`, topic: "SYNTHETIC manually selected rule", provision, part: 9, benchmark: false, identified: true, suggestion: "search", quote: { text: "", citation: "", source: "code" }, departure: "depart", clarifyingQuestion: "Which part?", answer: null } });
    const manualWanted = manual.candidates.map((a) => ({ candidateId: a.id, provision: a.provision }));
    manual = reducer(manual, { type: "reconcileSectionC", rows: canonicalRows(await api.sectionC(manualWanted.map((a) => a.provision)), manualWanted) });
    assert.ok(buildDeck(manual, getGaps(manual)).some((i) => i.ref === `search-${provision}` && !i.done && !i.optional));
    manual = reducer(manual, { type: "answerCandidate", id: `search-${provision}`, answer: "yes" });
    assert.deepEqual(confirmedProvisions(manual), [provision]);
    assert.equal(manual.sectionC.length > confirmedProvisions(manual).length, true, "candidate lookups and confirmed references differ");

    // The Review/finish callers should offer a check/preview for officer-pending Section D,
    // while preserving source and known professional duties as applicant blockers.
    for (const d of DETAIL_FIELDS.filter((d) => d.required)) manual = reducer(manual, { type: "setDetail", field: d.id, value: d.id === "scope" ? "site" : "SYNTHETIC applicant answer", section: d.section });
    for (const p of PROCESS_FIELDS) manual = reducer(manual, { type: "setProcess", field: p.id, value: "SYNTHETIC applicant passage" });
    manual = reducer(manual, { type: "setAuthority", authority: "edmonton" });
    const pending = { id: "professional:professional_requirement", field: "professional_requirement", label: "Officer determination pending", severity: "blocking" as const, submissionBlocking: false, href: "#/application?tab=D" };
    const officerDeck = buildDeck(manual, [pending], { includeDone: true });
    assert.equal(officerDeck.filter((i) => !i.done && !i.optional).length, 0);
    assert.equal(deckCompletion(officerDeck, []).skipped, 0);
    assert.match(deckCompletion(officerDeck, []).message, /officer.*pending/i);
    const stale = { ...manual, practiceOfEngineering: "unknown" as const };
    const localPending = getGaps(stale).filter((g) => g.id === "practice-unknown");
    assert.equal(preparationGaps(stale, localPending).checkNeeded.length, 1);
    assert.equal(preparationGaps(stale, localPending).applicant.length, 0);
    const mandatory = [{ ...pending, id: "professional:professional_source", field: "professional_source", submissionBlocking: true }, { ...pending, id: "needs-professional", field: "professional.role", submissionBlocking: true }];
    assert.equal(preparationGaps(stale, mandatory).applicant.length, 2, "mandatory source and required-professional gates stay intact");
    const missingSource = buildDeck(manual, [mandatory[0]], { includeDone: true });
    assert.equal(missingSource.find((i) => i.kind === "section-d")!.done, false);
    assert.equal(deckCompletion(missingSource, []).skipped, 0, "an unanswered requirement is not a Skip click");
    assert.equal(deckCompletion(missingSource, ["section-d"]).skipped, 1, "an actual Skip click remains explicit");
    console.log("P13 expanded triage receipt", JSON.stringify({ sentenceCandidates: expanded.candidates.length, groups: keywordGroups(expanded).length, confirmed: confirmedProvisions(manual).length, officerPendingSkipped: deckCompletion(officerDeck, []).skipped }));
  });
}
