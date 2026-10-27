import assert from "node:assert/strict";
import test from "node:test";
import { observeJob, type CaseJob } from "./jobs";

const job: CaseJob = { id: "job-a", case_id: "case-a", kind: "intake", state: "queued", stage: "queued", attempts: 0,
  created_at: "2026-10-26T00:00:00Z", updated_at: "2026-10-26T00:00:00Z",
  max_attempts: 3, base_version: 1, result_version: null, started_at: null, finished_at: null, next_attempt_at: null,
  heartbeat_at: null, lease_expires_at: null, error: null, can_retry: false, result_url: null };
const microtasks = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); };

test("persisted work keeps polling beyond thirty seconds; only a terminal status finishes it", async t => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const ctl = new AbortController(), changes: string[] = [];
  let polls = 0, terminal = false, finished = 0;
  observeJob({ job, signal: ctl.signal, interval: 1000,
    read: async () => { polls++; return { ...job, state: terminal ? "succeeded" : "running", stage: "review" }; },
    change: value => changes.push(value.state), failure: error => { throw error; }, finished: async () => { finished++; },
  });
  for (let seconds = 0; seconds < 42; seconds++) { t.mock.timers.tick(1000); await microtasks(); }
  assert.equal(polls, 42); assert.equal(finished, 0); assert.equal(changes.at(-1), "running");
  terminal = true; t.mock.timers.tick(1000); await microtasks();
  assert.equal(finished, 1); assert.equal(changes.at(-1), "succeeded");
  t.mock.timers.tick(10000); await microtasks(); assert.equal(polls, 43);
});

test("a late result for an old application is ignored after its view is retired", async t => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const ctl = new AbortController(), changes: CaseJob[] = [];
  let release!: (value: CaseJob) => void, finished = 0;
  const response = new Promise<CaseJob>(resolve => { release = resolve; });
  observeJob({ job, signal: ctl.signal, interval: 1000, read: () => response,
    change: value => changes.push(value), failure: error => { throw error; }, finished: async () => { finished++; },
  });
  t.mock.timers.tick(1000); await microtasks(); ctl.abort();
  release({ ...job, state: "succeeded" }); await microtasks();
  assert.deepEqual(changes.map(value => value.state), ["queued"]); assert.equal(finished, 0);
});

test("a status response with a different case identity never applies or finishes", async t => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const ctl = new AbortController(), failures: unknown[] = [], changes: CaseJob[] = [];
  let finished = 0;
  observeJob({ job, signal: ctl.signal, interval: 1000, read: async () => ({ ...job, case_id: "case-b", state: "succeeded" }),
    change: value => changes.push(value), failure: error => failures.push(error), finished: async () => { finished++; },
  });
  t.mock.timers.tick(1000); await microtasks();
  assert.equal(failures.length, 1); assert.equal(changes.length, 1); assert.equal(finished, 0);
});
