import assert from "node:assert/strict";
import test from "node:test";
import type { SectionCRow } from "./api/types.gen.ts";
import { emptyCase } from "./intake.ts";
import { articleAnswer, isCachedDemo, planIdentify, readDecisionBody } from "./identify.ts";
import { officerRequest, unseenRequestItems } from "./humanReview.ts";
import { getGaps, reducer } from "./model.ts";

const article = {
  provision: "9.10.15.5.",
  title: "Spatial separation",
  part: 9,
  quote: "The exposing building face shall comply.",
  reason: null as string | null,
};

const row: SectionCRow = {
  provision_id: "9.10.15.5.",
  citation: "NBC(AE) 2023 Division B 9.10.15.5.",
  attribution_status: "direct",
  attributed_via: null,
  pairs: [],
  intents: [],
  intent_comparison: null,
  differs: false,
  only_in_intent: [],
  only_in_ae: [],
  related_root: null,
  related_root_method: null,
  explainer: { text: "This is an explanation of the quoted text.", quote: "The exposing building face", source: "deterministic" },
};

test("cached demo is only mode cached_demo with cached true", () => {
  assert.equal(isCachedDemo({ mode: "cached_demo", cached: true }), true);
  assert.equal(isCachedDemo({ mode: "cached_demo", cached: false }), false);
  assert.equal(isCachedDemo({ mode: "bm25_fallback", cached: false }), false);
  assert.equal(isCachedDemo({ mode: "live", cached: true }), false);
});

test("a suggested or committed flag does not count as Yes", () => {
  const plan = planIdentify({
    mode: "cached_demo",
    cached: true,
    articles: [{ ...article, status: "suggested", decision: null }],
  });
  assert.equal(plan.decisions.length, 0);
  assert.match(plan.note, /stored demo/);
  assert.match(plan.note, /Nothing is accepted until you choose Yes/);
  assert.equal(articleAnswer({ decision: null }), null);
  assert.equal(articleAnswer({ decision: "not_sure" }), "not-sure");
});

test("a decision body may be a Section C row or an identify envelope", () => {
  const bare = readDecisionBody(row, "9.10.15.5.");
  assert.equal(bare.row?.citation, row.citation);
  assert.equal(bare.row?.explainer?.source, "deterministic");
  assert.equal(bare.openQuestionId, null);
  const envelope = readDecisionBody(
    {
      mode: "live",
      cached: false,
      articles: [{ provision: "9.10.15.5.", decision: "not_sure", open_question_id: "oq_abc123" }],
      section_c: [row],
    },
    "9.10.15.5.",
  );
  assert.equal(envelope.openQuestionId, "oq_abc123");
  assert.equal(envelope.row?.provision_id, "9.10.15.5.");
  assert.equal(readDecisionBody({ provision_id: "9.10.15.5.", citation: "x" }, "9.10.15.5.").row, null);
});

test("Not sure keeps the engine question id", () => {
  let c = reducer(emptyCase("homebuilder"), { type: "addIdentified", articles: [article] });
  const id = c.candidates.find((item) => item.provision === article.provision)?.id ?? "";
  c = reducer(c, { type: "answerCandidate", id, answer: "not-sure" });
  c = reducer(c, { type: "bindOpenQuestion", candidateId: id, questionId: "oq_abc123" });
  assert.equal(c.questions.some((q) => q.id === `q-from-${id}`), false);
  assert.equal(c.questions.some((q) => q.id === "oq_abc123"), true);
  const gap = getGaps(c).find((item) => item.id === "question-oq_abc123");
  assert.equal(gap?.severity, "warning");
  assert.equal(gap?.href, `#/code-check?focus=cand-${id}`);
  c = reducer(c, { type: "answerCandidate", id, answer: "no" });
  assert.equal(c.questions.some((q) => q.id === "oq_abc123"), false);
});

test("intake questions stay on the field id unless the payload has an id", () => {
  let c = reducer(emptyCase("contractor"), {
    type: "noteIdentifyQuestions",
    questions: [{ field: "building.storeys", text: "How many storeys?" }],
  });
  assert.equal(c.questions.find((q) => q.field === "building.storeys")?.id, "q-identify-building.storeys");
  c = reducer(c, {
    type: "noteIdentifyQuestions",
    questions: [{ id: "oq_storeys", field: "building.storeys", text: "How many storeys?" }],
  });
  assert.equal(c.questions.filter((q) => q.field === "building.storeys").length, 1);
  assert.equal(c.questions.find((q) => q.field === "building.storeys")?.id, "oq_storeys");
});

test("officer request includes engine items once", () => {
  const notSure = [{ id: "oq_abc123", text: "Does this article apply?" }];
  const items = [
    { id: "oq_abc123", provision_id: "9.10.15.5.", text: "Does this article apply?" },
    { id: "oq_def456", provision_id: "9.10.14.5.", text: "Does the other article apply?" },
  ];
  assert.equal(unseenRequestItems(notSure, items).length, 1);
  const letter = officerRequest({
    title: "Wall",
    files: [],
    gaps: [],
    notSure,
    ranking: [],
    professional: [],
    record: null,
    role: { engineer: "Name an engineer when the design needs one.", officer: "The officer decides." },
    reportNote: null,
    engineItems: items,
  });
  assert.equal(letter.split("Does this article apply?").length - 1, 1);
  assert.match(letter, /9\.10\.14\.5\./);
});
