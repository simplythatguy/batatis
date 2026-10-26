import assert from "node:assert/strict";
import test from "node:test";
import { emptyCase } from "./intake.ts";
import { PICTURES_FIELD, PICTURES_WAITING, picturesAllowed, picturesWaiting } from "./intakeView.ts";
import { reducer } from "./model.ts";
import type { Case } from "./types.ts";

function waiting(): Case {
  const c = emptyCase(null);
  const report = { file_id: "f1", name: "plans.pdf", status: "partly_read", pictures_not_read_reason: PICTURES_WAITING } as never;
  return { ...c, intake: { record: { files: [report] } } as unknown as Case["intake"] };
}

test("pictures wait for the applicant's OK and stop waiting once it is recorded", () => {
  const c = waiting();
  assert.equal(picturesAllowed(c), false);
  assert.equal(picturesWaiting(c), true);
  const allowed = reducer(c, { type: "setRuleInput", field: PICTURES_FIELD, value: true, rule: "privacy", quote: "Allowed by the applicant" });
  assert.equal(picturesAllowed(allowed), true);
  assert.equal(picturesWaiting(allowed), false);
});

test("a file without waiting pictures asks nothing", () => {
  assert.equal(picturesWaiting(emptyCase(null)), false);
});
