import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";
import { diffScript, parseDemoScript } from "./sync.mjs";
import { DECK_STILLS, STEPS, judgeChrome } from "./steps.mjs";

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
  const shot5 = source.slice(source.indexOf("async function shot5"), source.indexOf("async function openOfficerReview"));
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
  assert.match(stills, /status >= 500/);
  assert.match(stills, /An \/api call returned \$\{failedStatus\}/);
  assert.match(stills, /LIMIT_LINE/);
  assert.match(stills, /Section D tab is current/);
  assert.equal(stills.includes('captureOfficer("shot-s06-section-d")'), false);
  assert.match(stills, /captureOfficer\("shot-s07-officer"\)/);
  assert.match(stills, /Officer review of the open Case A application/);
  assert.match(source, /The footer reads "Online review unavailable"/);
  assert.match(source, /the compliance disclaimer is outside the frame/);
  assert.equal(source.includes("SECTION_D_STILL_LINE"), false);
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
  const sources = source.slice(source.indexOf("const SCRIPT_SOURCES"), source.indexOf("];", source.indexOf("const SCRIPT_SOURCES")));
  const worktree = sources.indexOf('"docs/demo/script.md"');
  const dev = sources.indexOf('"origin/dev:docs/demo/script.md"');
  const branch = sources.indexOf('"origin/cursor/demo-video-script-1e38:docs/demo/script.md"');
  assert.ok(worktree >= 0 && worktree < dev && dev < branch);
  assert.match(source, /loggedWebDir/);
  assert.match(source, /ensureCodeDb/);
  assert.match(source, /openapi\.json/);
  assert.match(source, /Capture aborted/);
  assert.match(source, /sync\.status !== "ok"/);
  assert.match(source, /--allow-drift/);
  assert.match(source, /allowDrift/);
});

test("the officer shot reviews the open application", () => {
  const source = readFileSync(new URL("./steps.mjs", import.meta.url), "utf8");
  const shot6 = source.slice(source.indexOf("async function shot6"), source.indexOf("async function authorityFrame"));
  const stills = source.slice(source.indexOf("shot-s07-officer"), source.lastIndexOf("shot-s09-scc-form"));
  assert.match(shot6, /openOfficerReview/);
  assert.match(shot6, /return pending/);
  assert.match(shot6, /Copy request/);
  assert.equal(shot6.includes("Before fixes"), false);
  assert.equal(shot6.includes("Original example"), false);
  assert.equal(stills.includes("package version control"), false);
  assert.match(source, /OFFICER_INTRO/);
});

test("the walk does not upload a PDF and has no address redactor", () => {
  const source = readFileSync(new URL("./steps.mjs", import.meta.url), "utf8");
  assert.equal(source.includes("setInputFiles"), false);
  assert.equal(source.includes("project-brief.pdf"), false);
  assert.equal(source.includes("maskRealAddress"), false);
  assert.equal(source.includes("11821 73 Avenue NW"), false);
  assert.match(source, /Download draft PDF/);
  assert.equal(source.includes("AI-agent simulated session"), false);
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

function readScriptCandidate(spec) {
  if (!spec.includes(":")) {
    if (!existsSync(spec)) return "";
    return readFileSync(spec, "utf8");
  }
  return execFileSync("git", ["show", spec], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
}

test("diff accepts the script from the working tree, origin/dev, or #20", (t) => {
  const specs = ["docs/demo/script.md", "origin/dev:docs/demo/script.md", "origin/cursor/demo-video-script-1e38:docs/demo/script.md"];
  let markdown = "";
  let used = "";
  for (const spec of specs) {
    try {
      const text = readScriptCandidate(spec);
      if (text) {
        markdown = text;
        used = spec;
        break;
      }
    } catch {
      // The next source in the same order the recorder uses.
    }
  }
  if (!markdown) {
    t.skip("docs/demo/script.md is not in the working tree, origin/dev, or #20");
    return;
  }
  const diff = diffScript(STEPS, markdown);
  assert.equal(diff.shots.length, 7, used);
  assert.deepEqual(diff.problems, []);
});

test("a frame with the compliance disclaimer pushed off screen is rejected", () => {
  const viewport = { width: 1440, height: 900 };
  const onScreen = { top: 800, left: 16, right: 1400, bottom: 860, width: 1384, height: 60 };
  const offScreen = { top: 940, left: 16, right: 1400, bottom: 1000, width: 1384, height: 60 };
  const clear = judgeChrome({
    bandRect: { top: 0, left: 0, right: 1440, bottom: 48, width: 1440, height: 48 },
    subtitleRect: { top: 60, left: 16, right: 400, bottom: 80, width: 384, height: 20 },
    footerRect: onScreen,
    disclaimerRect: onScreen,
    viewport,
  });
  assert.deepEqual(clear, []);
  const rejected = judgeChrome({
    bandRect: null,
    subtitleRect: { top: 60, left: 16, right: 400, bottom: 80, width: 384, height: 20 },
    footerRect: onScreen,
    disclaimerRect: offScreen,
    viewport,
  });
  assert.ok(rejected.includes("the compliance disclaimer is outside the frame"));
});

test("captured stills are not engine-down, and s06 is Section D", () => {
  const log = JSON.parse(readFileSync(new URL("../../artifacts/deck-stills/stills-log.json", import.meta.url), "utf8"));
  assert.equal(log.webDir.includes("/tmp/"), false);
  assert.match(log.engine, /Code search answered/);
  assert.equal(log.engine.includes("returned 503"), false);
  for (const slot of log.slots) {
    const text = JSON.stringify(slot);
    if (slot.status === "captured") {
      assert.match(slot.provenance, /^scripted demo capture, /);
      assert.equal(text.includes("Online review unavailable"), false, slot.id);
    } else {
      assert.equal(slot.status, "pending", slot.id);
      assert.equal(typeof slot.reason, "string");
      assert.ok(slot.reason.length > 0, slot.id);
    }
  }
  const sectionD = log.slots.find((slot) => slot.id === "shot-s06-section-d");
  assert.equal(sectionD.status, "captured");
  const notes = sectionD.notes.join(" ");
  assert.match(notes, /Section D tab is current/);
  assert.match(notes, /recommendations limit line is on screen/);
  assert.equal(notes.includes("is not on this screen"), false);
});
