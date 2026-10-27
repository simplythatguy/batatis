import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes } from "../../../scripts/component-harness.mjs";

/** Text a sighted user reads without hovering: skips aria-hidden, screen-reader-only and tooltip content. */
const visible = (n): string => {
  if (Array.isArray(n)) return n.map(visible).join("");
  if (n == null || typeof n === "boolean") return "";
  if (typeof n !== "object") return String(n);
  if (n.props?.["aria-hidden"] === "true" || String(n.props?.className ?? "").includes("cf-sr") || n.type === "Tip") return "";
  return visible(n.props?.children);
};
/** Text drawn on screen, aria-hidden included (sighted users see it); only tooltips and screen-reader text are skipped. */
const drawn = (n): string => {
  if (Array.isArray(n)) return n.map(drawn).join(" ");
  if (n == null || typeof n === "boolean") return "";
  if (typeof n !== "object") return String(n);
  if (String(n.props?.className ?? "").includes("cf-sr") || n.type === "Tip") return "";
  return drawn(n.props?.children);
};
/** Function components without hooks of their own are expanded so their markup can be read. */
const expand = (n) => {
  if (Array.isArray(n)) return n.map(expand);
  if (!n || typeof n !== "object") return n;
  if (typeof n.type === "function") return expand(n.type(n.props));
  return { ...n, props: { ...n.props, children: expand(n.props?.children) } };
};

const STAGES = [
  { id: "start", label: "Describe", icon: "describe", href: "#/", pct: 100, current: false },
  { id: "questions", label: "Questions", icon: "questions", href: "#/questions", pct: 40, current: true },
  { id: "review", label: "Review", icon: "review", href: "#/review", pct: 0, current: false },
  { id: "application", label: "Application", icon: "file", href: "#/application", pct: 0, current: false, disabled: "Nothing filled in yet" },
];

test("applicant stages: the current stage shows its one-word name beside its icon, the others are icons only", async () => {
  const h = await componentHarness(new URL("./AppHeader.tsx", import.meta.url), "StageRings", {
    "../icons": { Icon24: "Icon24" },
    "../RelevanceRing": { Tip: "Tip" },
  });
  const tree = expand(await h.render({ stages: STAGES }));
  h.unmount();
  const controls = nodes(tree, (n) => /^cf-stage( |$)/.test(n.props?.className ?? ""));
  assert.equal(controls.length, 4);
  // User decision 2026-10-22 (Option A+B): only the current stage draws its name; no fill marks it.
  assert.equal(drawn(tree).replace(/\s+/g, " ").trim(), "Questions", "the current stage's name is the only word in the stage bar");
  assert.deepEqual(controls.map((c) => drawn(c).trim()), ["", "Questions", "", ""], "the other stages draw no name");
  assert.equal(nodes(tree, (n) => n.props?.className === "cf-stage-word").length, 1, "one visible stage word");
  assert.deepEqual(controls.map((c) => c.props["aria-label"]), [
    "1 Describe, done", "2 Questions, 40% done", "3 Review, 0% done", "4 Application, 0% done. Nothing filled in yet",
  ]);
  assert.deepEqual(controls.map((c) => c.props["aria-current"]), [undefined, "step", undefined, undefined]);
  assert.deepEqual(controls.map((c) => c.props.href ?? null), ["#/", "#/questions", "#/review", null], "the locked stage is not a link");
  assert.equal(controls[3].props["aria-disabled"], "true");
  assert.deepEqual(nodes(tree, (n) => n.type === "Icon24").map((n) => n.props.name).filter((x) => x !== "check"), ["describe", "questions", "review", "file"], "every stage keeps its own icon");
  assert.equal(nodes(controls[0], (n) => String(n.props?.className ?? "").includes("cf-stage-done")).length, 1, "a done stage keeps a small done mark");
  assert.equal(nodes(tree, (n) => String(n.props?.className ?? "").includes("cf-stage-done")).length, 1, "only done stages carry it");
  assert.equal(nodes(controls[1], (n) => n.props?.className === "cf-stage-bar").length, 1, "a stage part of the way through shows its progress line");
  assert.equal(nodes(tree, (n) => n.props?.className === "cf-stage-bar").length, 1, "no line on done or untouched stages");
  const tips = nodes(tree, (n) => n.type === "Tip");
  assert.equal(tips.length, 4, "every stage, the current one included, has its on-demand label");
  assert.ok(tips.every((t) => t.props.open === false), "labels wait for hover or focus");
});

test("reviewer steps use the same control, with the open count beside the icon", async () => {
  const h = await componentHarness(new URL("../reviewer/PackageReview.tsx", import.meta.url), "StepTabs", {
    "../auth/bits": { AcIcon: "AcIcon" },
    "../shell/AppHeader": { StageButton: "StageButton" },
  });
  const tree = await h.render({ steps: ["summary", "missing", "checks", "final"], active: "missing", label: (s) => ({ summary: "Request", missing: "Missing", checks: "Checks", final: "Decide" })[s], counts: { missing: 3 }, onPick() {} });
  h.unmount();
  assert.equal(visible(tree).trim(), "", "no visible step names");
  const controls = nodes(tree, (n) => n.type === "StageButton");
  assert.equal(controls.length, 4);
  assert.deepEqual(controls.map((c) => c.props.ariaLabel), ["Step 1 of 4: Request", "Step 2 of 4: Missing, 3 to look at", "Step 3 of 4: Checks", "Step 4 of 4: Decide"], "passing a package view never completes an administrative check");
  assert.deepEqual(controls.map((c) => c.props.label), ["Request", "Missing", "Checks", "Decide"], "the name is the on-demand label");
  assert.deepEqual(controls.map((c) => Boolean(c.props.current)), [false, true, false, false]);
  assert.deepEqual(controls.map((c) => Boolean(c.props.done)), [false, false, false, false], "navigation never marks a check done");
  assert.equal(controls[1].props.count, 3, "the open count stays visible beside its icon");
  assert.deepEqual(controls.map((c) => c.props.icon.props.name), ["doc", "alert", "list", "scale"], "Request is a document; Missing, Checks and Decide keep their icons");
});

test("a resubmitted file's Changes step is the history icon, ahead of the others", async () => {
  const h = await componentHarness(new URL("../reviewer/PackageReview.tsx", import.meta.url), "StepTabs", {
    "../auth/bits": { AcIcon: "AcIcon" },
    "../shell/AppHeader": { StageButton: "StageButton" },
  });
  const tree = await h.render({ steps: ["changes", "summary", "missing", "checks", "final"], active: "changes", label: (s) => ({ changes: "Changes", summary: "Request", missing: "Missing", checks: "Checks", final: "Decide" })[s], counts: { missing: 2 }, onPick() {} });
  h.unmount();
  const controls = nodes(tree, (n) => n.type === "StageButton");
  assert.deepEqual(controls.map((c) => c.props.icon.props.name), ["history", "doc", "alert", "list", "scale"]);
  assert.deepEqual(controls.map((c) => Boolean(c.props.current)), [true, false, false, false, false]);
  assert.equal(controls[2].props.count, 2, "a later step keeps its real open count");
});

test("the current step draws its name and open count; another step draws only its count", async () => {
  const h = await componentHarness(new URL("./AppHeader.tsx", import.meta.url), "StageButton", {
    "../icons": { Icon24: "Icon24" },
    "../RelevanceRing": { Tip: "Tip" },
  }, { window: { addEventListener() {}, removeEventListener() {}, dispatchEvent() {} }, CustomEvent: class {} });
  const props = { id: "rv-missing", label: "Missing", ariaLabel: "Step 2 of 4: Missing, 7 to look at", icon: { type: "AcIcon", props: { name: "alert" } }, pct: 100, count: 7, onClick() {} };
  const current = expand(await h.render({ ...props, current: true }));
  assert.equal(drawn(current).replace(/\s+/g, " ").trim(), "Missing 7", "name, then the count (the state's own number)");
  assert.equal(current.props.children[0].props["aria-current"], "step");
  const other = expand(await h.render({ ...props, current: false }));
  assert.equal(drawn(other).replace(/\s+/g, " ").trim(), "7", "no name on a step that is not current");
  assert.equal(other.props.children[0].props["aria-current"], undefined);
  const tips = nodes(other, (n) => n.type === "Tip");
  assert.equal(tips.length, 1, "the hover or focus label stays");
  h.unmount();
});
