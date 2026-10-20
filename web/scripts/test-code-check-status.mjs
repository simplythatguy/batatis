import assert from "node:assert/strict";
import { codeCheckWaiting, getGaps } from "../src/model.ts";

const departure = "use a combustible drain where the sentence does not allow it";
const question = "Which exception is the drain relying on?";
const unanswered = {
  id: "c-7",
  topic: "Combustible drain",
  provision: "3.1.9.4.(7)",
  part: 3,
  benchmark: true,
  quote: { text: "synthetic", citation: "synthetic" },
  departure,
  clarifyingQuestion: question,
  answer: null,
};
const unsure = { ...unanswered, id: "c-4", provision: "3.1.9.4.(4)", answer: "not-sure" };

const waiting = codeCheckWaiting([unanswered, unsure]);
assert.equal(
  waiting,
  `3.1.9.4.(7): Does your design ${departure} instead?; 3.1.9.4.(4): ${question}`,
);
assert.equal(waiting.includes("wait for your answer"), false);
assert.equal(codeCheckWaiting([]), "");

const gaps = getGaps({
  id: "case",
  title: "synthetic",
  applicantType: "contractor",
  codeEdition: "NBC(AE) 2023",
  description: "",
  files: [],
  facts: [],
  questions: [],
  candidates: [unanswered, unsure],
  sectionC: [],
  process: { rationale: "x", risk: "x", mitigation: "x", assumptions: "x" },
}).filter((gap) => gap.id.startsWith("answer-"));

assert.deepEqual(
  gaps.map((gap) => gap.label),
  [`3.1.9.4.(7): Does your design ${departure} instead?`, `3.1.9.4.(4): ${question}`],
);
assert.equal(gaps.every((gap) => gap.severity === "blocking"), true);
