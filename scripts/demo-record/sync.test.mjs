import assert from "node:assert/strict";
import test from "node:test";
import { diffScript, parseDemoScript } from "./sync.mjs";
import { STEPS } from "./steps.mjs";

const EXPECTED = [
  ["1", "Three applicants, one template", "#/"],
  ["2", "Manufacturer intake", "#/describe"],
  ["3", "The fastening article", "#/code-check"],
  ["4", "Section C lookup", "#/section-c"],
  ["5", "What the evidence must address", "#/application?tab=D"],
  ["6", "It will not invent the listing", "#/application?tab=D"],
  ["7", "General contractor, tested system first", "#/describe"],
  ["8", "It will not write the engineering judgment", "#/application?tab=D"],
  ["9", "Homebuilder, one house, one variance", "#/describe"],
  ["10", "Officer, administrative completeness", "#/officer"],
  ["11", "Same record, two authorities", "#/application"],
];

test("recorder steps match the demo script shot list", () => {
  assert.deepEqual(
    STEPS.map((step) => [step.id, step.title, step.route]),
    EXPECTED,
  );
});

test("parser reads shot rows and headings", () => {
  const markdown = `
| Shot | Clock | Case label | Route | Criterion | Pending |
| --- | --- | --- | --- | --- | --- |
| 1 | 0:00–0:12 | All three | \`#/\` | General Applicability 5 | PENDING #16 |
| 7 | 1:34–1:52 | Case B | \`#/describe\` → \`#/code-check\` | Code Identification 20 | PENDING #16 |

### Shot 1 — Three applicants, one template
### Shot 7 — General contractor, tested system first
`;
  const shots = parseDemoScript(markdown);
  assert.equal(shots.length, 2);
  assert.deepEqual(shots[0], { id: "1", route: "#/", title: "Three applicants, one template" });
  assert.equal(shots[1].route, "#/describe");
  assert.equal(shots[1].title, "General contractor, tested system first");
});

test("diff reports title and route drift", () => {
  const markdown = "| 1 | 0:00 | All | `#/nope` | x | y |\n### Shot 1 — Different title\n";
  const diff = diffScript([{ id: "1", title: "Three applicants, one template", route: "#/" }], markdown);
  assert.equal(diff.problems.length, 2);
});

test("diff accepts the recorder against a matching shot list", () => {
  const rows = EXPECTED.map(
    ([id, title, route]) => `| ${id} | 0:00 | Case | \`${route}\` | x | y |\n### Shot ${id} — ${title}`,
  ).join("\n");
  const diff = diffScript(
    EXPECTED.map(([id, title, route]) => ({ id, title, route })),
    rows,
  );
  assert.deepEqual(diff.problems, []);
});
