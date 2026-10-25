/**
 * Drives the built app (dist/main/main.js) inside Electron with a throwaway data directory.
 * No debugging port or listener: pages are read and clicked through executeJavaScript and captured
 * with capturePage. Usage: electron scripts/smoke.cjs <output-dir>
 */
const { app, BrowserWindow } = require("electron");
const { mkdtempSync, mkdirSync, writeFileSync } = require("node:fs");
const { tmpdir } = require("node:os");
const { join, resolve } = require("node:path");

const out = resolve(process.argv[process.argv.length - 1] ?? "smoke-out");
mkdirSync(out, { recursive: true });
const userData = mkdtempSync(join(tmpdir(), "batatis-smoke-"));
app.setPath("userData", userData);

const report = { userData, steps: [], csp: [], errors: [] };
const windows = [];
app.on("browser-window-created", (_event, window) => {
  windows.push(window);
  window.webContents.on("console-message", (event) => {
    const text = event.message ?? "";
    if (/Content Security Policy|Refused to/.test(text)) report.csp.push(text.slice(0, 300));
    if (event.level === "error") report.errors.push(text.slice(0, 300));
  });
});

require("../dist/main/main.js");

const sleep = (ms) => new Promise((done) => setTimeout(done, ms));
const live = () => windows.filter((w) => !w.isDestroyed() && w.webContents.getURL().startsWith("batatis://app/")).at(-1);

async function until(predicate, label, timeout = 30000) {
  const deadline = Date.now() + timeout;
  for (;;) {
    try {
      const value = await predicate();
      if (value) return value;
    } catch {
      /* page reloading */
    }
    if (Date.now() > deadline) throw new Error(`timed out: ${label}`);
    await sleep(150);
  }
}

const page = (script) => live().webContents.executeJavaScript(script, true);
const text = () => page("document.body.innerText");

async function capture(name, note) {
  await sleep(700);
  const image = await live().webContents.capturePage();
  writeFileSync(join(out, `${name}.png`), image.toPNG());
  report.steps.push({ name, note, url: live().webContents.getURL(), text: (await text()).slice(0, 400) });
}

async function click(label) {
  const done = await page(`(() => {
    const target = [...document.querySelectorAll('button, a, [role^=menuitem]')].find((el) => el.textContent.trim() === ${JSON.stringify(label)} || el.getAttribute('aria-label') === ${JSON.stringify(label)});
    if (!target) return false;
    target.click();
    return true;
  })()`);
  if (!done) throw new Error(`no control labelled ${label}`);
}

async function run() {
  await until(() => live(), "first window");
  await until(async () => /Sign in|Create/.test(await text()), "local sign-in page");
  await capture("1-local-signin", "Normal workspace, nobody signed in yet: the existing sign-in page");

  const before = live();
  await page("window.batatisDesktop.switchWorkspace('dev')");
  await until(async () => live() !== before && (await text()).length > 40, "dev window");
  await capture("2-dev-applicant-home", "Local development, signed in as the seeded test applicant");

  await page("location.hash = '#/settings'");
  await until(async () => /Workspace/.test(await text()) && /AI connections/.test(await text()), "settings");
  await capture("3-dev-settings", "Settings: workspace, person, AI connections, code database");

  await click("Account: Test applicant");
  await until(async () => /Local development/.test(await text()), "account menu");
  await capture("4-dev-account-menu", "Quick switch in the account menu");

  const applicantWindow = live();
  await click("Reviewer · Calgary");
  await until(async () => live() !== applicantWindow && /review/i.test(live().webContents.getURL()), "reviewer window");
  await until(async () => (await text()).length > 40, "reviewer page");
  await capture("5-dev-reviewer-queue", "After the switch: a fresh window opens the Calgary reviewer's queue, no case claimed");

  const info = await page("window.batatisDesktop.info()");
  report.info = info;
}

app.whenReady().then(async () => {
  try {
    await run();
  } catch (error) {
    report.failure = String(error && error.stack || error);
    try { await capture("x-failure", "state at failure"); } catch { /* window gone */ }
  }
  writeFileSync(join(out, "report.json"), JSON.stringify(report, null, 2));
  app.quit();
});
