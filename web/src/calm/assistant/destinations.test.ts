import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { capturePlace, checkPlan, DESTINATIONS, offeredDestinations, openDestination, registerPanel, type OpenDeps } from "./destinations.ts";
import { libraryDetached, setLibraryDetached } from "../libraryContext.ts";

test("offers follow role and application; reviewer panels and comments only when registered", () => {
  const applicant = offeredDestinations({ role: "applicant", caseId: "A" });
  assert.ok(applicant.includes("question-date") && applicant.includes("references") && applicant.includes("applications"));
  assert.ok(!applicant.some((id) => id.startsWith("review-")) && !applicant.includes("comments"));
  const draft = offeredDestinations({ role: "applicant", caseId: null });
  assert.ok(draft.includes("questions") && !draft.includes("question-date") && !draft.includes("downloads"));
  assert.deepEqual(offeredDestinations({ role: null, caseId: "A" }), []);
  const reviewer = offeredDestinations({ role: "reviewer", caseId: "F" });
  assert.ok(reviewer.includes("review-queue") && !reviewer.includes("review-decide") && !reviewer.includes("questions"));
  const off = registerPanel("review-decide", "F", () => true);
  assert.ok(offeredDestinations({ role: "reviewer", caseId: "F" }).includes("review-decide"));
  assert.ok(!offeredDestinations({ role: "reviewer", caseId: "G" }).includes("review-decide"), "another file's panel is not offered");
  off();
  assert.ok(!offeredDestinations({ role: "reviewer", caseId: "F" }).includes("review-decide"));
  const offComments = registerPanel("comments", "A", () => true);
  assert.ok(offeredDestinations({ role: "applicant", caseId: "A" }).includes("comments"));
  assert.ok(!offeredDestinations({ role: "applicant", caseId: "B" }).includes("comments"));
  offComments();
  assert.throws(() => registerPanel("settings", null, () => true), /not a panel/);
  assert.ok(offeredDestinations({ role: "applicant", caseId: "A" }).length <= 64);
});

test("a registered panel opens for the captured application, and only reports what it really did", async () => {
  const seen: (string | null)[] = [];
  const off = registerPanel("comments", "A", (caseId) => { seen.push(caseId); return false; });
  const deps = {} as OpenDeps;
  assert.equal(await openDestination("comments", "A", deps), false, "a panel that did not open is not opened");
  assert.equal(await openDestination("comments", "B", deps), false, "never for another application");
  assert.deepEqual(seen, ["A"]);
  off();
});

test("plans are checked against binding, generation and the current offer", () => {
  const now = { key: "k", generation: 3, offered: ["settings"] as const };
  assert.equal(checkPlan({ destination: "settings" }, { key: "k", generation: 3 }, { ...now, offered: [...now.offered] }), "apply");
  assert.equal(checkPlan({ destination: "settings" }, { key: "other", generation: 3 }, { ...now, offered: [...now.offered] }), "moved-on");
  assert.equal(checkPlan({ destination: "settings" }, { key: "k", generation: 2 }, { ...now, offered: [...now.offered] }), "moved-on");
  assert.equal(checkPlan({ destination: "notifications" }, { key: "k", generation: 3 }, { ...now, offered: [...now.offered] }), "not-offered");
  assert.equal(checkPlan({ destination: "https://evil.example" }, { key: "k", generation: 3 }, { ...now, offered: [...now.offered] }), "not-offered");
});

test("a route only counts once it is still showing after the app's redirects", async () => {
  let path = "/";
  const deps: OpenDeps = { go: () => { path = "/application"; }, settle: async () => { if (path === "/application") path = "/"; }, path: () => path, card: () => null, shows: () => false };
  assert.equal(await openDestination("application", "A", deps), false);
});

test("opening code from an application restores its native context after an earlier None visit", async () => {
  let path = "/questions";
  const deps: OpenDeps = { go: () => { path = "/code"; }, settle: async () => {}, path: () => path, card: () => null, shows: () => false };
  setLibraryDetached(true);
  assert.equal(await openDestination("code-library", "A", deps), true); assert.equal(libraryDetached(), false);
  setLibraryDetached(true);
  assert.equal(await openDestination("code-library", null, deps), true); assert.equal(libraryDetached(), true);
  setLibraryDetached(false);
});

test("the return point pins the deck's card exactly", () => {
  const place = capturePlace({ path: () => "/questions", card: () => "cand-9.27.3", hash: () => "#/questions", focusId: () => "cf-q", shows: () => false }, "question 4");
  assert.equal(place.href, "#/questions?focus=cand-9.27.3");
  const other = capturePlace({ path: () => "/code/9.27.3.4", card: () => null, hash: () => "#/code/9.27.3.4?filter=all", focusId: () => null, shows: () => false }, "the code library");
  assert.equal(other.href, "#/code/9.27.3.4?filter=all");
});

test("question targets are the deck's real keys, and the palette event matches CodePalette", () => {
  const deck = readFileSync(new URL("../deck.ts", import.meta.url), "utf8");
  assert.match(deck, /key: `field-\$\{d\.id\}`/);
  assert.match(deck, /key: `field-\$\{p\.id\}`/);
  assert.match(deck, /key: "authority"/);
  assert.match(deck, /key: "section-d"/);
  const model = readFileSync(new URL("../../model.ts", import.meta.url), "utf8");
  for (const [id, t] of Object.entries(DESTINATIONS)) {
    if (t.kind !== "route" || !("card" in t) || !t.card?.startsWith("field-")) continue;
    assert.match(model, new RegExp(`id: "${t.card.slice("field-".length)}"`), id);
  }
  const palette = readFileSync(new URL("../CodePalette.tsx", import.meta.url), "utf8");
  assert.match(palette, /OPEN_PALETTE = "cf:open-palette"/);
  assert.match(readFileSync(new URL("./destinations.ts", import.meta.url), "utf8"), /const OPEN_PALETTE = "cf:open-palette"/);
});
