import assert from "node:assert/strict";
import test from "node:test";
import { notSureQuestions, officerProfessionalLines, officerRequest, officerRoutedLabel, pdfOutcomeLine, practiceFlagLine, practicePrompt, professionalRouteNote, SCO_JUDGEMENT, textRecord } from "./humanReview.ts";
import { emptyCase } from "./intake.ts";
import { getGaps, reducer, unresolvedCandidates } from "./model.ts";

const article = {
  provision: "9.10.15.5",
  title: "Spatial separation",
  part: 9,
  quote: "The exposing building face shall comply.",
  reason: null,
};

test("article ranking does not accept an article", () => {
  let c = reducer(emptyCase("homebuilder"), {
    type: "addCandidate",
    candidate: {
      id: "desc-wall",
      topic: "Wall",
      provision: "wall",
      part: 9,
      benchmark: false,
      quote: { text: "hempcrete", citation: "From what you wrote" },
      departure: "use hempcrete",
      clarifyingQuestion: "Which sentence?",
      answer: null,
    },
  });
  c = reducer(c, { type: "addIdentified", articles: [article] });
  const card = c.candidates.find((item) => item.provision === article.provision);
  assert.equal(card?.answer, null);
  assert.equal(card?.benchmark, false);
  assert.ok(unresolvedCandidates(c).some((item) => item.provision === article.provision));
});

test("an explicit Yes is what accepts the article", () => {
  let c = reducer(emptyCase("contractor"), { type: "addIdentified", articles: [article] });
  const id = c.candidates.find((item) => item.provision === article.provision)?.id;
  assert.ok(id);
  c = reducer(c, { type: "answerCandidate", id, answer: "yes" });
  const card = c.candidates.find((item) => item.id === id);
  assert.equal(card?.answer, "yes");
  assert.equal(card?.benchmark, true);
  c = reducer(c, { type: "addIdentified", articles: [article] });
  const again = c.candidates.find((item) => item.provision === article.provision);
  assert.equal(again?.answer, "yes");
  assert.equal(again?.benchmark, true);
});

test("Not sure is an open question and does not block Continue", () => {
  let c = reducer(emptyCase("homebuilder"), { type: "addIdentified", articles: [article] });
  const id = c.candidates.find((item) => item.provision === article.provision)?.id ?? "";
  c = reducer(c, { type: "answerCandidate", id, answer: "not-sure" });
  assert.equal(unresolvedCandidates(c).some((item) => item.id === id), false);
  const question = c.questions.find((item) => item.id === `q-from-${id}`);
  assert.match(question?.why ?? "", /officer/);
  const gap = getGaps(c).find((item) => item.id === `question-q-from-${id}`);
  assert.equal(gap?.severity, "warning");
  assert.match(gap?.label ?? "", /Open question/);
  const letter = officerRequest({
    title: c.title,
    files: [],
    gaps: getGaps(c),
    notSure: c.questions.filter((item) => item.id.startsWith("q-from-")),
    ranking: [],
    professional: ["Practice of engineering is unknown."],
    record: { label: "Export blocked", reasons: ["Section B, alternative description is empty."], note: "Export blocked." },
    role: { engineer: "Name an engineer when the design needs one.", officer: "The officer decides contradictions." },
    reportNote: "The grouped completeness report isn't available on this engine yet.",
  });
  assert.match(letter, /Which part of this sentence/);
  assert.match(letter, /Export blocked/);
  assert.match(letter, /Section B, alternative description is empty/);
  assert.match(letter, /SCO judgement/);
  for (const item of SCO_JUDGEMENT) assert.match(letter, new RegExp(item.label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  assert.match(letter, /Practice of engineering is unknown/);
  assert.match(letter, /No documents uploaded/);
  assert.doesNotMatch(letter, /complies or is safe\.\nAdministrative/);
  assert.match(letter, /does not decide whether the design complies or is safe/);
  assert.match(letter, /Questions the applicant marked Not sure/);
  const grouped = officerRequest({
    title: "Case",
    files: [],
    gaps: [{ id: "g-scope", severity: "blocking", label: "Jurisdiction-wide variance missing", href: "#/describe", field: "scope" }],
    notSure: [],
    ranking: [],
    professional: ["Not yet checked."],
    record: null,
    role: { engineer: "Name an engineer.", officer: "The officer decides." },
    reportNote: null,
    sectionById: new Map([["g-scope", "B"]]),
  });
  assert.match(grouped, /Section B/);
  assert.doesNotMatch(grouped, /Facts and questions\n- Jurisdiction-wide variance missing/);
});

test("the officer professional line waits for the professional route", () => {
  assert.deepEqual(officerProfessionalLines("pending", true, []), ["Not yet checked."]);
  assert.match(officerProfessionalLines("ready", "unknown", [])[0], /More facts are needed/);
});

test("a check that did not export does not say the PDF was blocked", () => {
  assert.deepEqual(pdfOutcomeLine({ example: true, downloaded: null }), ["Example: PDF not offered."]);
  const checked = pdfOutcomeLine({ example: false, downloaded: null });
  assert.match(checked[0], /not prepared in this session/);
  assert.doesNotMatch(checked.join("\n"), /blocked/);
  const record = textRecord({
    title: "House",
    description: "Hempcrete",
    factLines: ["Owner: Ada (from what you entered)"],
    blockingCount: 3,
    warningCount: 1,
    checkedAt: "2026-10-20",
    pdfLines: checked,
  });
  assert.match(record, /Completeness: 3 required items, 1 open question, checked at 2026-10-20/);
  assert.match(record, /does not decide whether the design complies or is safe/);
  assert.doesNotMatch(record, /\(pointed, confirmed\)/);
  const blocked = pdfOutcomeLine({
    example: false,
    downloaded: null,
    blocked: true,
    reasons: ["Owner name missing", "Authority missing"],
  });
  assert.deepEqual(blocked, ["Application PDF: blocked. Reasons:", "- Owner name missing", "- Authority missing"]);
  const failed = pdfOutcomeLine({
    example: false,
    downloaded: null,
    failed: true,
    reasons: ["The application PDF form is unavailable. Download a text record or try again later."],
  });
  assert.deepEqual(failed, [
    "Application PDF: could not be prepared.",
    "The application PDF form is unavailable. Download a text record or try again later.",
  ]);
  const downloaded = pdfOutcomeLine({
    example: false,
    downloaded: { name: "case-homebuilder-scc-variance-DRAFT.pdf", draft: true, at: "2026-10-20" },
    failed: true,
  });
  const afterPdf = textRecord({
    title: "House",
    description: "Hempcrete",
    factLines: [],
    blockingCount: 0,
    warningCount: 0,
    checkedAt: "2026-10-20",
    pdfLines: downloaded,
  });
  assert.match(afterPdf, /Application PDF: downloaded draft PDF case-homebuilder-scc-variance-DRAFT\.pdf/);
  assert.doesNotMatch(afterPdf, /did not return that PDF/);
  assert.doesNotMatch(afterPdf, /The engine did not return/);
  assert.doesNotMatch(afterPdf, /could not be prepared/);
});

test("the Section D practice line does not repeat depends", () => {
  const depends = practiceFlagLine("depends");
  const yes = practiceFlagLine("yes");
  const no = practiceFlagLine("no");
  assert.equal(depends, "More facts are needed before this screen can say whether practice of engineering applies. This is not a licence decision.");
  assert.doesNotMatch(depends, /depends/i);
  assert.doesNotMatch(`${depends} ${yes} ${no}`, /depends\.\s*depends|yes\.\s*yes|no\.\s*no/i);
  assert.doesNotMatch(yes, /Practice of engineering:\s*yes/i);
  assert.doesNotMatch(no, /Practice of engineering:\s*no/i);
});

test("a yes asks for the professional and an unknown shows its question", () => {
  let routed = reducer(emptyCase("contractor"), { type: "notePractice", value: true });
  routed = reducer(routed, {
    type: "answerScope",
    field: "fire_alarm",
    answer: "not-sure",
    text: "Is a fire alarm system being installed?",
  });
  assert.equal(routed.practiceOfEngineering, true);
  assert.ok(notSureQuestions(routed.questions).some((q) => q.text.includes("fire alarm")));
  assert.ok(getGaps(routed).some((gap) => gap.id === "needs-professional" && /officer/.test(gap.label)));
  routed = reducer(routed, { type: "answerScope", field: "fire_alarm", answer: "no", text: "Is a fire alarm system being installed?" });
  assert.equal(routed.questions.some((q) => q.id === "q-scope-fire_alarm"), false);
  assert.equal(routed.practiceOfEngineering, true);
  assert.ok(getGaps(routed).some((gap) => gap.id === "needs-professional"));
  routed = reducer(routed, { type: "answerScope", field: "fire_alarm", answer: "clear" });
  assert.equal(routed.facts.some((fact) => fact.field === "professional.fire_alarm"), false);
  const yes = practicePrompt(true, "Is the span over 12.20 m?");
  assert.match(yes.lead, /routed to the officer/);
  assert.match(yes.lead, /Name the registered professional/);
  assert.match(yes.lead, /seal or registration number/);
  assert.match(yes.lead, /does not state their engineering judgment/);
  assert.doesNotMatch(yes.lead, /needs_professional/);
  assert.equal(yes.question, null);
  const route = professionalRouteNote([{ id: "D12:responsible_professional", field: "responsible_professional" }]);
  assert.match(route ?? "", /routed to the officer/);
  assert.match(route ?? "", /draft PDF/);
  assert.match(route ?? "", /Do not invent a number/);
  assert.equal(professionalRouteNote([{ id: "detail-owner", field: "owner" }]), null);
  const labeled = officerRoutedLabel("a named registered professional required for this work");
  assert.match(labeled, /routed to the officer/);
  assert.match(labeled, /Not sure or Not engaged yet/);
  assert.equal(officerRoutedLabel(labeled), labeled);
  const unknown = practicePrompt("unknown", "What is the confirmed occupancy?");
  assert.equal(unknown.question, "What is the confirmed occupancy?");
  assert.match(unknown.lead, /not a yes or a no/);
  assert.doesNotMatch(`${unknown.lead} ${unknown.question}`, /judgment/);
});
