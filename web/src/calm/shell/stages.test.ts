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

test("applicant stages are icons: no visible words or numbers, names for screen readers and on hover or focus", async () => {
  const h = await componentHarness(new URL("./AppHeader.tsx", import.meta.url), "StageRings", {
    "../icons": { Icon24: "Icon24" },
    "../RelevanceRing": { Tip: "Tip" },
  });
  const tree = expand(await h.render({ stages: STAGES }));
  h.unmount();
  assert.equal(visible(tree).trim(), "", "nothing written in the stage bar");
  const controls = nodes(tree, (n) => n.props?.className?.includes?.("cf-stage ") || n.props?.className === "cf-stage" || /^cf-stage( |$)/.test(n.props?.className ?? ""));
  assert.equal(controls.length, 4);
  assert.deepEqual(controls.map((c) => c.props["aria-label"]), [
    "1 Describe, done", "2 Questions, 40% done", "3 Review, 0% done", "4 Application, 0% done. Nothing filled in yet",
  ]);
  assert.deepEqual(controls.map((c) => c.props["aria-current"]), [undefined, "step", undefined, undefined]);
  assert.deepEqual(controls.map((c) => c.props.href ?? null), ["#/", "#/questions", "#/review", null], "the locked stage is not a link");
  assert.equal(controls[3].props["aria-disabled"], "true");
  assert.deepEqual(nodes(tree, (n) => n.type === "Icon24").map((n) => n.props.name).filter((x) => x !== "check"), ["describe", "questions", "review", "file"]);
  assert.ok(nodes(controls[0], (n) => String(n.props?.className ?? "").includes("cf-stage-done")).length, "a done stage carries its check badge");
  const tips = nodes(tree, (n) => n.type === "Tip");
  assert.equal(tips.length, 4, "every stage has its on-demand label");
});

test("reviewer steps use the same icon control, with the open count as a badge", async () => {
  const h = await componentHarness(new URL("../reviewer/PackageReview.tsx", import.meta.url), "StepTabs", {
    "../auth/bits": { AcIcon: "AcIcon" },
    "../shell/AppHeader": { StageButton: "StageButton" },
  });
  const tree = await h.render({ steps: ["summary", "missing", "checks", "final"], active: "missing", label: (s) => ({ summary: "Overview", missing: "Missing", checks: "Checks", final: "Decide" })[s], counts: { missing: 3 }, onPick() {} });
  h.unmount();
  assert.equal(visible(tree).trim(), "", "no visible step names");
  const controls = nodes(tree, (n) => n.type === "StageButton");
  assert.equal(controls.length, 4);
  assert.deepEqual(controls.map((c) => c.props.ariaLabel), ["Step 1 of 4: Overview, done", "Step 2 of 4: Missing, 3 to look at", "Step 3 of 4: Checks", "Step 4 of 4: Decide"], "a passed step says done, like the applicant stages");
  assert.deepEqual(controls.map((c) => c.props.label), ["Overview", "Missing", "Checks", "Decide"], "the name is the on-demand label");
  assert.deepEqual(controls.map((c) => Boolean(c.props.current)), [false, true, false, false]);
  assert.deepEqual(controls.map((c) => Boolean(c.props.done)), [true, false, false, false], "a passed step shows done");
  assert.equal(controls[1].props.count, 3, "the open count stays visible as a badge on its icon");
  assert.deepEqual(controls.map((c) => c.props.icon.props.name), ["eye", "alert", "list", "scale"]);
});
