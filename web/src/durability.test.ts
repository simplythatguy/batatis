/** Real mounted provider and editors; mocked HTTP only. No server, ports, model or capture. */
import assert from "node:assert/strict";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import test from "node:test";
import { createHash } from "node:crypto";
import { rolldown } from "rolldown";

let playwright;
try { playwright = await import(process.env.PLAYWRIGHT_MODULE ? pathToFileURL(process.env.PLAYWRIGHT_MODULE).href : "playwright-core"); }
catch (error) { if (error.code !== "ERR_MODULE_NOT_FOUND") throw error; }

test("mounted durable saves and jobs (mocked HTTP; no listeners)", { skip: !playwright && "Set PLAYWRIGHT_MODULE to installed playwright-core" }, async t => {
  const directory = await mkdtemp(join(tmpdir(), "batatis-durable-unit-"));
  const build = await rolldown({ input: fileURLToPath(new URL("../tests/durable-provider.tsx", import.meta.url)), platform: "browser", moduleTypes: { ".css": "empty" },
    transform: { define: { "process.env.NODE_ENV": '"production"', "import.meta.env": JSON.stringify({ VITE_ENGINE_URL: "https://batatis.unit.test/api" }) }, jsx: { runtime: "automatic" } } });
  let script;
  try { script = (await build.generate({ format: "iife" })).output.filter(f => f.type === "chunk").map(f => f.code).join("\n"); }
  finally { await build.close(); }
  const path = join(directory, "provider.html");
  await writeFile(path, `<!doctype html><meta charset="utf-8"><div id="root"></div><script>${script.replaceAll("</script", "<\\/script")}</script>`);
  const template = JSON.parse(await readFile(new URL("./calm/fixtures/reopen-api-case.json", import.meta.url), "utf8"));
  const browser = await playwright.chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
  try {
    const cases = new Map(), jobs = new Map(), jobKeys = new Map(), jobInputs = new Map(), uploads = new Map(), requests = [];
    let nextCase = 0, nextJob = 0, rejectDraft = false, rejectUpload = false, held = null, heldUpload = null, nextFile = 0, loggedOut = false;
    let handlerRevision = 1, retryChanged = false, ambiguousStart = false;
    let workerAvailable = true;
    let heldJobs = null, heldLogout = null, rejectLogout = false, rejectCancel = false;
    const context = await browser.newContext();
    await context.route("https://batatis.unit.test/**", async route => {
      const req = route.request(), method = req.method(), url = new URL(req.url()).pathname.replace(/^\/api/, "");
      const body = req.headers()["content-type"]?.includes("application/json") ? req.postDataJSON() : null;
      requests.push({ method, url, body, key: req.headers()["idempotency-key"] });
      const reply = (value, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(value) });
      if (url === "/auth/me") return loggedOut ? reply({ detail: "signed out" }, 401) : reply({ user: {
        id: "durability-owner", role: "applicant", authority: null, applicant_type: "homebuilder", name: "Synthetic applicant",
        email: "synthetic@example.test", onboarded: true, created_at: "2026-10-26T00:00:00Z",
      } });
      if (url === "/auth/logout") {
        if (heldLogout) { const wait = heldLogout; heldLogout = null; await wait.promise; }
        if (rejectLogout) return reply({ detail: "fixture logout failed" }, 503);
        loggedOut = true; return reply({});
      }
      if (url === "/me/applications") return reply({ applications: [] });
      if (url === "/cases" && method === "POST") {
        const id = `case-${++nextCase}`;
        const saved = { ...structuredClone(template), id, title: null, facts: [], provisions: [], selected_articles: null,
          intake: null, identify: null, applicant_draft: null, jurisdiction: body.jurisdiction ?? null, authority: body.jurisdiction?.id ?? null,
          evidence: [], status: "draft", version: 1, decision: null };
        cases.set(id, saved); return reply(saved);
      }
      const match = /^\/cases\/([^/]+)(.*)$/.exec(url);
      if (!match) return reply({ detail: "fixture route unavailable" }, 404);
      const [, id, suffix] = match, saved = cases.get(id);
      if (!saved) return reply({ detail: "case not found" }, 404);
      if (!suffix && method === "GET") return reply(saved);
      if (suffix === "/draft" && method === "PATCH") {
        if (held) { const wait = held; held = null; await wait.promise; }
        if (rejectDraft) return reply({ detail: "fixture failed save" }, 503);
        if (body.expected_version !== saved.version) return reply({ detail: "saved application changed" }, 409);
        if (body.facts) {
          const ids = new Set(body.facts.map(f => f.id));
          saved.facts = [...saved.facts.filter(f => !ids.has(f.id)), ...body.facts];
        }
        for (const key of ["applicant_draft", "jurisdiction", "selected_articles"]) if (key in body) saved[key] = body[key];
        if ("jurisdiction" in body) saved.authority = body.jurisdiction?.id ?? null;
        saved.version++; return reply(saved);
      }
      if (suffix === "/jobs" && method === "GET") {
        if (heldJobs) { const wait = heldJobs; heldJobs = null; await wait.promise; }
        return reply({ items: [...jobs.values()].filter(j => j.case_id === id) });
      }
      if (suffix === "/jobs/health" && method === "GET") return reply({ worker_available: workerAvailable,
        last_heartbeat_at: workerAvailable ? new Date().toISOString() : null, queued: 0, running: 1, execution: "external_required" });
      if (suffix === "/files" && method === "POST") {
        if (heldUpload) { const wait = heldUpload; heldUpload = null; await wait.promise; }
        if (rejectUpload) return reply({ detail: "fixture upload failed" }, 503);
        const file = { id: `file-${++nextFile}`, name: "evidence.pdf", size: 4, content_type: "application/pdf" };
        uploads.set(file.id, { ...file, case_id: id }); return reply(file);
      }
      if (suffix === "/files" && method === "GET") return reply({ items: [...uploads.values()].filter(file => file.case_id === id) });
      if (/^\/(intake|identify)\/jobs$/.test(suffix) && method === "POST") {
        const kind = suffix.split("/")[1], key = req.headers()["idempotency-key"];
        const { expected_version, ...input } = body;
        const fingerprint = JSON.stringify([id, kind, input, handlerRevision]);
        const existing = jobs.get(jobKeys.get(key)) ?? [...jobs.values()].find(j => jobInputs.get(j.id) === fingerprint);
        if (existing) return reply(existing, 202);
        const job = { id: `job-${++nextJob}`, case_id: id, kind, state: "running", stage: "reading", attempts: 1,
          created_at: new Date().toISOString(), updated_at: new Date().toISOString(), result_version: null, result_url: null, error: null, can_retry: false, max_attempts: 3, base_version: saved.version, started_at: null, finished_at: null, next_attempt_at: null, heartbeat_at: null, lease_expires_at: null };
        jobs.set(job.id, job); jobKeys.set(key, job.id); jobInputs.set(job.id, fingerprint);
        if (ambiguousStart) { ambiguousStart = false; return reply({ detail: "fixture response lost after acceptance" }, 503); }
        return reply(job, 202);
      }
      if (/^\/jobs\/[^/]+\/retry$/.test(suffix) && method === "POST") {
        const job = jobs.get(suffix.split("/")[2]);
        if (retryChanged) return reply({ detail: "job handler revision changed" }, 409);
        if (!job?.can_retry) return reply({ detail: "job cannot be retried" }, 409);
        job.state = "queued"; job.stage = "queued"; job.error = null; job.can_retry = false;
        return reply(job, 202);
      }
      if (/^\/jobs\/[^/]+\/cancel$/.test(suffix) && method === "POST") {
        if (rejectCancel) return reply({ detail: "Synthetic cancellation unavailable" }, 503);
        const job = jobs.get(suffix.split("/")[2]); job.state = "cancelled"; job.can_retry = job.attempts < job.max_attempts;
        return reply(job);
      }
      if (suffix.startsWith("/jobs/") && method === "GET") return reply(jobs.get(suffix.split("/")[2]));
      return reply({ detail: "fixture route unavailable" }, 404);
    });
    const errors = [];
    const page = await context.newPage();
    page.on("pageerror", e => errors.push(e.message));
    async function ready() { await page.waitForFunction(() => !!window.caseStore && window.getAccountState().phase !== "probing"); }
    async function begin() { await page.evaluate(() => window.caseStore.beginEmpty("homebuilder")); await page.waitForFunction(() => window.caseStore.phase === "case"); }
    async function editOwner(value) { await page.evaluate(value => window.caseStore.dispatch({ type: "setDetail", field: "owner", section: "A", value }), value); }
    const save = () => page.evaluate(() => window.caseStore.saveDraft());
    const saved = () => page.waitForFunction(() => window.caseStore.readSync().saved);
    async function fresh() { await begin(); await editOwner("Synthetic owner"); return save(); }
    await page.goto(pathToFileURL(path).href); await ready();

    await t.test("the production composer saves an onboarded applicant's raw draft before Start without starting AI", async () => {
      await page.getByLabel("Describe your project", { exact: true }).fill("  Unstarted raw description with spaces  ");
      await saved();
      const id = await page.evaluate(() => window.caseStore.engineId);
      assert.ok(id); assert.equal(nextCase, 1);
      assert.equal(cases.get(id).applicant_draft.question_text["description-editor"].value, "  Unstarted raw description with spaces  ");
      assert.equal(jobs.size, 0);
      await page.reload(); await ready(); await page.evaluate(id => window.caseStore.openCase(id, "homebuilder"), id);
      assert.equal(await page.getByLabel("Describe your project", { exact: true }).inputValue(), "  Unstarted raw description with spaces  ");
    });

    await t.test("typed text is synchronously dirty; exact latest text/choices flush in one request without derived reloads", async () => {
      await editOwner("Original owner"); const id = await save(); assert.ok(id);
      requests.length = 0;
      await page.getByLabel("Unconfirmed owner").fill("Unfinished applicant text");
      assert.equal(await page.evaluate(() => window.caseStore.readSync().saved), false);
      await page.evaluate(() => window.updateSession({ skipped: ["field-date"], seen: ["section-d"], packages: { pack: "no" }, ruleUnsure: ["rule.input"], authorityUnsure: true }));
      await save();
      assert.equal(cases.get(id).applicant_draft.question_text["owner-editor"].value, "Unfinished applicant text");
      assert.deepEqual(cases.get(id).applicant_draft.packages, { pack: "no" });
      assert.equal(requests.filter(r => r.method === "PATCH" && r.url.endsWith("/draft")).length, 1);
      assert.equal(requests.some(r => /\/gaps|\/professional|\/section-d\/issues/.test(r.url)), false);
      const storage = await page.evaluate(() => Object.entries(sessionStorage));
      assert.equal(storage.some(([, value]) => /Unfinished|Original owner|question_text/.test(value)), false);
    });

    await t.test("an older acknowledgement cannot mark later typing Saved; the flush coalesces the latest revision", async () => {
      let release; const promise = new Promise(r => { release = r; }); held = { promise };
      await page.getByLabel("Unconfirmed owner").fill("Older in flight");
      await page.evaluate(() => { window.pendingSave = window.caseStore.saveDraft(); });
      await page.waitForFunction(() => window.caseStore.saveStatus === "saving");
      await page.getByLabel("Unconfirmed owner").fill("Newest typing while save waits");
      assert.equal(await page.evaluate(() => window.caseStore.readSync().saved), false);
      release(); const id = await page.evaluate(() => window.pendingSave); await saved();
      assert.equal(cases.get(id).applicant_draft.question_text["owner-editor"].value, "Newest typing while save waits");
    });

    await t.test("a failed flush keeps the active case and unfinished editors", async () => {
      const id = await page.evaluate(() => window.caseStore.engineId);
      rejectDraft = true; await page.getByLabel("Unconfirmed owner").fill("Keep on failure");
      assert.equal(await save(), null);
      const error = await page.evaluate(() => window.caseStore.openCase("case-unavailable", "homebuilder"));
      assert.match(error, /aren’t saved/);
      assert.equal(await page.evaluate(() => window.caseStore.engineId), id);
      assert.equal(await page.getByLabel("Unconfirmed owner").inputValue(), "Keep on failure");
      rejectDraft = false; await save();
    });

    await t.test("uploaded reading inputs survive refresh before AI starts and explicit removal stays removed", async () => {
      await page.evaluate(() => {
        window.caseStore.dispatch({ type: "addFiles", files: [{ id: "reading-input", name: "evidence.pdf" }] });
        window.updateSession({ held: [{ id: "reading-input", file: new File(["unit"], "evidence.pdf", { type: "application/pdf" }) }] });
      });
      const id = await save(); await saved();
      const fileId = cases.get(id).applicant_draft.intake_file_ids[0]; assert.ok(fileId);
      await page.reload(); await ready(); await page.evaluate(id => window.caseStore.openCase(id, "homebuilder"), id);
      assert.equal(await page.evaluate(() => window.caseStore.c.files[0].engineId), fileId);
      assert.equal(await page.evaluate(() => window.caseStore.c.files[0].name), "evidence.pdf");
      assert.equal(jobs.size, 0);
      await page.evaluate(() => window.caseStore.dispatch({ type: "removeFile", id: window.caseStore.c.files[0].id }));
      await save();
      await page.reload(); await ready(); await page.evaluate(id => window.caseStore.openCase(id, "homebuilder"), id);
      assert.equal(await page.evaluate(() => window.caseStore.c.files.length), 0);
      assert.deepEqual(cases.get(id).applicant_draft.intake_file_ids, []);
      assert.ok(uploads.has(fileId), "removal of a reading input does not delete stored supporting bytes");
    });

    await t.test("running intake releases the save queue; reload rejoins progress and draft/skip choices", async () => {
      await page.evaluate(() => window.caseStore.dispatch({ type: "setDescription", text: "Synthetic project description" }));
      await page.evaluate(() => window.caseStore.readDescription());
      const id = await page.evaluate(() => window.caseStore.engineId);
      assert.equal([...jobs.values()].filter(j => j.kind === "intake").length, 1);
      await page.getByLabel("Unconfirmed owner").fill("Typed during slow AI");
      await save(); assert.equal(cases.get(id).applicant_draft.question_text["owner-editor"].value, "Typed during slow AI");
      await page.reload(); await ready();
      assert.equal(await page.evaluate(id => window.caseStore.openCase(id, "homebuilder"), id), null);
      await page.waitForFunction(() => window.caseStore.reading.intakeJob?.state === "running");
      assert.equal(await page.getByLabel("Unconfirmed owner").inputValue(), "Typed during slow AI");
      assert.deepEqual(await page.evaluate(() => window.getSession().skipped), ["field-date"]);
      assert.deepEqual(await page.evaluate(() => window.getSession().packages), { pack: "no" });
      assert.equal([...jobs.values()].filter(j => j.kind === "intake").length, 1);
    });

    await t.test("unavailable workers are reported honestly while saves continue and refresh recovers availability", async () => {
      const id = await page.evaluate(() => window.caseStore.engineId);
      workerAvailable = false;
      await page.reload(); await ready(); await page.evaluate(id => window.caseStore.openCase(id, "homebuilder"), id);
      await page.waitForFunction(() => window.caseStore.reading.intakeNote.includes("Background processing is unavailable"));
      await page.getByLabel("Unconfirmed owner").fill("Still saved without a worker"); await save();
      assert.equal(cases.get(id).applicant_draft.question_text["owner-editor"].value, "Still saved without a worker");
      workerAvailable = true;
      await page.reload(); await ready(); await page.evaluate(id => window.caseStore.openCase(id, "homebuilder"), id);
      await page.waitForFunction(() => window.caseStore.reading.intakeJob?.state === "running" && window.caseStore.reading.intakeNote === "");
      assert.equal(await page.getByLabel("Unconfirmed owner").inputValue(), "Still saved without a worker");
    });

    await t.test("job output changing a saved base preserves raw text through application and reopen", async () => {
      const id = await page.evaluate(() => window.caseStore.engineId), remote = cases.get(id);
      const job = [...jobs.values()].find(j => j.case_id === id && j.kind === "intake");
      await page.getByLabel("Unconfirmed owner").fill("Raw text must survive a new base"); await save();
      remote.facts.push({ id: "job-owner", field: "owner_name", value: "Job supplied a changed base", status: "confirmed", kind: "pointed",
        source: { type: "user_text", ref: "intake:description", quote: "Job supplied a changed base" }, confidence: null, formula: null, inputs: [] });
      remote.version++; job.result_version = remote.version; job.state = "succeeded"; job.stage = "completed";
      await page.waitForFunction(() => window.caseStore.c.facts.some(f => f.id === "job-owner"));
      assert.equal(await page.getByLabel("Unconfirmed owner").inputValue(), "Raw text must survive a new base");
      assert.match(await page.getByLabel("Editor conflict").textContent(), /text retained/);
      await save(); await page.reload(); await ready();
      assert.equal(await page.evaluate(id => window.caseStore.openCase(id, "homebuilder"), id), null);
      assert.equal(await page.getByLabel("Unconfirmed owner").inputValue(), "Raw text must survive a new base");
      assert.match(await page.getByLabel("Editor conflict").textContent(), /text retained/);
    });

    await t.test("retry uses the failed identity's retry route without resetting its attempts", async () => {
      await page.evaluate(() => window.caseStore.runIdentify());
      const job = [...jobs.values()].filter(j => j.kind === "identify").at(-1);
      job.state = "failed"; job.can_retry = true; job.error = { code: "processing_failed", message: "Processing could not be completed.", stage: "reading", retryable: true };
      await page.waitForFunction(() => window.caseStore.reading.identify === "error");
      const starts = requests.filter(r => r.url.endsWith("/identify/jobs")).length;
      await page.evaluate(() => window.caseStore.runIdentify());
      await page.waitForFunction(() => window.caseStore.reading.identifyJob?.state === "queued");
      assert.equal(requests.filter(r => r.url.endsWith(`/jobs/${job.id}/retry`)).length, 1);
      assert.equal(requests.filter(r => r.url.endsWith("/identify/jobs")).length, starts);
      assert.equal(job.attempts, 1); assert.equal([...jobs.values()].filter(j => j.kind === "identify").length, 1);
    });

    await t.test("an exhausted identity stays bounded; changed description can enqueue a new job", async () => {
      const old = [...jobs.values()].filter(j => j.kind === "identify").at(-1);
      old.state = "failed"; old.attempts = old.max_attempts; old.can_retry = false;
      old.error = { code: "processing_failed", message: "Processing could not be completed.", stage: "reading", retryable: true };
      await page.waitForFunction(() => window.caseStore.reading.identify === "error");
      const before = requests.filter(r => r.url.endsWith("/identify/jobs")).length;
      await page.getByLabel("Unconfirmed owner").fill("Unconfirmed text alone creates no computation"); await save();
      assert.equal(requests.filter(r => r.url.endsWith("/identify/jobs")).length, before);
      assert.equal(await page.evaluate(() => window.caseStore.reading.identifyJob.can_retry), false);
      await page.evaluate(() => window.caseStore.dispatch({ type: "setDescription", text: "Changed substantive project description" }));
      await page.waitForFunction(() => !window.caseStore.reading.identifyJob);
      await page.evaluate(() => window.caseStore.runIdentify());
      const current = [...jobs.values()].filter(j => j.kind === "identify").at(-1);
      assert.notEqual(current.id, old.id); assert.equal(old.attempts, old.max_attempts);
      assert.equal(requests.filter(r => r.url.endsWith("/identify/jobs")).length, before + 1);
    });

    await t.test("a changed-handler retry gets a new logical key, retained when the acceptance response is lost", async () => {
      const old = [...jobs.values()].filter(j => j.kind === "identify").at(-1);
      old.state = "failed"; old.can_retry = true;
      old.error = { code: "processing_failed", message: "Processing could not be completed.", stage: "reading", retryable: true };
      await page.waitForFunction(() => window.caseStore.reading.identify === "error");
      const previousKey = requests.filter(r => r.url.endsWith("/identify/jobs")).at(-1).key;
      retryChanged = true; handlerRevision++; ambiguousStart = true;
      await page.evaluate(() => window.caseStore.runIdentify());
      const first = requests.filter(r => r.url.endsWith("/identify/jobs")).at(-1);
      assert.notEqual(first.key, previousKey);
      await page.evaluate(() => window.caseStore.runIdentify());
      const second = requests.filter(r => r.url.endsWith("/identify/jobs")).at(-1);
      assert.equal(second.key, first.key, "the same accepted logical submission keeps its HTTP retry identity");
      assert.notEqual([...jobs.values()].filter(j => j.kind === "identify").at(-1).id, old.id);
      assert.equal(old.attempts, 1);
      retryChanged = false;
    });

    await t.test("files remain unsaved during upload; a failed upload is retained and retried by the draft flush", async () => {
      let release; heldUpload = { promise: new Promise(resolve => { release = resolve; }) };
      await page.evaluate(() => { window.fileSave = window.caseStore.uploadEvidenceFile(new File(["unit"], "evidence.pdf", { type: "application/pdf" }), "task-file"); });
      assert.equal(await page.evaluate(() => window.caseStore.readSync().saved), false);
      assert.equal(await page.evaluate(() => { const event = new Event("beforeunload", { cancelable: true }); window.dispatchEvent(event); return event.defaultPrevented; }), true);
      release(); const uploaded = await page.evaluate(() => window.fileSave); await saved();
      const id = await page.evaluate(() => window.caseStore.engineId);
      assert.equal(cases.get(id).applicant_draft.evidence_drafts["task-file"].file_binding.file_id, uploaded.id);
      rejectUpload = true;
      const error = await page.evaluate(() => window.caseStore.uploadEvidenceFile(new File(["unit 2"], "evidence2.pdf", { type: "application/pdf" }), "task-retry").then(() => "", error => error.message));
      assert.ok(error); assert.equal(await page.evaluate(() => window.caseStore.readSync().saved), false);
      rejectUpload = false; await save(); await saved();
      assert.ok(cases.get(id).applicant_draft.evidence_drafts["task-retry"].file_binding.file_id);
    });

    await t.test("reload after persisted intake success resumes the downstream identify chain exactly once", async () => {
      await begin();
      await page.evaluate(() => window.caseStore.dispatch({ type: "setDescription", text: "Resume this saved pipeline" }));
      await page.evaluate(() => window.caseStore.readDescription());
      const id = await page.evaluate(() => window.caseStore.engineId), remote = cases.get(id);
      const job = [...jobs.values()].find(j => j.case_id === id && j.kind === "intake");
      remote.intake = { pointers: [], conflicts: [], plan: null, review: null, unresolved_citations: [], files: [], ran_at: new Date().toISOString(),
        text_sha256: createHash("sha256").update("Resume this saved pipeline").digest("hex"),
        model: { status: "off", model: null, reason: null, pointed: 0, proposed: 0, dropped: 0, input_tokens: 0, output_tokens: 0 } };
      remote.version++; job.result_version = remote.version; job.result_url = `/cases/${id}/intake`; job.state = "succeeded"; job.stage = "completed";
      await page.reload(); await ready(); await page.evaluate(id => window.caseStore.openCase(id, "homebuilder"), id);
      await page.waitForFunction(() => window.caseStore.reading.identifyJob?.state === "running");
      assert.equal([...jobs.values()].filter(j => j.case_id === id && j.kind === "intake").length, 1);
      assert.equal([...jobs.values()].filter(j => j.case_id === id && j.kind === "identify").length, 1);
    });

    await t.test("refresh rejoins a job from another device without a case version change", async () => {
      const id = await fresh(), version = cases.get(id).version, now = new Date().toISOString();
      const job = { id: `job-${++nextJob}`, case_id: id, kind: "intake", state: "running", stage: "reading", attempts: 1,
        created_at: now, updated_at: now, result_version: null, result_url: null, error: null, can_retry: false, max_attempts: 3,
        base_version: version, started_at: now, finished_at: null, next_attempt_at: null, heartbeat_at: now, lease_expires_at: null };
      jobs.set(job.id, job); requests.length = 0;
      assert.equal(await page.evaluate(() => window.caseStore.refreshCurrentCase()), null);
      assert.equal(await page.evaluate(() => window.caseStore.reading.intakeJob?.id), job.id);
      assert.equal(cases.get(id).version, version);
      assert.equal(requests.some(r => r.method === "GET" && r.url === `/cases/${id}/jobs`), true);
    });

    for (const kind of ["intake", "identify"]) await t.test(`${kind} accepts only acknowledged input after a held job-list read`, async () => {
      const id = await fresh();
      await page.getByLabel("Describe your project", { exact: true }).fill("Acknowledged earlier input"); await save();
      requests.length = 0;
      let release; heldJobs = { promise: new Promise(resolve => { release = resolve; }) };
      try {
        await page.evaluate(kind => { window.startRequest = kind === "intake" ? window.caseStore.readDescription() : window.caseStore.runIdentify(); }, kind);
        await page.waitForResponse(r => r.url().endsWith("/jobs"), { timeout: 50 }).catch(() => {});
        assert.ok(requests.some(r => r.method === "GET" && r.url.endsWith("/jobs")));
        await page.getByLabel("Describe your project", { exact: true }).fill("New raw input while the job list waits");
        release(); await page.evaluate(() => window.startRequest);
        const index = requests.findIndex(r => r.method === "POST" && r.url === `/cases/${id}/${kind}/jobs`), start = requests[index];
        assert.ok(start);
        const text = kind === "intake" ? start.body.text : start.body.prose;
        const before = requests.slice(0, index).filter(r => r.method === "PATCH" && r.url.endsWith("/draft")).at(-1);
        assert.equal(text, "New raw input while the job list waits");
        assert.equal(before?.body.applicant_draft.question_text["description-editor"].value, text,
          "the newer computation input needs a draft acknowledgement before acceptance");
        assert.equal(before.body.expected_version + 1, start.body.expected_version);
      } finally { release(); heldJobs = null; }
    });

    for (const kind of ["intake", "identify"]) await t.test(`${kind} Cancel shows a returned error and remains retryable through status polls`, async () => {
      await fresh();
      await page.evaluate(kind => kind === "intake" ? window.caseStore.readDescription() : window.caseStore.runIdentify(), kind);
      rejectCancel = true;
      try {
        const section = page.getByRole("region", { name: kind === "intake" ? "Reading progress" : "Code progress" });
        const response = page.waitForResponse(r => r.url().endsWith("/cancel"));
        await section.getByRole("button", { name: "Cancel", exact: true }).click(); await response;
        await page.waitForTimeout(30);
        assert.match(await section.innerText(), /could not.*cancel|cancellation unavailable/i);
        await page.waitForTimeout(1650);
        assert.match(await section.innerText(), /could not.*cancel|cancellation unavailable/i, "polling must retain the cancellation failure");
        rejectCancel = false;
        await section.getByRole("button", { name: "Cancel", exact: true }).click();
        await page.waitForFunction(kind => window.caseStore.reading[`${kind}Job`]?.state === "cancelled", kind);
      } finally { rejectCancel = false; }
    });

    await t.test("save conflict offers a review and preserves remote answers, local pending facts and both raw values until acknowledgement", async () => {
      const id = await fresh(), remote = cases.get(id);
      await page.getByLabel("Unconfirmed owner").fill("Baseline unfinished answer"); await save();
      const remoteOwner = { ...remote.facts.find(f => f.field === "owner"), id: "other-device-owner", value: "Other device owner" };
      remote.facts.push(remoteOwner);
      remote.facts.push({ ...remoteOwner, id: "other-device-mail", field: "mailingAddress", value: "Other device address" });
      remote.applicant_draft.question_text["owner-editor"] = { base: "Other device owner", value: "Other device unfinished text" };
      remote.applicant_draft.choices.remote = "saved choice";
      remote.version++;
      await editOwner("Local pending owner");
      await page.getByLabel("Unconfirmed owner").fill("  Local unfinished text  ");
      await page.evaluate(() => window.caseStore.dispatch({ type: "setDetail", section: "A", field: "representative", value: "Local pending representative" }));
      assert.equal(await save(), null);
      const patches = requests.filter(r => r.method === "PATCH").length;
      const reviewButton = page.getByRole("button", { name: "Review changes", exact: true });
      assert.equal(await reviewButton.count(), 1, "the save indicator needs a reachable conflict-recovery action");
      await reviewButton.click();
      const review = page.getByRole("dialog", { name: "Review saved changes" });
      await review.waitFor();
      assert.match(await review.innerText(), /Other device owner/);
      assert.match(await review.innerText(), /Local pending owner/);
      assert.match(await review.innerText(), /Other device unfinished text/);
      assert.match(await review.innerText(), /Local unfinished text/);
      assert.equal(requests.filter(r => r.method === "PATCH").length, patches, "opening review is read-only");
      assert.equal(await review.getByRole("button", { name: "Save reviewed changes", exact: true }).isDisabled(), true);
      await review.getByRole("group", { name: "Owner", exact: true }).getByRole("button", { name: "Use saved", exact: true }).click();
      await review.getByRole("group", { name: "Unfinished answer", exact: true }).getByRole("button", { name: "Keep mine", exact: true }).click();
      rejectDraft = true;
      await review.getByRole("button", { name: "Save reviewed changes", exact: true }).click();
      await page.waitForFunction(() => window.caseStore.saveStatus === "failed");
      assert.equal(await page.getByLabel("Unconfirmed owner").inputValue(), "  Local unfinished text  ");
      assert.equal(await page.evaluate(() => window.caseStore.c.facts.find(f => f.field === "owner").value), "Local pending owner");
      assert.equal(remote.facts.filter(f => f.field === "owner").at(-1).value, "Other device owner");
      rejectDraft = false;
      await review.getByRole("button", { name: "Save reviewed changes", exact: true }).click(); await saved();
      assert.equal(remote.facts.filter(f => f.field === "owner").at(-1).value, "Other device owner");
      assert.equal(remote.facts.filter(f => f.field === "mailingAddress").at(-1).value, "Other device address");
      assert.equal(remote.facts.filter(f => f.field === "representative").at(-1).value, "Local pending representative");
      assert.equal(remote.applicant_draft.question_text["owner-editor"].value, "  Local unfinished text  ");
      assert.equal(remote.applicant_draft.choices.remote, "saved choice");
      assert.equal(await page.getByLabel("Unconfirmed owner").inputValue(), "  Local unfinished text  ");
      await page.reload(); await ready(); await page.evaluate(id => window.caseStore.openCase(id, "homebuilder"), id);
      assert.equal(await page.getByLabel("Unconfirmed owner").inputValue(), "  Local unfinished text  ");
    });

    await t.test("a job that finishes while editing is paused is applied when editing resumes, not dropped", async () => {
      await begin();
      await page.evaluate(() => window.caseStore.dispatch({ type: "setDescription", text: "Finish while paused" }));
      await page.evaluate(() => window.caseStore.readDescription());
      await page.waitForFunction(() => window.caseStore.reading.intakeJob?.state === "running");
      const id = await page.evaluate(() => window.caseStore.engineId), remote = cases.get(id);
      const job = [...jobs.values()].filter(j => j.case_id === id && j.kind === "intake").at(-1);
      await page.evaluate(() => { window.resumeEdits = window.pauseApplicationEdits(); });
      try {
        remote.facts.push({ id: "paused-job-fact", field: "owner_name", value: "Applied after the pause", status: "confirmed", kind: "pointed",
          source: { type: "user_text", ref: "intake:description", quote: "Applied after the pause" }, confidence: null, formula: null, inputs: [] });
        remote.version++; job.result_version = remote.version; job.state = "succeeded"; job.stage = "completed";
        await page.waitForFunction(() => window.caseStore.reading.intakeJob?.state === "succeeded");
        await page.waitForTimeout(200);
        assert.equal(await page.evaluate(() => window.caseStore.c.facts.some(f => f.id === "paused-job-fact")), false, "output waits for the pause");
      } finally { await page.evaluate(() => window.resumeEdits()); }
      await page.waitForFunction(() => window.caseStore.c.facts.some(f => f.id === "paused-job-fact"));
    });

    await t.test("an account change while editing is paused still clears the previous applicant's visit", async () => {
      await fresh();
      await page.getByLabel("Unconfirmed owner").fill("Private to the first account"); await save();
      await page.evaluate(() => window.updateSession({ skipped: ["first-account-skip"] }));
      const user = await page.evaluate(() => window.getAccountState().user);
      await page.evaluate(() => { window.resumeEdits = window.pauseApplicationEdits(); });
      try {
        await page.evaluate(user => window.setAccountState({ user: { ...user, id: "second-account" } }), user);
        await page.waitForFunction(() => window.caseStore.phase === "who" && window.caseStore.engineId === null);
        assert.equal(await page.evaluate(() => window.caseStore.c.facts.length), 0);
        assert.deepEqual(await page.evaluate(() => window.getSession().skipped), []);
        assert.equal(await page.getByLabel("Unconfirmed owner").inputValue(), "");
      } finally { await page.evaluate(() => window.resumeEdits()); }
      await page.evaluate(user => window.setAccountState({ user }), user);
      await page.waitForFunction(() => window.getAccountState().user?.id === "durability-owner");
    });

    await t.test("logout freezes DOM, dispatch, raw-editor and session callbacks through HTTP failure then restores editing", async () => {
      const id = await fresh();
      await page.getByLabel("Unconfirmed owner").fill("Text accepted before logout");
      let release; heldLogout = { promise: new Promise(resolve => { release = resolve; }) }; rejectLogout = true;
      try {
        await page.evaluate(() => { window.logoutRequest = window.signOut(); });
        await page.waitForFunction(() => window.signOutStatus().pending);
        for (let i = 0; i < 100 && !requests.some(r => r.url === "/auth/logout"); i++) await page.waitForTimeout(10);
        assert.ok(requests.some(r => r.url === "/auth/logout"));
        assert.equal(await page.getByLabel("Describe your project", { exact: true }).isEditable(), false);
        assert.equal(await page.getByLabel("Unconfirmed owner").isDisabled(), true);
        const before = await page.evaluate(() => ({ owner: window.caseStore.c.facts.find(f => f.field === "owner").value,
          session: window.getSession(), scope: window.questionDrafts.scope(JSON.stringify([window.getAccountState().user.id, "applicant", null]), 0, window.caseStore.engineId) }));
        await page.evaluate(scope => {
          window.caseStore.dispatch({ type: "setDetail", section: "A", field: "owner", value: "Late discarded dispatch" });
          window.questionDrafts.write(scope, "owner-editor", "Synthetic owner", "Late discarded text");
          window.questionDrafts.writeChoices(scope, { late: "discarded" });
          window.updateSession({ skipped: ["late-skip"], packages: { late: "yes" } });
        }, before.scope);
        assert.equal(await page.evaluate(() => window.caseStore.c.facts.find(f => f.field === "owner").value), before.owner);
        assert.equal(await page.getByLabel("Unconfirmed owner").inputValue(), "Text accepted before logout");
        assert.deepEqual(await page.evaluate(() => window.getSession()), before.session);
        assert.equal(cases.get(id).applicant_draft.question_text["owner-editor"].value, "Text accepted before logout");
        release(); assert.equal(await page.evaluate(() => window.logoutRequest), false);
        assert.equal(await page.getByLabel("Unconfirmed owner").isEnabled(), true);
        await page.getByLabel("Unconfirmed owner").fill("Editing restored after logout failed"); await save();
        assert.equal(cases.get(id).applicant_draft.question_text["owner-editor"].value, "Editing restored after logout failed");
      } finally { release(); await page.evaluate(() => window.logoutRequest); heldLogout = null; rejectLogout = false; }
    });

    await t.test("dirty Sign out failure keeps the account and text; success flushes before logout and clears private state", async () => {
      requests.length = 0;
      await page.getByLabel("Unconfirmed owner").fill("Do not lose this on sign out");
      rejectDraft = true;
      assert.equal(await page.evaluate(() => window.signOut()), false);
      assert.equal(loggedOut, false);
      assert.equal(await page.evaluate(() => window.getAccountState().phase), "signed-in");
      assert.equal(await page.getByLabel("Unconfirmed owner").inputValue(), "Do not lose this on sign out");
      assert.match(await page.evaluate(() => window.signOutStatus().error), /aren’t saved/);
      rejectDraft = false;
      const id = await page.evaluate(() => window.caseStore.engineId);
      await page.getByLabel("Unconfirmed owner").fill("Latest successful sign out text");
      await Promise.all([page.waitForNavigation(), page.evaluate(() => { void window.signOut(); })]); await ready();
      assert.equal(loggedOut, true); assert.equal(cases.get(id).applicant_draft.question_text["owner-editor"].value, "Latest successful sign out text");
      assert.equal(await page.evaluate(() => window.getAccountState().phase), "signed-out");
      assert.equal(await page.getByLabel("Unconfirmed owner").inputValue(), "");
      assert.equal(await page.evaluate(() => Object.values(sessionStorage).some(value => /Latest successful|Do not lose/.test(value))), false);
      const logout = requests.findIndex(r => r.url === "/auth/logout");
      assert.ok(requests.slice(0, logout).some(r => r.method === "PATCH" && r.body?.applicant_draft?.question_text?.["owner-editor"]?.value === "Latest successful sign out text"));
    });
    assert.deepEqual(errors, []);
    await context.close();
  } finally { await browser.close(); }
});
