import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../scripts/component-harness.mjs";
import type { ApplicationSummary } from "../api/accounts.ts";
import { groupApplications, previewFacts, readOnly, readOnlyStatus, statusLine } from "./applications.ts";
import { placeMenu, placePreview } from "./shell/placement.ts";

const NOW = Date.parse("2026-10-21T12:00:00Z");
const app = (over: Partial<ApplicationSummary>): ApplicationSummary => ({
  id: "c1", title: "NorthCore CX exterior sheathing board", status: "draft", authority: "edmonton",
  updated_at: "2026-10-21T11:59:30Z", submitted_at: null, completeness: { answered: 10, total: 16 },
  unread_messages: 0, reviewer: null, archived: false, pinned: false, ...over,
});

test("status lines: draft, in review, returned with news, settled", () => {
  assert.deepEqual(statusLine(app({}), NOW), { text: "Draft · 63% · just now", tone: "grey", attention: false, unread: 0 });
  assert.equal(statusLine(app({ completeness: null, updated_at: "2026-10-18T12:00:00Z" }), NOW).text, "Draft · 3 d ago");
  assert.equal(statusLine(app({ status: "in_review" }), NOW).text, "In review · Edmonton");
  assert.equal(statusLine(app({ status: "submitted", authority: null }), NOW).text, "Submitted");
  assert.deepEqual(statusLine(app({ status: "returned", unread_messages: 1 }), NOW), { text: "Returned · 1 new message", tone: "accent", attention: true, unread: 1 });
  assert.equal(statusLine(app({ status: "returned", unread_messages: 3 }), NOW).text, "Returned · 3 new messages");
  assert.equal(statusLine(app({ status: "returned" }), NOW).text, "Returned · fix and resubmit");
  assert.equal(statusLine(app({ status: "accepted", authority: "calgary" }), NOW).text, "Accepted · Calgary");
  assert.equal(statusLine(app({ status: "refused", authority: "edmonton" }), NOW).text, "Refused · Edmonton");
  assert.equal(groupApplications([app({ status: "refused" })]).settled.length, 1);
});

test("the list groups settled applications and searches titles", () => {
  const apps = [
    app({ id: "a", title: "Old draft", updated_at: "2026-10-01T00:00:00Z" }),
    app({ id: "b", title: "Rooftop deck guard height", status: "accepted" }),
    app({ id: "c", title: "Hempcrete walls", status: "returned", updated_at: "2026-10-21T10:00:00Z" }),
    app({ id: "d", title: "Basement egress", status: "withdrawn" }),
  ];
  const g = groupApplications(apps);
  assert.deepEqual(g.active.map((a) => a.id), ["c", "a"]);
  assert.deepEqual(g.settled.map((a) => a.id).sort(), ["b", "d"]);
  assert.deepEqual(groupApplications(apps, "hemp").active.map((a) => a.id), ["c"]);
  assert.equal(readOnly("in_review"), true);
  assert.equal(readOnly("returned"), false);
  assert.equal(readOnly("draft"), false);
});

test("refused applications are settled and read-only, without resubmission instructions", () => {
  const refused = app({ id: "refused", status: "refused", unread_messages: 1 });
  assert.equal(readOnly(refused.status), true);
  assert.deepEqual(groupApplications([refused, app({})]), { pinned: [], active: [app({})], settled: [refused], archived: [] });
  assert.deepEqual(statusLine(refused, NOW), { text: "Refused · 1 new message", tone: "accent", attention: true, unread: 1 });
  assert.equal(statusLine({ ...refused, unread_messages: 2 }, NOW).text, "Refused · 2 new messages");
  assert.equal(statusLine({ ...refused, unread_messages: 0 }, NOW).text, "Refused · Edmonton");
  assert.doesNotMatch(statusLine(refused, NOW).text, /returned|fix|resubmit/i);
  const display = readOnlyStatus(refused.status, refused.authority);
  assert.equal(display.label, "Refused · read-only");
  assert.equal(display.heading, "Refused by Edmonton");
  assert.equal(display.tone, "blocking");
  assert.match(display.note, /closed/);
  assert.doesNotMatch(display.note, /until|return|fix|resubmit|missing/i);
  assert.equal(readOnly("returned"), false, "an ordinary return stays editable");
});

test("final statuses stay read-only and never promise an officer return", () => {
  for (const status of ["accepted", "refused", "withdrawn", "future_final_status"]) {
    assert.equal(readOnly(status), true);
    const copy = readOnlyStatus(status, "edmonton");
    assert.doesNotMatch(copy.note + copy.next, /until.*return|if.*return/i);
  }
  assert.match(readOnlyStatus("accepted", "edmonton").note, /administratively complete/);
  assert.match(readOnlyStatus("accepted", "edmonton").note, /does not decide whether the design complies or is safe/);
  assert.match(readOnlyStatus("refused", "edmonton").heading, /Refused by Edmonton/);
  assert.equal(readOnly(undefined), false);
  for (const status of ["submitted", "in_review"]) assert.match(readOnlyStatus(status).next, /if the officer returns it/);
});

import { answerBlocks } from "./assistant/assistant.ts";

test("assistant answers split prose and quoted code text", () => {
  assert.deepEqual(answerBlocks("Cladding is the outer finish. The sentence says:\n> Gypsum sheathing, rigid insulation\n> shall not be used.\nSo if the nails only grip the foam, that departs."), [
    { kind: "p", text: "Cladding is the outer finish. The sentence says:" },
    { kind: "quote", text: "Gypsum sheathing, rigid insulation shall not be used." },
    { kind: "p", text: "So if the nails only grip the foam, that departs." },
  ]);
  assert.deepEqual(answerBlocks("One.\n\nTwo."), [{ kind: "p", text: "One." }, { kind: "p", text: "Two." }]);
});

/** The sidebar row as rendered: what is visible, what a screen reader and a hover hear. */
async function rowFor(a: ApplicationSummary) {
  const h = await componentHarness(new URL("./shell/ApplicationList.tsx", import.meta.url), "ApplicationList", {
    "../applications": await import("./applications.ts"),
    "../icons": { Icon24: "Icon24" },
    "../ui": { MOD_KEY: "⌘" },
  }, { window: { setTimeout: () => 0, clearTimeout() {} } });
  const tree = await h.render({ items: [a], selectedId: a.id, onSelect() {} });
  h.unmount();
  // The list renders one <Row>; it has no hooks, so calling it gives its <li>.
  const element = nodes(tree, (n) => typeof n.type === "function")[0];
  const row = element.type(element.props);
  const line = nodes(row, (n) => String(n.props?.className ?? "").startsWith("cf-list-line"))[0];
  const hidden = (n) => n.props?.["aria-hidden"] === "true" || String(n.props?.className ?? "").includes("cf-sr");
  const visible = (n): string => Array.isArray(n) ? n.map(visible).join("") : n == null || typeof n === "boolean" ? "" : typeof n !== "object" ? String(n) : hidden(n) ? "" : visible(n.props?.children);
  const shown = (n): string => Array.isArray(n) ? n.map(shown).join("") : n == null || typeof n === "boolean" ? "" : typeof n !== "object" ? String(n) : String(n.props?.className ?? "").includes("cf-sr") ? "" : shown(n.props?.children);
  const sr = nodes(line, (n) => String(n.props?.className ?? "").includes("cf-sr")).map(text).join("");
  const icons = nodes(line, (n) => n.type === "Icon24").map((n) => n.props.name);
  return { row, line, seen: shown(line), spoken: `${visible(line)}${sr}`, icons, selected: row.props.className.includes("is-selected") };
}

test("sidebar rows: unread officer messages are a message icon and the count, the words only for hover and screen readers", async () => {
  for (const [status, n, label] of [["returned", 2, "Returned · 2 new messages"], ["returned", 1, "Returned · 1 new message"], ["refused", 3, "Refused · 3 new messages"]] as const) {
    const r = await rowFor(app({ status, unread_messages: n }));
    assert.equal(r.seen, String(n), `${status}/${n}: only the count is visible text`);
    assert.deepEqual(r.icons, ["msg"], "a message icon sits before the count");
    assert.doesNotMatch(r.seen, /new message|Returned|Refused/);
    assert.equal(r.spoken, label, "the full status is still read out");
    assert.ok(previewFacts(app({ status, unread_messages: n })).some((f) => f.icon === "msg" && f.text === `${n} new ${n === 1 ? "message" : "messages"}`), "and in the hover preview");
    assert.ok(r.selected, "the selected state is kept");
  }
  // No unread messages: the short status line stays, with no icon and no bare zero.
  for (const [over, line] of [
    [{ status: "returned", unread_messages: 0 }, "Returned · fix and resubmit"],
    [{ status: "refused", unread_messages: 0 }, "Refused · Edmonton"],
    [{ status: "accepted", unread_messages: 0 }, "Accepted · Edmonton"],
    [{ status: "accepted", unread_messages: 4 }, "Accepted · Edmonton"],
  ] as const) {
    const r = await rowFor(app(over));
    assert.equal(r.seen, line);
    assert.deepEqual(r.icons, []);
  }
});

test("sidebar rows carry no status dot (user decision 2026-10-22)", async () => {
  for (const status of ["draft", "submitted", "in_review", "returned", "accepted", "refused", "withdrawn"] as const) {
    for (const unread_messages of [0, 2]) {
      const r = await rowFor(app({ status, unread_messages }));
      assert.equal(nodes(r.row, (n) => /\bcf-dot\b/.test(String(n.props?.className ?? ""))).length, 0, `${status}/${unread_messages}`);
    }
  }
});

test("pinned rows sit above the rest; archived rows leave the list (they are restored from Settings) and keep their pin", () => {
  const apps = [
    app({ id: "a", title: "Newest draft", updated_at: "2026-10-21T11:00:00Z" }),
    app({ id: "b", title: "Pinned old draft", pinned: true, updated_at: "2026-09-01T00:00:00Z" }),
    app({ id: "c", title: "Pinned accepted", status: "accepted", pinned: true }),
    app({ id: "d", title: "Archived pinned", archived: true, pinned: true, updated_at: "2026-10-21T11:59:59Z" }),
    app({ id: "e", title: "Archived refusal", status: "refused", archived: true }),
    app({ id: "f", title: "Settled", status: "withdrawn" }),
  ];
  const g = groupApplications(apps);
  assert.deepEqual(g.pinned.map((a) => a.id), ["c", "b"]);
  assert.deepEqual(g.active.map((a) => a.id), ["a"]);
  assert.deepEqual(g.settled.map((a) => a.id), ["f"]);
  assert.deepEqual(g.archived.map((a) => a.id).sort(), ["d", "e"]);
  assert.equal(g.archived.find((a) => a.id === "d")?.pinned, true, "the pin waits for the restore");
  // Restoring brings the pin back above the active rows.
  assert.deepEqual(groupApplications(apps.map((a) => (a.id === "d" ? { ...a, archived: false } : a))).pinned.map((a) => a.id), ["d", "c", "b"]);
  assert.deepEqual(groupApplications(apps, "archived").archived.map((a) => a.id).sort(), ["d", "e"], "search still finds them for Settings");
});

test("row preview: real summary fields only, no verdicts", () => {
  const facts = previewFacts(app({ status: "returned", unread_messages: 2, reviewer: { name: "Morgan" }, updated_at: "2026-10-21T09:00:00Z" }), NOW);
  assert.deepEqual(facts.map((f) => f.text), ["Returned · fix and resubmit", "Edmonton", "Morgan", "10 of 16 answered", "2 new messages", "Updated 3 h ago"]);
  assert.equal(previewFacts(app({ status: "accepted" }), NOW)[0].text, "Accepted · completeness only");
  assert.deepEqual(previewFacts(app({ completeness: { answered: 20, total: 16 } }), NOW).find((f) => f.icon === "questions")?.text, "16 of 16 answered");
  assert.equal(previewFacts(app({ completeness: null, authority: null }), NOW).length, 2, "status and update only");
  assert.ok(previewFacts(app({ archived: true }), NOW).some((f) => f.text === "Archived"));
  for (const status of ["draft", "submitted", "in_review", "returned", "accepted", "refused", "withdrawn"] as const) {
    const all = previewFacts(app({ status, completeness: { answered: 16, total: 16 } }), NOW).map((f) => f.text).join(" ");
    assert.doesNotMatch(all, /complies|compliant|safe|certified|approved|perfect|100%/i, status);
  }
});

test("row menu bounds: never wider than the sidebar, never past its left or right edge, inside the viewport", () => {
  const menu = { width: 224, height: 214 };
  const cases = [
    // [name, sidebar box, viewport, anchor]
    ["desktop ⋯, list beside the rail", { left: 68, top: 0, right: 368, bottom: 900 }, { width: 1440, height: 900 }, { x: 352, y: 140, flipY: 104, align: "end" }],
    ["desktop right-click near the list's left edge", { left: 68, top: 0, right: 368, bottom: 900 }, { width: 1440, height: 900 }, { x: 70, y: 300, flipY: 300, align: "start" }],
    ["desktop right-click near the right edge", { left: 68, top: 0, right: 368, bottom: 900 }, { width: 1440, height: 900 }, { x: 366, y: 300, flipY: 300, align: "start" }],
    ["bottom row opens upward", { left: 68, top: 0, right: 368, bottom: 900 }, { width: 1440, height: 900 }, { x: 352, y: 890, flipY: 850, align: "end" }],
    ["phone sheet 390", { left: 64, top: 0, right: 359, bottom: 844 }, { width: 390, height: 844 }, { x: 340, y: 200, flipY: 160, align: "end" }],
    ["narrow resized sidebar", { left: 68, top: 0, right: 248, bottom: 700 }, { width: 800, height: 700 }, { x: 240, y: 100, flipY: 60, align: "end" }],
    ["zoomed: tiny viewport", { left: 30, top: 0, right: 190, bottom: 300 }, { width: 400, height: 300 }, { x: 20, y: 290, flipY: 290, align: "start" }],
  ] as const;
  for (const [name, box, vp, anchor] of cases) {
    const p = placeMenu(anchor, menu, box, vp);
    assert.ok(p.left >= box.left + 8 - 1e-9, `${name}: left edge`);
    assert.ok(p.left + p.width <= box.right - 8 + 1e-9, `${name}: right edge`);
    assert.ok(p.width <= box.right - box.left - 16 + 1e-9, `${name}: width`);
    const h = Math.min(menu.height, p.maxHeight);
    assert.ok(p.top >= 8 && p.top + h <= Math.min(box.bottom, vp.height) - 8 + 1e-9, `${name}: vertical`);
  }
  assert.equal(placeMenu({ x: 352, y: 140, flipY: 104, align: "end" }, menu, { left: 68, top: 0, right: 368, bottom: 900 }, { width: 1440, height: 900 }).left, 352 - 224, "⋯ lines up the menu's right edge");
  assert.equal(placeMenu({ x: 352, y: 890, flipY: 850, align: "end" }, menu, { left: 68, top: 0, right: 368, bottom: 900 }, { width: 1440, height: 900 }).top, 850 - 214, "opens upward from the bottom row");
});

test("row preview sits right of the sidebar only when it fits", () => {
  const side = { left: 68, top: 0, right: 368, bottom: 900 };
  assert.deepEqual(placePreview({ left: 82, top: 200, right: 354, bottom: 270 }, side, { width: 264, height: 180 }, { width: 1440, height: 900 }), { left: 376, top: 200 });
  assert.equal(placePreview({ left: 82, top: 200, right: 354, bottom: 270 }, { left: 64, top: 0, right: 359, bottom: 844 }, { width: 264, height: 180 }, { width: 390, height: 844 }), null, "phone: no room");
  assert.equal(placePreview({ left: 82, top: 860, right: 354, bottom: 900 }, side, { width: 264, height: 180 }, { width: 1440, height: 900 })?.top, 900 - 180 - 8, "bottom row: kept on screen");
});
