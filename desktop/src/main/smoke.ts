import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { isAbsolute, join, resolve } from "node:path";
import { app, type BrowserWindow } from "electron";
import type { DesktopHost } from "./controller";
import type { Engine } from "./engine";
import type { workflowFixture } from "./workflow-fixture";

export interface SmokeOptions {
  output: string;
  userData: string;
  stage: 1 | 2;
}

export function smokeOptions(): SmokeOptions | null {
  const output = process.env.BATATIS_DESKTOP_SMOKE_DIR;
  if (!process.argv.includes("--batatis-smoke-test") || !output) return null;
  assert.ok(isAbsolute(output), "smoke output is an absolute prepared directory");
  const stage = process.env.BATATIS_DESKTOP_SMOKE_STAGE;
  assert.ok(stage === "1" || stage === "2", "smoke stage is 1 or 2");
  return { output: resolve(output), userData: join(resolve(output), "workspace données 100% #"), stage: stage === "1" ? 1 : 2 };
}

export function monitorSmoke(options: SmokeOptions | null) {
  const csp: string[] = [];
  const errors: string[] = [];
  if (options) app.on("browser-window-created", (_event, window) => {
    window.webContents.on("console-message", (event) => {
      if (/Content Security Policy|Refused to/.test(event.message)) csp.push(event.message.slice(0, 500));
      if (event.level === "error") errors.push(event.message.slice(0, 500));
    });
  });
  return { csp, errors };
}

interface SmokeDeps {
  options: SmokeOptions;
  host: DesktopHost;
  current(): BrowserWindow | null;
  engines: Engine[];
  monitor: ReturnType<typeof monitorSmoke>;
  fixture?: ReturnType<typeof workflowFixture>;
  runtime(): Promise<{ executable: string; sha256: string }>;
}

const sleep = (ms: number) => new Promise((done) => setTimeout(done, ms));

async function until<T>(read: () => Promise<T> | T, label: string, timeout = 45_000): Promise<NonNullable<T>> {
  const deadline = Date.now() + timeout;
  for (;;) {
    try {
      const result = await read();
      if (result) return result;
    } catch {
      // Replacing a renderer rejects its pending evaluation.
    }
    if (Date.now() >= deadline) throw new Error(`Timed out waiting for ${label}`);
    await sleep(100);
  }
}

function record(value: unknown): Record<string, unknown> {
  assert.ok(typeof value === "object" && value !== null && !Array.isArray(value), "expected an object");
  return Object.fromEntries(Object.entries(value));
}

function string(value: unknown): string {
  assert.equal(typeof value, "string");
  return String(value);
}

export async function runSmoke(deps: SmokeDeps): Promise<void> {
  const { host, options, engines, monitor } = deps;
  const steps: { name: string; note: string }[] = [];
  const scenario = record(JSON.parse(readFileSync(join(options.output, "scenario.json"), "utf8")));
  const expectedApplicant = string(scenario.applicantId);
  const reviewCase = string(scenario.reviewCase);
  const report: Record<string, unknown> = { packaged: app.isPackaged, platform: process.platform, arch: process.arch, stage: options.stage, steps,
    inference: "Offline workflow fixture only. No provider status, authentication, entitlement or inference is checked.", fixture: deps.fixture, ...monitor };
  const window = () => {
    const value = deps.current();
    assert.ok(value && !value.isDestroyed(), "current app window exists");
    return value;
  };
  const page = (script: string): Promise<unknown> => window().webContents.executeJavaScript(script, true);
  const text = async () => string(await page("document.body.innerText"));
  const api = async (path: string, method = "GET", body?: unknown) => {
    const raw = await page(`(async () => {
      const response = await fetch(${JSON.stringify(`/api${path}`)}, {
        method: ${JSON.stringify(method)},
        ${body === undefined ? "" : `headers: {'content-type':'application/json'}, body: ${JSON.stringify(JSON.stringify(body))},`}
      });
      const text = await response.text();
      return {status: response.status, body: text ? JSON.parse(text) : null, cookie: response.headers.get('set-cookie')};
    })()`);
    const result = record(raw);
    assert.equal(result.cookie, null, "the renderer never sees session cookies");
    return result;
  };
  const json = async (path: string, method = "GET", body?: unknown, status = 200) => {
    const reply = await api(path, method, body);
    assert.equal(reply.status, status, JSON.stringify(reply));
    return record(reply.body);
  };
  const capture = async (name: string, note: string) => {
    await sleep(250);
    writeFileSync(join(options.output, `${options.stage}-${name}.png`), (await window().webContents.capturePage()).toPNG());
    steps.push({ name, note });
  };
  const replaced = async (action: () => Promise<unknown>) => {
    const previous = window();
    const pending = action();
    await pending.catch(() => undefined);
    await until(async () => deps.current() !== previous && /batatis:\/\/app\//.test(window().webContents.getURL())
      && !window().webContents.isLoading() && (await text()).trim().length > 20, "fresh app window");
    await until(() => previous.isDestroyed(), "old window destroyed");
  };
  const click = async (label: string) => {
    const found = await page(`(() => {
      const el = [...document.querySelectorAll('button, a, [role^=menuitem]')].find(el =>
        el.textContent.trim() === ${JSON.stringify(label)} || el.getAttribute('aria-label') === ${JSON.stringify(label)});
      if (!el) return false;
      el.click(); return true;
    })()`);
    assert.equal(found, true, `control exists: ${label}`);
  };
  const person = async (label: string) => {
    await until(async () => /Account:/.test(string(await page("[...document.querySelectorAll('[aria-label]')].map(e => e.getAttribute('aria-label')).join('|')"))), "account control");
    await click(`Account: ${host.info().person?.name}`);
    await replaced(() => click(label));
  };
  const me = async () => record((await json("/auth/me")).user);

  try {
    await until(async () => deps.current() && !window().webContents.isLoading() && (await text()).length > 20, "loaded canonical UI");
    assert.equal(app.isPackaged, true, "acceptance requires the packaged executable");
    assert.equal(deps.fixture?.adapterConstructed, true, "the bundled adapter factory was constructed without account access");
    report.codexRuntime = await deps.runtime();
    assert.match(process.execPath, /Application composée 100% #/, "the packaged executable runs from a URI-sensitive path");
    assert.equal(await page("typeof require"), "undefined", "Node is absent from the renderer");
    assert.equal(await page("typeof process"), "undefined", "Node process is absent from the renderer");
    assert.equal(await page("document.cookie"), "", "cookies remain host-owned");
    assert.ok(host.info().service.state === "ready", JSON.stringify(host.info()));

    if (options.stage === 1) {
      assert.equal(host.info().workspace, "local");
      assert.equal((await api("/auth/me")).status, 401);
      await capture("local-signin", "Canonical hosted UI in the separate local workspace.");
      await replaced(() => host.addCodeDb(string(scenario.codeDb)));
      assert.equal(host.info().codeDb.available, true, "the test deliberately imported a CodeDB; none was bundled");
      await until(async () => /Local development/.test(await text()), "visible first-use workspace entry");
      await replaced(() => click("Local development"));
      const applicant = await me();
      assert.equal(applicant.id, expectedApplicant);
      assert.equal(applicant.role, "applicant");
      report.applicantId = applicant.id;
      await capture("dev-applicant", "Distinct seeded applicant, no manually created account.");
      const forbidden = await api("/auth/onboarding", "POST", { role: "reviewer", authority: "calgary" });
      assert.equal(forbidden.status, 403);

      const created = await json("/cases", "POST", { title: "SYNTHETIC plan données 100% #" }, 201);
      const caseId = string(created.id);
      const binary = readFileSync(join(options.output, string(scenario.pdfFile)));
      assert.ok(binary.length > 256 * 1024, "the binary attachment spans bridge frames");
      const uploaded = record(await page(`(async () => {
        const pdf = Uint8Array.from(atob(${JSON.stringify(binary.toString("base64"))}), c => c.charCodeAt(0));
        const form = new FormData(); form.append('file', new File([pdf], 'plan données 100% #.pdf', {type:'application/pdf'}));
        const response = await fetch(${JSON.stringify(`/api/cases/${caseId}/files`)}, {method:'POST', body:form});
        return {status:response.status, file:await response.json()};
      })()`));
      assert.equal(uploaded.status, 201, JSON.stringify(uploaded));
      const file = record(uploaded.file);
      assert.equal(file.name, "plan données 100% #.pdf");
      const fileId = string(file.id);
      const download = record(await page(`(async () => {
        const response = await fetch(${JSON.stringify(`/api/cases/${caseId}/files/${fileId}`)});
        const bytes = new Uint8Array(await response.arrayBuffer());
        const digest = [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(b => b.toString(16).padStart(2,'0')).join('');
        return {status:response.status, size:bytes.length, digest};
      })()`));
      assert.equal(download.status, 200);
      assert.equal(download.size, binary.length);
      assert.equal(download.digest, createHash("sha256").update(binary).digest("hex"));
      assert.equal(download.digest, scenario.pdfSha256);
      steps.push({ name: "binary-upload-download", note: `${binary.length} exact bytes and the Unicode filename survived multipart, private pipes and download.` });

      const beforeRead = await json(`/cases/${caseId}`);
      const intake = await json(`/cases/${caseId}/intake`, "POST", { file_ids: [fileId], model: false, expected_version: beforeRead.version });
      const intakeRecord = record(intake.record);
      assert.ok(Array.isArray(intakeRecord.files));
      const read = intakeRecord.files.map(record).find((item) => item.file_id === fileId);
      assert.ok(read, "the bundled PDF reader returned the selected file");
      assert.equal(read.status, "read");
      assert.deepEqual(read.pages_read, [1]);
      assert.equal(record(intakeRecord.model).status, "off", "PDF extraction made no provider call");
      steps.push({ name: "pdf-read", note: "The bundled PDF reader extracted the selected attachment's first page with the model explicitly off." });

      const preview = await json(`/cases/${caseId}/export/preview`);
      assert.equal(preview.kind, "pages");
      assert.ok(Array.isArray(preview.pages) && preview.pages.length > 0, "bundled PDFium rendered exported pages");
      const first = record(preview.pages[0]);
      const image = string(first.image);
      writeFileSync(join(options.output, "export-preview-page.png"), Buffer.from(image.split(",")[1], "base64"));
      const pdf = record(await page(`(async () => {
        const r = await fetch(${JSON.stringify(`/api/cases/${caseId}/export`)}, {method:'POST',headers:{'content-type':'application/json'},body:'{"draft":true}'});
        const data = new Uint8Array(await r.arrayBuffer());
        return {status:r.status, type:r.headers.get('content-type'), prefix:new TextDecoder().decode(data.slice(0,5)), size:data.length};
      })()`));
      assert.equal(pdf.status, 200, JSON.stringify(pdf));
      assert.equal(pdf.prefix, "%PDF-");
      assert.equal(pdf.type, "application/pdf");
      steps.push({ name: "pdf-preview-export", note: "The packaged engine exported a draft and PDFium rendered its real PDF bytes." });
      const incomplete = await json(`/cases/${caseId}`);
      const blocked = await api(`/cases/${caseId}/submit`, "POST", { expected_version: incomplete.version });
      assert.equal(blocked.status, 409, "an incomplete draft is still blocked");
      assert.match(JSON.stringify(blocked.body), /Resolve blocking administrative gaps/, "the normal completeness gate owns the refusal");

      await page("location.hash = '#/settings'");
      await until(async () => /Workspace/.test(await text()) && /AI connections/.test(await text()), "desktop settings");
      await until(async () => /ChatGPT/.test(await text()), "explicit generation choices");
      await replaced(() => click("ChatGPT"));
      assert.equal(host.configuration().generation, "chatgpt");
      const fixtureBefore = await json(`/cases/${caseId}`);
      const fixtureIntake = await json(`/cases/${caseId}/intake`, "POST", {
        text: "SYNTHETIC offline workflow. We propose a cladding alternative with no supporting test report.",
        file_ids: [fileId], model: true, expected_version: fixtureBefore.version,
      });
      const fixtureRecord = record(fixtureIntake.record);
      assert.equal(record(fixtureRecord.model).input_tokens, null, "unreported fixture token usage stays unknown");
      assert.equal(record(fixtureRecord.review).input_tokens, null);
      const assisted = await json("/assist", "POST", { case_id: caseId, screen: "describe", question: "What information should a supporting report identify?" });
      assert.match(string(assisted.answer), /Offline workflow fixture/);
      assert.ok(deps.fixture.calls.some((call) => call.task === "intake"));
      assert.ok(deps.fixture.calls.some((call) => call.task === "document-review"));
      assert.ok(deps.fixture.calls.some((call) => call.task === "assistant"));
      const fixtureCount = deps.fixture.calls.length;
      await replaced(() => click("Off"));
      const offBefore = await json(`/cases/${caseId}`);
      const off = await json(`/cases/${caseId}/intake`, "POST", { text: "SYNTHETIC offline model-off check.", file_ids: [fileId], model: true, expected_version: offBefore.version });
      assert.equal(record(record(off.record).model).status, "off");
      assert.equal(deps.fixture.calls.length, fixtureCount, "Off makes no generation or screening dispatch");
      steps.push({ name: "selected-workflows", note: "Visible settings selected subscription generation, actual engine intake/document-review/assistant used the offline host fixture, usage stayed null, then Off made no dispatch. No account was checked." });
      await click("Applicant");
      await sleep(50);
      await replaced(() => click("Reviewer · Calgary"));
      assert.equal((await me()).authority, "calgary", "choosing the already selected person never locks the next switch");
      await person("Applicant");
      await page("location.hash = '#/settings'");
      await until(async () => /Workspace/.test(await text()) && /AI connections/.test(await text()), "desktop settings after no-op switch");
      await capture("settings", "Workspace, seeded people, truthful unavailable connection and stored-key controls.");
      const prepared = await json(`/cases/${reviewCase}`);
      const submitted = await json(`/cases/${reviewCase}/submit`, "POST", { expected_version: prepared.version });
      assert.equal(submitted.status, "submitted", "a complete synthetic fixture follows the normal submit gate");
      await person("Reviewer · Calgary");
      const calgary = await me();
      assert.notEqual(calgary.id, applicant.id);
      assert.equal(calgary.authority, "calgary");
      assert.deepEqual((await json("/review/queue")).applications, []);
      assert.equal((await api(`/cases/${reviewCase}`)).status, 404, "another authority cannot read the submission");
      await person("Reviewer · Edmonton");
      const edmonton = await me();
      assert.notEqual(edmonton.id, applicant.id);
      const queue = await json("/review/queue");
      assert.ok(Array.isArray(queue.applications));
      const queued = queue.applications.map(record).find((row) => row.id === reviewCase);
      assert.ok(queued, "the same database delivers the applicant's submission to its authority");
      assert.equal(queued.claim, null, "opening the reviewer queue never claims a case");
      await capture("reviewer-queue", "Edmonton sees the submitted fixture, with no automatic claim.");
      const claim = await json(`/review/${reviewCase}/claim`, "POST", {});
      assert.equal(record(claim.claim).reviewer_id, edmonton.id);
      const version = (await json(`/cases/${reviewCase}`)).version;
      const returned = await json(`/review/${reviewCase}/decision`, "POST", {
        outcome: "return", message: "SYNTHETIC native review message", items: [{ field: "mailing_address", note: "SYNTHETIC missing unit" }], expected_version: version,
      });
      assert.equal(returned.status, "returned");
      await person("Applicant");
      assert.equal((await me()).id, expectedApplicant);
      const messages = await json(`/cases/${reviewCase}/messages`);
      assert.equal(record(messages.decision).outcome, "return");
      assert.equal((await api(`/review/${reviewCase}/claim`, "POST", {})).status, 404);
      await replaced(() => page("window.batatisDesktop.restart()"));
      assert.equal((await json(`/cases/${caseId}`)).title, created.title);
      writeFileSync(join(options.output, "persisted.json"), JSON.stringify({ caseId, fileId, title: created.title }));
      await capture("saved-restart", "The same applicant and saved application survived an engine restart.");
    } else {
      const previous = record(JSON.parse(readFileSync(join(options.output, "persisted.json"), "utf8")));
      assert.equal(host.info().workspace, "dev");
      const applicant = await me();
      assert.equal(applicant.id, expectedApplicant);
      report.applicantId = applicant.id;
      const caseId = string(previous.caseId);
      assert.equal((await json(`/cases/${caseId}`)).title, previous.title);
      const files = await json(`/cases/${caseId}/files`);
      assert.ok(Array.isArray(files.items) && files.items.some((item) => record(item).id === previous.fileId));
      assert.equal((await json(`/cases/${reviewCase}`)).status, "returned");
      const deleted = await api(`/cases/${caseId}`, "DELETE");
      assert.equal(deleted.status, 204);
      assert.equal(deleted.body, null);
      assert.equal((await api(`/cases/${caseId}`)).status, 404);
      await capture("app-reopened", "A new packaged-app process restored the same principal, attachment and review state; 204 deletion worked.");
    }
    assert.deepEqual(monitor.csp, []);
    assert.deepEqual(monitor.errors, []);
    report.ok = true;
  } catch (error) {
    report.ok = false;
    report.failure = error instanceof Error ? error.stack : String(error);
    try { await capture("failure", "The actual state when native acceptance failed."); } catch { /* App window may have closed. */ }
  } finally {
    await host.dispose();
    report.enginePids = engines.map((engine) => engine.pid);
    report.engineExitCodes = await Promise.all(engines.map((engine) => engine.exited));
    writeFileSync(join(options.output, `report-${options.stage}.json`), JSON.stringify(report, null, 2));
    app.exit(report.ok === true ? 0 : 1);
  }
}
