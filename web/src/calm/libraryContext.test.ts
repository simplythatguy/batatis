import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness } from "../../scripts/component-harness.mjs";
import * as relevance from "./relevance.ts";
import { chooseContext, contextOptions, KEEP_OPEN_NOTE, NO_APPLICATION, switchApplication } from "./libraryContext.ts";
import type { ApplicationSummary } from "../api/accounts";

class CodeLibraryError extends Error {}

const deferred = <T,>() => {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => { resolve = r; });
  return { promise, resolve };
};
const settle = () => new Promise((resolve) => setImmediate(resolve));

const record = (scores: Record<string, number>) => ({
  status: "scored", model: "relevance-2", scored_at: "2026-10-22T12:00:00Z", description_sha256: "0", stale: false,
  scores, rerank: scores, display: scores, bands: { x: 0, y: 1, status: "uncalibrated; display range only" },
});
const A_SCORES = { "9.10.1.1.": 0.9 };
const B_SCORES = { "9.20.1.1.": 0.6 };

/**
 * The real relevance hook over a stubbed engine and a switchable application context:
 * what the code library's rings, filters and Score button read.
 */
async function relevanceWorld() {
  const world = {
    engineId: "case-a" as string | null,
    scope: "application" as "application" | "none",
    epoch: 0,
    gets: [] as { id: string; reply: ReturnType<typeof deferred<unknown>> }[],
    posts: [] as string[],
    saves: [] as ReturnType<typeof deferred<string | null>>[],
  };
  const h = await componentHarness(new URL("./useRelevance.ts", import.meta.url), "useRelevance", {
    "../api/codeLibrary": {
      CodeLibraryError,
      codeLibrary: {
        relevance: (id: string) => { const reply = deferred<unknown>(); world.gets.push({ id, reply }); return reply.promise; },
        score: async (id: string) => { world.posts.push(id); return record({}); },
      },
    },
    "../store": {
      useCase: () => ({
        engineId: world.engineId, c: { description: "Synthetic project." }, phase: "case",
        saveDraft: () => { const d = deferred<string | null>(); world.saves.push(d); return d.promise; },
      }),
    },
    "./codeScope": { useCodeScope: () => world.scope },
    "./libraryContext": { libraryEpoch: () => world.epoch },
    "./relevance": relevance,
  });
  await h.render({});
  return { world, h, reset: h.exports.resetRelevance as () => void };
}

test("library context None: no scores, no Score button reason, and no relevance request of any kind", async () => {
  const { world, h } = await relevanceWorld();
  world.scope = "none";
  const rel = await h.render();
  rel.refresh();
  await rel.score();
  await settle();
  assert.equal(world.gets.length, 0, "None reads no application's scores");
  assert.equal(world.posts.length, 0, "None never starts paid scoring");
  assert.equal(world.saves.length, 0, "None never saves the hidden draft");
  const after = await h.render();
  assert.equal(after.scope, "none");
  assert.equal(after.display, undefined);
  assert.equal(after.blocked, "", "no 'Start your application first' nag");
  assert.equal(after.shown("9.10.1.1.").band, "unscored");
  h.unmount();
});

test("A → None → A: A's scores hide under None and come back for A, never for another case", async () => {
  const { world, h } = await relevanceWorld();
  (await h.render()).refresh();
  world.gets[0].reply.resolve(record(A_SCORES));
  await settle();
  assert.equal((await h.render()).display?.["9.10.1.1."], 0.9);
  world.scope = "none";
  world.epoch++;
  const none = await h.render();
  assert.equal(none.display, undefined, "None shows no application's percentages");
  none.refresh();
  assert.equal(world.gets.length, 1, "switching to None makes no request");
  world.scope = "application";
  world.epoch++;
  assert.equal((await h.render()).display?.["9.10.1.1."], 0.9, "returning to A shows A's scores");
  h.unmount();
});

test("a late GET for application A never shows as B's scores after switching to B", async () => {
  const { world, h, reset } = await relevanceWorld();
  (await h.render()).refresh();
  // The switch: the shell opens B and resets the shared scores before B's library asks for its own.
  world.engineId = "case-b";
  reset();
  (await h.render()).refresh();
  assert.deepEqual(world.gets.map((g) => g.id), ["case-a", "case-b"]);
  world.gets[0].reply.resolve(record(A_SCORES));
  await settle();
  const between = await h.render();
  assert.equal(between.display, undefined, "A's late answer is dropped");
  assert.equal(between.caseId, "case-b");
  world.gets[1].reply.resolve(record(B_SCORES));
  await settle();
  const b = await h.render();
  assert.deepEqual(b.display, B_SCORES);
  h.unmount();
});

test("the opened application's own GET, started before the switch settles, still shows its scores", async () => {
  const { world, h, reset } = await relevanceWorld();
  // The library asks for B as soon as B is the open case; the shell then clears the last case's scores.
  world.engineId = "case-b";
  (await h.render()).refresh();
  reset();
  world.gets[0].reply.resolve(record(B_SCORES));
  await settle();
  assert.deepEqual((await h.render()).display, B_SCORES, "B is not left 'Not scored' with no request on its way");
  h.unmount();
});

test("Score pressed on A, then None chosen while A's draft saves: no paid scoring starts", async () => {
  const { world, h } = await relevanceWorld();
  const pending = (await h.render()).score();
  await settle();
  assert.equal(world.saves.length, 1, "Score saves the draft first");
  world.scope = "none";
  world.epoch++;
  world.saves[0].resolve("case-a");
  await pending;
  await settle();
  assert.deepEqual(world.posts, [], "the request is dropped once the context changed");
  h.unmount();
});

test("Score pressed on A, then B opened while A's draft saves: nothing is scored for either case", async () => {
  const { world, h, reset } = await relevanceWorld();
  const pending = (await h.render()).score();
  await settle();
  world.engineId = "case-b";
  reset();
  world.saves[0].resolve("case-a");
  await pending;
  await settle();
  assert.deepEqual(world.posts, []);
  assert.equal((await h.render()).phase, "idle", "B shows no running score that belongs to A");
  h.unmount();
});

/* —— Choosing the context —— */

function switchDeps(over: Partial<Parameters<typeof switchApplication>[1]> = {}) {
  const calls: string[] = [];
  const deps: Parameters<typeof switchApplication>[1] = {
    inCase: true,
    saveStatus: "saved",
    saveDraft: async () => { calls.push("save"); return "case-a"; },
    openCase: async (id) => { calls.push(`open ${id}`); return null; },
    settle: () => { calls.push("settle"); },
    ...over,
  };
  return { deps, calls };
}

test("switching applications saves the open draft's unsaved answers before opening the other one", async () => {
  const { deps, calls } = switchDeps({ saveStatus: "unsaved" });
  assert.equal(await switchApplication("case-b", deps), null);
  assert.deepEqual(calls, ["save", "open case-b", "settle"]);
});

test("a draft whose save failed is saved again before switching; a second failure keeps it open", async () => {
  const { deps, calls } = switchDeps({ saveStatus: "failed", saveDraft: async () => { calls.push("save"); return null; } });
  assert.equal(await switchApplication("case-b", deps), KEEP_OPEN_NOTE);
  assert.deepEqual(calls, ["save"], "nothing opened, nothing reset: the unsaved answers stay in this application");
});

test("a deleted or unreadable application reports the engine's reason and changes nothing", async () => {
  const { deps, calls } = switchDeps({ openCase: async (id) => { calls.push(`open ${id}`); return "That application was deleted or has expired."; } });
  assert.equal(await switchApplication("case-gone", deps), "That application was deleted or has expired.");
  assert.deepEqual(calls, ["open case-gone"]);
});

function chooser(openId: string | null, switchTo = async (_id: string): Promise<string | null> => null) {
  const calls: string[] = [];
  return {
    calls,
    deps: {
      openId,
      detach: (on: boolean) => { calls.push(on ? "detach" : "attach"); },
      switchTo: async (id: string) => { calls.push(`switch ${id}`); return switchTo(id); },
    },
  };
}

test("None only detaches the library: the open draft is not saved, reset or reopened", async () => {
  const { deps, calls } = chooser("case-a");
  assert.equal(await chooseContext(NO_APPLICATION, deps), null);
  assert.deepEqual(calls, ["detach"]);
});

test("choosing the open application again re-attaches without reopening (unsaved answers stay)", async () => {
  const { deps, calls } = chooser("case-a");
  assert.equal(await chooseContext("case-a", deps), null);
  assert.deepEqual(calls, ["attach"]);
});

test("choosing another application goes through the guarded switch, and attaches only once it is open", async () => {
  const ok = chooser("case-a");
  assert.equal(await chooseContext("case-b", ok.deps), null);
  assert.deepEqual(ok.calls, ["switch case-b", "attach"]);
  const refused = chooser("case-a", async () => KEEP_OPEN_NOTE);
  assert.equal(await chooseContext("case-b", refused.deps), KEEP_OPEN_NOTE);
  assert.deepEqual(refused.calls, ["switch case-b"], "a refused switch leaves the context as it was");
});

const app = (id: string, over: Partial<ApplicationSummary> = {}): ApplicationSummary => ({
  id, title: id, status: "draft", authority: "edmonton", updated_at: "2026-10-22T10:00:00Z", submitted_at: null,
  completeness: { answered: 1, total: 4 }, unread_messages: 0, reviewer: null, archived: false, pinned: false, ...over,
});

test("the options are the account's own applications with their short titles; archived ones only when open", () => {
  const items = [
    app("case-old", { title: "Old porch", updated_at: "2026-10-01T10:00:00Z" }),
    app("case-sent", { title: "Infill sheathing", status: "submitted", updated_at: "2026-10-20T10:00:00Z" }),
    app("case-pin", { title: "Garage", pinned: true, updated_at: "2026-09-01T10:00:00Z" }),
    app("case-arch", { title: "Shed", archived: true }),
  ];
  const opts = contextOptions(items, "case-old");
  assert.deepEqual(opts.map((o) => o.id), ["case-pin", "case-sent", "case-old"]);
  assert.deepEqual(opts.map((o) => o.title), ["Garage", "Infill sheathing", "Old porch"]);
  assert.equal(opts.find((o) => o.id === "case-sent")?.readOnly, true, "a sent application keeps its read-only status");
  assert.equal(opts.find((o) => o.id === "case-old")?.open, true);
  assert.ok(contextOptions(items, "case-arch").some((o) => o.id === "case-arch"), "the open application is always offered");
  assert.equal(contextOptions([app("x", { title: "  " })], null)[0].title, "Untitled application");
});

/* —— The reader's write: "Add to my application" —— */

import * as provisions from "../provisions.ts";
import * as applications from "./applications.ts";
import { nodes, text } from "../../scripts/component-harness.mjs";

async function addAction(world: { scope: "application" | "none"; engineId: string; status: string | null; sending?: boolean }) {
  const dispatched: { to: string; action: { type: string; candidate?: { provision: string } } }[] = [];
  const h = await componentHarness(new URL("./CodeLibrary.tsx", import.meta.url), "AddToApplication", {
    "../store": {
      useCase: () => ({
        engineId: world.engineId, phase: "case", c: { candidates: [] },
        dispatch: (action: never) => dispatched.push({ to: world.engineId, action }),
      }),
    },
    "./begin": {
      useCurrentApplication: () => {
        const app = world.status ? { id: world.engineId, status: world.status, authority: "edmonton" } : null;
        const readOnly = applications.readOnly(app?.status as never);
        // `sending`: a dispatched submission is on its way (begin.ts: locked, not yet read-only).
        return { app, locked: Boolean(world.sending) || readOnly, readOnly };
      },
    },
    "./codeScope": { useCodeScope: () => world.scope },
    "../provisions": provisions,
    "./applications": applications,
    "../screens/SectionC": { provisionCandidate: (r: { id: string }) => ({ id: `search-${r.id}`, provision: r.id }) },
    "./ui": { CIcon: () => null },
  });
  const props = { id: "9.10.15.4.", record: { id: "9.10.15.4.", title: "Area", article_title: "Area", text: "Synthetic.", citation: "NBC(AE) 2023" } };
  const button = (tree: unknown) => nodes(tree, (n: { type: unknown }) => n.type === "button")[0] as { props: { onClick: () => void; disabled?: boolean } } | undefined;
  return { h, props, dispatched, button };
}

test("None offers no write: the hidden open application cannot receive the article", async () => {
  const world = { scope: "none" as const, engineId: "case-a", status: "draft" };
  const { h, props, dispatched, button } = await addAction(world);
  const tree = await h.render(props);
  assert.equal(button(tree), undefined);
  assert.doesNotMatch(text(tree), /Add to my application|Start an application/);
  assert.equal(dispatched.length, 0);
  h.unmount();
});

test("a sent application stays read-only in the library: no Add, a read-only note instead", async () => {
  for (const status of ["submitted", "in_review", "accepted", "refused"]) {
    const { h, props, button } = await addAction({ scope: "application", engineId: "case-a", status });
    const tree = await h.render(props);
    assert.equal(button(tree), undefined, `${status} cannot be changed from the library`);
    assert.match(text(tree), /Your saved application is read-only\. You can still read the code\./);
    h.unmount();
  }
});

test("a submission on its way pauses Add: the button stays, disabled, and the draft is not called read-only", async () => {
  for (const status of ["draft", "returned"]) {
    const { h, props, dispatched, button } = await addAction({ scope: "application", engineId: "case-a", status, sending: true });
    const tree = await h.render(props);
    const add = button(tree);
    assert.ok(add, `${status}: the mounted control stays while the saved revision is sent`);
    assert.equal(add.props.disabled, true);
    add.props.onClick();
    assert.equal(dispatched.length, 0, "a late click cannot change the revision on its way");
    assert.doesNotMatch(text(tree), /read-only/);
    h.unmount();
  }
});

test("Add writes to the application the library reads for, and its note never follows a switch", async () => {
  const world = { scope: "application" as "application" | "none", engineId: "case-a", status: "draft" };
  const { h, props, dispatched, button } = await addAction(world);
  button(await h.render(props))!.props.onClick();
  assert.deepEqual(dispatched.map((d) => [d.to, d.action.type, d.action.candidate?.provision]), [["case-a", "addCandidate", "9.10.15.4."]]);
  assert.match(text(await h.render(props)), /Added as a Code check card/);
  world.engineId = "case-b";
  const b = await h.render(props);
  assert.doesNotMatch(text(b), /Added as a Code check card/, "B was never given this article");
  assert.ok(button(b), "B can add it itself");
  h.unmount();
});

test("a made-up article link shows one not-found state and never cites the article", async () => {
  const missing = Object.assign(new Error("That provision was not found."), { status: 404, detail: "That provision was not found." });
  const h = await componentHarness(new URL("./CodeLibrary.tsx", import.meta.url), "Reading", {
    "./codeData": { useText: () => ({ state: "error", error: missing, retry() {} }), useContext: () => ({ state: "error", error: missing, retry() {} }), errorText: (e: Error) => ({ text: e.message }) },
    "./codeScope": { useCodeScope: () => "application" },
    "./routes": { codeHref: () => "#/code" },
    "./ui": { CIcon: () => null },
  });
  const tree = await h.render({ id: "99.99.99.", filter: "all", index: new Map(), narrow: false });
  const shown = text(tree);
  assert.doesNotMatch(shown, /Article 99\.99\.99\.|NBC\(AE\)/, "no citation for a provision that does not exist");
  assert.equal(nodes(tree, (n: { type: unknown }) => n.type === "button").length, 0, "no Try again for a missing provision");
  assert.equal(shown.match(/not in the code/g)?.length, 1);
  h.unmount();
});
