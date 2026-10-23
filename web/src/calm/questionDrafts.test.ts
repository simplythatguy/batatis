import assert from "node:assert/strict";
import { test } from "node:test";
import { QuestionDrafts } from "./questionDrafts";

test("unconfirmed text and choices stay on the exact application and card without saving", () => {
  const d = new QuestionDrafts(); d.selectAccount("applicant:A");
  d.write("case A", "question 1", "saved", "half typed");
  d.writeChoices("case A", { condition: "does_not_apply" });
  assert.equal(d.read("case B", "question 1", "saved"), "saved");
  assert.equal(d.read("case A", "question 2", ""), "");
  assert.equal(d.read("case A", "question 1", "saved"), "half typed");
  assert.deepEqual(d.readChoices("case B"), {});
  assert.equal(d.readChoices("case A").condition, "does_not_apply");
});

test("a newer saved answer replaces an older draft", () => {
  const d = new QuestionDrafts(); d.selectAccount("A");
  d.write("case", "card", "", "typed");
  assert.equal(d.read("case", "card", "confirmed elsewhere"), "confirmed elsewhere");
  assert.equal(d.read("case", "card", ""), "");
});

test("signout, another account or role change clears private drafts and choices", () => {
  const d = new QuestionDrafts(); d.selectAccount("A/applicant");
  d.write("case", "card", "", "private"); d.writeChoices("case", { card: "yes" });
  d.selectAccount(null); d.selectAccount("A/applicant");
  assert.equal(d.read("case", "card", ""), ""); assert.deepEqual(d.readChoices("case"), {});
  d.write("case", "card", "", "private"); d.selectAccount("A/reviewer");
  assert.equal(d.read("case", "card", ""), "");
});

test("new cases with identical local IDs stay separate and saved IDs restore across reopening", () => {
  const d = new QuestionDrafts();
  const first = d.scope("owner", 1, null); d.write(first, "card", "", "A unfinished"); d.writeChoices(first, { condition: "does_not_apply" });
  const savedA = d.scope("owner", 1, "saved-A");
  assert.equal(d.read(savedA, "card", ""), "A unfinished", "first save retains local typing");
  assert.equal(d.readChoices(savedA).condition, "does_not_apply");
  const second = d.scope("owner", 2, null); assert.equal(d.read(second, "card", ""), "");
  const savedB = d.scope("owner", 2, "saved-B"); d.write(savedB, "card", "", "B unfinished");
  const reopenedA = d.scope("owner", 3, "saved-A");
  assert.equal(d.read(reopenedA, "card", ""), "A unfinished");
  assert.equal(d.read(savedB, "card", ""), "B unfinished");
});
