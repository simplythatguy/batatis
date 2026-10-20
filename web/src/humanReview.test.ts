import assert from "node:assert/strict";
import test from "node:test";
import { officerRequest, practicePrompt, SCO_JUDGEMENT } from "./humanReview.ts";
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
});

test("a yes asks for the professional and an unknown shows its question", () => {
  const yes = practicePrompt(true, "Is the span over 12.20 m?");
  assert.match(yes.lead, /Name the registered professional/);
  assert.match(yes.lead, /does not state their engineering judgment/);
  assert.equal(yes.question, null);
  const unknown = practicePrompt("unknown", "What is the confirmed occupancy?");
  assert.equal(unknown.question, "What is the confirmed occupancy?");
  assert.match(unknown.lead, /not a yes or a no/);
  assert.doesNotMatch(`${unknown.lead} ${unknown.question}`, /judgment/);
});
