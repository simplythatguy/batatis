import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../scripts/component-harness.mjs";
import { emptyCase } from "./intake.ts";
import { reducer } from "./model.ts";
import * as professional from "./professional.ts";
import { spokenValue } from "./intakeView.ts";
import type { Action } from "./model.ts";
import type { Case, Fact } from "./types.ts";

const fact = (field: string, value: Fact["value"]): Fact => ({ id: field, field, value, kind: "pointed", status: "confirmed", source: { type: "user_text", ref: "intake answer", quote: String(value) } });

test("the professional screen skips known project questions and each choice moves to the next question", async () => {
  let c: Case = { ...emptyCase("owner"), description: "A house with a larger window.", practiceOfEngineering: true, facts: [fact("occupancy", "single_family"), fact("storeys", 2), fact("building_area_m2", 140), fact("part4_design", false)] };
  const dispatch = (action: Action) => { c = reducer(c, action); };
  let evidence = false;
  const h = await componentHarness(new URL("./screens/Recommendations.tsx", import.meta.url), "ProfessionalAnswers", {
    "../store": { useCase: () => ({ c, dispatch }) }, "../professional": professional, "../intakeView": { spokenValue },
  });
  const props = { onEvidence: () => { evidence = true; } };
  let tree = await h.render(props);
  const heading = () => text(nodes(tree, (node) => node.type === "h3")[0]);
  const button = (name: string) => nodes(tree, (node) => node.type === "button" && text(node) === name)[0];
  assert.match(heading(), /reserved professional judgement/);
  assert.match(text(tree), /Known from your project \(4\)/);
  button("Ask my designer").props.onClick();
  tree = await h.render(props);
  assert.match(heading(), /Who is the registered professional/);
  button("Engineer").props.onClick();
  tree = await h.render(props);
  assert.equal(heading(), "Professional registration number");
  nodes(tree, (node) => node.type === "input")[0].props.onChange({ target: { value: "SYNTHETIC-123" } });
  tree = await h.render(props);
  nodes(tree, (node) => node.type === "form")[0].props.onSubmit({ preventDefault() {} });
  tree = await h.render(props);
  assert.match(text(tree), /No more professional questions for you/);
  assert.equal(c.practiceOfEngineering, true);
  assert.equal(professional.professionalOpenCount(c), 0);
  assert.equal(professional.professionalQuestions(c).find((question) => question.field === "professional_judgement_required")?.deferred, true);
  nodes(tree, (node) => node.type === "button" && node.props?.["aria-label"] === "Change How many storeys is the building?")[0].props.onClick();
  tree = await h.render(props);
  assert.equal(heading(), "How many storeys is the building?");
  nodes(tree, (node) => node.type === "input")[0].props.onChange({ target: { value: "3" } });
  tree = await h.render(props);
  nodes(tree, (node) => node.type === "form")[0].props.onSubmit({ preventDefault() {} });
  tree = await h.render(props);
  assert.equal(professional.professionalValue(c, "storeys"), 3);
  button("Continue to evidence").props.onClick();
  assert.equal(evidence, true);
  h.unmount();
});
