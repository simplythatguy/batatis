import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";
import { diffScript, parseDemoScript } from "./sync.mjs";
import { DECK_STILLS, STEPS } from "./steps.mjs";

const REAL_ADDRESS_GUARD = "11821 73 Avenue NW";

const EXPECTED = [
  ["1", "Three applicants (0:18)", "#/"],
  ["2", "Homebuilder paste (0:10)", "#/describe"],
  ["3", "Not sure (0:23)", "#/"],
  ["4", "Code identification (0:45)", "#/section-c"],
  ["5", "Section D, then the limit (0:24 + 0:08)", "#/application?tab=alt"],
  ["6", "Officer review of the open application (0:36)", "#/officer"],
  ["7", "Authority, gaps open, then the draft variance-form PDF (0:16)", "#/describe"],
];

const SCRIPT_EXCERPT = `
### Shot 1 — Three applicants (0:18)
- **Route:** \`#/\` Who are you?

### Shot 2 — Homebuilder paste (0:10)
- **Route:** \`#/describe\`

### Shot 3 — Not sure (0:23)
- **Route:** \`#/\` then \`#/describe\` then \`#/code-check\`

### Shot 4 — Code identification (0:45)
- **Route:** Case C code check, still open from shot 2, then \`#/section-c\`, then three stills

### Shot 5 — Section D, then the limit (0:24 + 0:08)
- **Route:** \`#/application?tab=alt\`, then \`#/application?tab=D\`

### Shot 6 — Officer review of the open application (0:36)
- **Route:** \`#/officer\`

### Shot 7 — Authority, gaps open, then the draft variance-form PDF (0:16)
- **Route:** \`#/describe\` for the authority select, then \`#/application\`
`;

const DECK_FILES = [
  "shot-s08-roles.png",
  "shot-s02-describe.png",
  "shot-s03-not-sure.png",
  "shot-s04-search.png",
  "shot-s04-benchmark.png",
  "shot-s05-eval.png",
  "shot-s06-section-d.png",
  "shot-s07-officer.png",
  "shot-s09-locked.png",
  "shot-s09-scc-form.png",
];

test("deck still filenames match the screenshot slot list", () => {
  assert.deepEqual(
    DECK_STILLS.map((slot) => slot.file),
    DECK_FILES,
  );
  assert.equal(new Set(DECK_STILLS.map((slot) => slot.id)).size, DECK_STILLS.length);
});

test("recorder steps match the 7-shot demo script", () => {
  assert.deepEqual(
    STEPS.map((step) => [step.id, step.title, step.route]),
    EXPECTED,
  );
});

test("retired 11-shot titles are not in the catalog", () => {
  const titles = STEPS.map((step) => step.title).join("\n");
  for (const banned of [
    "It will not invent the listing",
    "It will not write the engineering judgment",
    "General contractor, tested system first",
    "Same record, two authorities",
    "Homebuilder, one house, one variance",
    "The fastening article",
    "Section C lookup",
  ]) {
    assert.equal(titles.includes(banned), false, banned);
  }
});

test("shot 4 and shot 5 skip when their subject is not on screen", () => {
  const source = readFileSync(new URL("./steps.mjs", import.meta.url), "utf8");
  const shot4 = source.slice(source.indexOf("async function shot4"), source.indexOf("async function shot5"));
  const shot5 = source.slice(source.indexOf("async function shot5"), source.indexOf("async function waitOfficerLoaded"));
  assert.match(shot4, /if \(!search\.added\)/);
  assert.match(shot4, /offline sample/);
  assert.match(shot5, /LIMIT_LINE/);
  assert.match(shot5, /is not on screen/);
  assert.match(shot4, /return skipped/);
  assert.match(shot5, /return skipped/);
  assert.match(source, /demo-recorder-band/);
  assert.match(source, /not a finding that the design complies/);
  assert.equal(source.includes('top: "12px"'), false);
  assert.equal(source.includes('bottom: "16px"'), false);
  const stills = source.slice(source.indexOf("export async function runDeckStills"));
  assert.match(stills, /status: "pending"/);
  assert.match(stills, /provenance:/);
  assert.equal(stills.includes('status: "skipped"'), false);
});

test("the recorder uses the engine unless --offline is set", () => {
  const source = readFileSync(new URL("./record.mjs", import.meta.url), "utf8");
  assert.match(source, /offline: false/);
  assert.match(source, /--offline/);
  assert.match(source, /networkMode: engineSession\.networkMode/);
  assert.match(source, /engineState: engineSession\.engineState/);
  assert.equal(source.includes("blockEngineAndModels"), false);
  assert.equal(source.includes("Recording anyway"), false);
  assert.match(source, /origin\/cursor\/demo-video-script-1e38:docs\/demo\/script\.md/);
  assert.match(source, /sync\.status !== "ok"/);
});

test("the walk does not upload a PDF", () => {
  const source = readFileSync(new URL("./steps.mjs", import.meta.url), "utf8");
  assert.equal(source.includes("setInputFiles"), false);
  assert.equal(source.includes("project-brief.pdf"), false);
  assert.equal(source.includes(REAL_ADDRESS_GUARD), true);
});

test("parser reads legacy shot rows and headings", () => {
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

test("parser reads the 7-shot route lines", () => {
  const shots = parseDemoScript(SCRIPT_EXCERPT);
  assert.deepEqual(
    shots.map((shot) => [shot.id, shot.title, shot.route]),
    EXPECTED,
  );
});

test("diff reports title and route drift", () => {
  const markdown = "| 1 | 0:00 | All | `#/nope` | x | y |\n### Shot 1 — Different title\n";
  const diff = diffScript([{ id: "1", title: "Three applicants (0:18)", route: "#/" }], markdown);
  assert.equal(diff.problems.length, 2);
});

test("diff accepts the recorder against the 7-shot list", () => {
  const diff = diffScript(STEPS, SCRIPT_EXCERPT);
  assert.deepEqual(diff.problems, []);
});

test("this branch does not carry docs/demo/script.md", () => {
  assert.equal(existsSync(new URL("../../docs/demo/script.md", import.meta.url)), false);
});

test("diff accepts the recorder against #20's script", () => {
  const markdown = execFileSync("git", ["show", "origin/cursor/demo-video-script-1e38:docs/demo/script.md"], {
    encoding: "utf8",
  });
  const diff = diffScript(STEPS, markdown);
  assert.equal(diff.shots.length, 7);
  assert.deepEqual(diff.problems, []);
});
