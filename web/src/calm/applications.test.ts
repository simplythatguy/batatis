import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../scripts/component-harness.mjs";
import type { ApplicationSummary } from "../api/accounts.ts";
import { groupApplications, readOnly, readOnlyStatus, statusLine } from "./applications.ts";

const NOW = Date.parse("2026-10-21T12:00:00Z");
const app = (over: Partial<ApplicationSummary>): ApplicationSummary => ({
  id: "c1", title: "NorthCore CX exterior sheathing board", status: "draft", authority: "edmonton",
  updated_at: "2026-10-21T11:59:30Z", submitted_at: null, completeness: { answered: 10, total: 16 },
  unread_messages: 0, reviewer: null, ...over,
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
  assert.deepEqual(groupApplications([refused, app({})]), { active: [app({})], settled: [refused] });
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
  });
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
    assert.equal(r.line.props.title, label, "and shown on hover");
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
