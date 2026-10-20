/**
 * Walkthrough steps for the Batatis demo recording.
 *
 * Ids, titles, and primary routes match the shot list in docs/demo/script.md
 * (the demo-script change). `./scripts/record-demo.sh --check-script` diffs
 * this list against that file when it is on the branch.
 *
 * A step whose screen is missing is skipped and logged. The runner does not
 * invent article numbers, listings, test results, or professional opinions.
 * It does not click "Try an example" and it does not open the accuracy page.
 */
import { existsSync } from "node:fs";
import { join } from "node:path";

const CASE_PDF = {
  A: "evals/demo-cases/a-manufacturer-nailbase-sheathing/input/project-brief.pdf",
  B: "evals/demo-cases/b-contractor-firestop-nonconformance/input/project-brief.pdf",
  C: "evals/demo-cases/c-homebuilder-infill-house/input/project-brief.pdf",
};

const CASES = {
  A: {
    role: "Manufacturer",
    authority: "Edmonton",
    pdf: "A",
    lower: "EXAMPLE DATA · Case A · Manufacturer",
    text: "We make EPW NailBase CI-50, a 50 mm insulating sheathing panel, and we want it approved across Alberta so builders can nail vinyl siding straight into the facer. One pilot house: 0000 Example Way NW, Edmonton. Owner not decided. No legal description. No permit yet.",
  },
  B: {
    role: "General contractor",
    authority: "Calgary",
    pdf: "B",
    lower: "EXAMPLE DATA · Case B · General contractor",
    text: "Firestop inspection failed 46 plastic pipe penetrations on levels 3 and 4 at Example Commons, 0000 Example Avenue SW, Calgary. Five-storey sprinklered building, permit already issued. Drywall close-in is in 9 days. Can we get a variance and keep going?",
  },
  C: {
    role: "Homebuilder",
    authority: "Edmonton",
    pdf: "C",
    lower: "EXAMPLE DATA · Case C · Homebuilder",
    text: "Two-storey infill at 0000 Example Crescent NW, Edmonton, about 210 m², no sprinklers. Heated slab with R-7.5 under it. Unvented low-slope roof, spray foam thickness still TBD. Bedroom 3 window clear opening 400 mm by 780 mm. What needs a variance?",
  },
};

const ALL_LOWER = `${CASES.A.lower}\n${CASES.B.lower}\n${CASES.C.lower}`;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function skipped(reason) {
  return { status: "skipped", reason };
}

function recorded() {
  return { status: "recorded" };
}

function escapeReg(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function slug(title) {
  return title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 48);
}

async function visible(locator, timeout = 1000) {
  try {
    await locator.first().waitFor({ state: "visible", timeout });
    return true;
  } catch {
    return false;
  }
}

function h1(page, name) {
  return page.getByRole("heading", { level: 1, name }).first();
}

function describeHeading(page) {
  return h1(page, /What are you building\?|Describe your idea/);
}

function navLink(page, name) {
  return page.getByRole("navigation", { name: "Main" }).getByRole("link", { name });
}

function roleButton(page, label) {
  return page.getByRole("button", { name: new RegExp(`^${escapeReg(label)}(?!\\s*·)`) }).first();
}

async function overlay(page, { caption, lower }) {
  await page.evaluate(
    ({ caption, lower }) => {
      const ensure = (id, style) => {
        let el = document.getElementById(id);
        if (!el) {
          el = document.createElement("div");
          el.id = id;
          el.setAttribute("data-demo-recorder", "true");
          Object.assign(el.style, style);
          document.body.appendChild(el);
        }
        return el;
      };
      const cap = ensure("demo-recorder-caption", {
        position: "fixed",
        top: "12px",
        right: "16px",
        zIndex: "10000",
        background: "rgba(20,20,20,0.88)",
        color: "#f4f4f5",
        font: "600 13px/1.3 ui-sans-serif, system-ui, sans-serif",
        padding: "6px 10px",
        borderRadius: "6px",
        pointerEvents: "none",
      });
      cap.textContent = caption || "";
      cap.style.display = caption ? "block" : "none";
      const low = ensure("demo-recorder-lower", {
        position: "fixed",
        left: "16px",
        bottom: "16px",
        zIndex: "10000",
        background: "rgba(20,20,20,0.88)",
        color: "#f4f4f5",
        font: "500 13px/1.45 ui-sans-serif, system-ui, sans-serif",
        padding: "8px 12px",
        borderRadius: "6px",
        pointerEvents: "none",
        whiteSpace: "pre",
        maxWidth: "420px",
      });
      low.textContent = lower || "";
      low.style.display = lower ? "block" : "none";
    },
    { caption, lower: lower || "" },
  );
}

async function cover(page, on) {
  await page.evaluate((on) => {
    const id = "demo-recorder-cover";
    const existing = document.getElementById(id);
    if (!on) {
      existing?.remove();
      return;
    }
    if (existing) return;
    const el = document.createElement("div");
    el.id = id;
    Object.assign(el.style, {
      position: "fixed",
      inset: "0",
      zIndex: "20000",
      background: "#18181b",
    });
    document.body.appendChild(el);
  }, on);
}

async function settle(page, api, lower) {
  await overlay(page, { caption: `Shot ${api.step.id} · ${api.step.title}`, lower });
  await sleep(api.holdMs);
  const file = join(api.framesDir, `shot-${api.step.id.padStart(2, "0")}-${slug(api.step.title)}.png`);
  await page.screenshot({ path: file });
  api.frames.push(file);
}

async function goHash(page, hash) {
  const target = hash.startsWith("#") ? hash : `#${hash}`;
  await page.evaluate((next) => {
    if (location.hash !== next) location.hash = next;
  }, target);
  await sleep(350);
}

function findPdf(roots, key) {
  const rel = CASE_PDF[key];
  for (const root of roots) {
    const path = join(root, rel);
    if (existsSync(path)) return path;
  }
  return null;
}

async function clickSummary(page, name) {
  const summary = page.locator("summary").filter({ hasText: name }).first();
  if (!(await visible(summary, 800))) return false;
  await summary.scrollIntoViewIfNeeded().catch(() => {});
  await summary.click();
  return true;
}

async function showDescribeExtras(page, api) {
  if (await clickSummary(page, "Applicant and site details")) await sleep(300);
  else api.notes.push("Applicant and site details is not on this screen.");
}

async function ensureRole(page, api, label) {
  const who = h1(page, "Who are you?");
  if (!(await visible(who, 700))) {
    const link = navLink(page, "Describe");
    if (await visible(link, 700)) {
      await link.click();
      await sleep(400);
    }
  }
  if (await visible(who, 700)) {
    api.state.sawWho = true;
    const button = roleButton(page, label);
    if (!(await visible(button, 1500))) {
      return { ok: false, reason: `The ${label} role button is not on Who are you?.` };
    }
    await button.click();
    if (!(await visible(describeHeading(page), 8000))) {
      return { ok: false, reason: `Choosing ${label} did not open the describe screen.` };
    }
    api.state.roles.add(label);
    return { ok: true, mode: "role" };
  }
  if (await visible(describeHeading(page), 1500)) return { ok: true, mode: "fixture" };
  return { ok: false, reason: "Neither Who are you? nor the describe screen is on this build." };
}

async function fillIntake(page, api, spec) {
  const started = await ensureRole(page, api, spec.role);
  if (!started.ok) return started;
  if (started.mode === "fixture") {
    api.notes.push(
      "This build has no Who are you? screen, so the preloaded fixture case stays on screen. The script paragraph was not pasted over it.",
    );
    await showDescribeExtras(page, api);
    return { ok: true, mode: "fixture" };
  }
  const box = page.getByRole("textbox", { name: /What are you building\?|Describe your idea/ }).first();
  if (await visible(box, 2000)) await box.fill(spec.text);
  else api.notes.push("The description field was not found, so the script paragraph was not pasted.");
  const authority = page.getByLabel(/Which authority will review this/).first();
  if (await visible(authority, 800)) {
    try {
      await authority.selectOption({ label: spec.authority });
    } catch (error) {
      api.notes.push(`The authority select did not accept ${spec.authority}: ${error.message}`);
    }
  } else {
    api.notes.push("Which authority will review this? is not on this build.");
  }
  const pdf = findPdf([api.webRoot, join(api.webRoot, ".."), api.repoRoot], spec.pdf);
  if (!pdf) {
    api.notes.push(`Did not upload a PDF. ${CASE_PDF[spec.pdf]} is not in this checkout.`);
  } else {
    const input = page.locator('input[type="file"]');
    if ((await input.count()) === 0) api.notes.push("Choose PDFs is not on this screen, so the case PDF was not uploaded.");
    else {
      await input.first().setInputFiles(pdf);
      api.notes.push(`Uploaded ${CASE_PDF[spec.pdf]}.`);
      await sleep(900);
    }
  }
  await showDescribeExtras(page, api);
  return { ok: true, mode: "role", lower: spec.lower };
}

async function goCodeCheck(page) {
  const cont = page.getByRole("link", { name: "Continue to code check" }).first();
  if (await visible(cont, 800)) await cont.click();
  else {
    const nav = navLink(page, "Code check");
    if (!(await visible(nav, 800))) return false;
    await nav.click();
  }
  return visible(h1(page, "Code check"), 8000);
}

async function goSectionC(page) {
  const cont = page.getByRole("link", { name: "Continue to Section C" }).first();
  if (await visible(cont, 800)) await cont.click();
  else {
    const nav = navLink(page, "Section C");
    if (!(await visible(nav, 800))) return false;
    await nav.click();
  }
  return visible(h1(page, /Section C/), 8000);
}

async function goApplication(page, tabLabel) {
  const onApp = await visible(h1(page, "Application"), 400);
  if (!onApp) {
    const nav = navLink(page, "Application");
    if (!(await visible(nav, 800))) return false;
    await nav.click();
    if (!(await visible(h1(page, "Application"), 8000))) return false;
  }
  if (!tabLabel) return true;
  const tab = page
    .getByRole("navigation", { name: "Application sections" })
    .getByRole("link", { name: new RegExp(`^${escapeReg(tabLabel)}\\b`) })
    .first();
  if (!(await visible(tab, 1200))) return false;
  await tab.click();
  await sleep(350);
  return true;
}

async function answerYourWords(page) {
  const cards = page.locator("article").filter({ hasText: "Your words" });
  const count = await cards.count();
  let clicked = 0;
  for (let i = 0; i < count; i += 1) {
    const button = cards.nth(i).getByRole("button", { name: "Not sure", exact: true });
    if (await visible(button, 500)) {
      await cards.nth(i).scrollIntoViewIfNeeded().catch(() => {});
      await button.click();
      clicked += 1;
    }
  }
  return { count, clicked };
}

async function searchDivisionB(page, query, acceptIds) {
  const box = page.getByLabel("Search Division B").first();
  if (!(await visible(box, 1000))) {
    return { note: "Search Division B is not on this build. No article id was typed in." };
  }
  await box.fill(query);
  await page.getByRole("button", { name: "Search", exact: true }).first().click();
  const finished = page.getByText(/\d+ provisions returned|No provisions returned|did not return|could not be reached|Bad Gateway/).first();
  if (!(await visible(finished, 8000))) {
    return { note: `Search for "${query}" did not report a result. No article id was typed in.` };
  }
  const text = await page.locator("main").innerText();
  if (/did not return|unreachable|could not be reached|bad gateway/i.test(text) && !/\d+ provisions returned/.test(text)) {
    return {
      note: `Search for "${query}" did not return (no engine or code database). No article id was typed in.`,
    };
  }
  const found = acceptIds.find((id) => text.includes(id));
  if (!found) {
    return { note: `Search for "${query}" did not show ${acceptIds.join(" or ")}. Nothing was added.` };
  }
  const item = page
    .locator("li, article")
    .filter({ hasText: found })
    .filter({ has: page.getByRole("button", { name: "Add to this check" }) })
    .first();
  if (!(await visible(item, 1000))) {
    return { note: `Saw ${found} in the page text but not on an Add to this check row. Nothing was added.` };
  }
  await item.getByRole("button", { name: "Add to this check" }).click();
  await sleep(400);
  const card = page.locator("article").filter({ hasText: found }).last();
  const yes = card.getByRole("button", { name: "Yes", exact: true });
  if (await visible(yes, 1500)) await yes.click();
  return { added: found, note: `Added ${found} from the returned search rows and answered Yes on that card.` };
}

async function openFirstCodeReference(page) {
  return clickSummary(page, "Code reference");
}

async function resetCase(page) {
  const button = page.getByRole("button", { name: "Reset case" }).first();
  if (!(await visible(button, 1500))) return false;
  await button.click();
  await sleep(400);
  await visible(h1(page, "Who are you?"), 4000);
  return true;
}

async function shot1(page, api) {
  await goHash(page, "/");
  const who = h1(page, "Who are you?");
  if (!(await visible(who, 2000))) {
    return skipped("Who are you? is not on this build. This checkout opens the describe screen on the fixture case.");
  }
  api.state.sawWho = true;
  api.notes.push("Try an example was left unclicked.");
  await settle(page, api, ALL_LOWER);
  return recorded();
}

async function shot2(page, api) {
  const filled = await fillIntake(page, api, CASES.A);
  if (!filled.ok) return skipped(filled.reason);
  if (!(await visible(describeHeading(page), 2000))) return skipped("The describe screen is not showing.");
  await settle(page, api, filled.lower);
  return recorded();
}

async function shot3(page, api) {
  if (!(await goCodeCheck(page))) return skipped("Code check is not on this build.");
  const words = await answerYourWords(page);
  api.notes.push(
    words.count
      ? `Answered Not sure on ${words.clicked} Your words card(s). Did not answer Yes on them.`
      : "No Your words card is on this screen, so Not sure was not clicked.",
  );
  const search = await searchDivisionB(page, "cladding fastened furring", ["9.27.5.1"]);
  api.notes.push(search.note);
  if (!(await openFirstCodeReference(page))) api.notes.push("Code reference disclosure was not found.");
  const filters = page.getByRole("toolbar", { name: "Filter" });
  if (await visible(filters, 600)) {
    const needs = filters.getByRole("button", { name: /Needs an answer/ });
    if (await visible(needs, 400)) await needs.click();
    await sleep(400);
    const all = filters.getByRole("button", { name: /^All\b/ });
    if (await visible(all, 400)) await all.click();
  }
  await settle(page, api, api.state.roles.has("Manufacturer") ? CASES.A.lower : undefined);
  return recorded();
}

async function shot4(page, api) {
  if (!(await goSectionC(page))) return skipped("Section C is not on this build.");
  const offline = page.getByText(/Offline sample|not a lookup for this case|bundled offline sample/);
  if (await visible(offline, 1200)) {
    api.notes.push("Section C is the bundled offline sample. The engine lookup is not reachable, and no attribution was invented.");
  }
  const row = page.getByRole("row").nth(1);
  if (await visible(row, 1000)) await row.click();
  else api.notes.push("Section C has no attribution row to select.");
  await settle(page, api, api.state.roles.has("Manufacturer") ? CASES.A.lower : undefined);
  return recorded();
}

async function sectionDNote(page, api) {
  const heading = page.getByRole("heading", { name: "Section D and professional screening" }).first();
  if (!(await visible(heading, 5000))) return false;
  await sleep(400);
  const stub = page.getByText(/No engine case|stay blank|did not return|could not be reached|Bad Gateway/).first();
  if (await visible(stub, 1500)) {
    api.notes.push(
      "Section D issues are blank. Those routes need the engine, and the recorder does not call a model or invent evidence.",
    );
  }
  return true;
}

async function shot5(page, api) {
  if (!(await goApplication(page, "Section D"))) {
    return skipped("Section D is not an application tab on this build. The practice-of-engineering screen is a later change.");
  }
  if (!(await sectionDNote(page, api))) {
    return skipped("The Section D tab opened without the professional screening heading.");
  }
  await settle(page, api, api.state.roles.has("Manufacturer") ? CASES.A.lower : undefined);
  return recorded();
}

async function shot6(page, api) {
  const heading = page.getByRole("heading", { name: "Section D and professional screening" }).first();
  if (!(await visible(heading, 800))) {
    if (!(await goApplication(page, "Section D"))) {
      return skipped("Section D is not on this build, so the listing refusal cannot be shown.");
    }
  }
  if (!(await visible(heading, 3000))) return skipped("Section D professional screening is not on screen.");
  const main = await page.locator("main").innerText();
  if (!/does not write the evidence|not a licence decision|listing number/i.test(main)) {
    return skipped(
      "The refusal line (the tool does not write a listing or a professional opinion) is not visible. Section D routes did not return, and that sentence was not invented.",
    );
  }
  await settle(page, api, api.state.roles.has("Manufacturer") ? CASES.A.lower : undefined);
  return recorded();
}

async function shot7(page, api) {
  if (!api.state.sawWho) {
    return skipped("Who are you? is not on this build, so the general-contractor case cannot be started.");
  }
  if (!(await resetCase(page))) return skipped("Reset case is not available, so Case B was not started.");
  const filled = await fillIntake(page, api, CASES.B);
  if (!filled.ok || filled.mode !== "role") {
    return skipped(filled.reason || "General contractor did not open an empty describe screen.");
  }
  if (!(await goCodeCheck(page))) return skipped("Code check did not open for the general-contractor case.");
  const words = await answerYourWords(page);
  api.notes.push(
    words.count
      ? `Answered Not sure on ${words.clicked} Your words card(s).`
      : "No Your words card appeared from the Case B paragraph.",
  );
  const search = await searchDivisionB(page, "combustible piping firestop", ["3.1.9.1", "3.1.9.4"]);
  api.notes.push(search.note);
  await settle(page, api, CASES.B.lower);
  return recorded();
}

async function shot8(page, api) {
  if (!api.state.roles.has("General contractor")) {
    return skipped("The general-contractor case was not started, so Section D for that case was not recorded.");
  }
  if (!(await goApplication(page, "Section D"))) return skipped("Section D is not on this build.");
  const tab = page
    .getByRole("navigation", { name: "Application sections" })
    .getByRole("link", { name: /^Section D\b/ })
    .first();
  if ((await tab.getAttribute("aria-current")) !== "page") {
    return skipped("Section D is not the selected application tab.");
  }
  if (!(await sectionDNote(page, api))) return skipped("Section D professional screening is not on screen.");
  const practice = page.getByText(/Practice of engineering:|not a licence decision|registered professional is indicated/).first();
  if (!(await visible(practice, 1000))) {
    return skipped(
      "The practice-of-engineering line is not on screen. The recorder did not invent an engineering judgment or a licence decision.",
    );
  }
  await settle(page, api, CASES.B.lower);
  return recorded();
}

async function shot9(page, api) {
  if (!api.state.sawWho) {
    return skipped("Who are you? is not on this build, so the homebuilder case cannot be started.");
  }
  if (!(await resetCase(page))) return skipped("Reset case is not available, so Case C was not started.");
  const filled = await fillIntake(page, api, CASES.C);
  if (!filled.ok || filled.mode !== "role") {
    return skipped(filled.reason || "Homebuilder did not open an empty describe screen.");
  }
  if (!(await goCodeCheck(page))) return skipped("Code check did not open for the homebuilder case.");
  const words = await answerYourWords(page);
  api.notes.push(
    words.count
      ? `Answered Not sure on ${words.clicked} Your words card(s).`
      : "No Your words card appeared from the Case C paragraph.",
  );
  const search = await searchDivisionB(page, "bedroom window unobstructed", ["9.9.10.1"]);
  api.notes.push(search.note);
  api.notes.push(
    "STANDATA classification sentences were not spoken or typed. They are recorded only when a matching code-text card is actually returned.",
  );
  await settle(page, api, CASES.C.lower);
  return recorded();
}

async function shot10(page, api) {
  const nav = navLink(page, "Officer review");
  if (!(await visible(nav, 1500))) return skipped("Officer review is not in the navigation.");
  const href = (await nav.getAttribute("href")) || "#/officer";
  await cover(page, true);
  try {
    await page.evaluate((next) => {
      location.hash = next.startsWith("#") ? next : `#${next}`;
    }, href);
    await sleep(400);
    const title = h1(page, "Officer review");
    if (!(await visible(title, 8000))) return skipped("Officer review did not open.");
    if (await visible(page.getByRole("heading", { name: "Not built yet" }), 1000)) {
      await goHash(page, "/describe");
      return skipped(
        "Officer review is the Not built yet placeholder. The script records this shot when the screen lists an open package.",
      );
    }
    const request = page.getByRole("heading", { name: "Information request" }).first();
    if (!(await visible(request, 8000))) {
      return skipped("Officer review opened without an information request, so it was not recorded as the completeness review.");
    }
    await cover(page, false);
    api.notes.push(
      "The officer screen on this build is one planted package, not Cases A, B, and C. Those case labels were not overlaid.",
    );
    const before = page.getByRole("button", { name: "Before fixes" }).first();
    if (await visible(before, 800)) await before.click();
    await request.scrollIntoViewIfNeeded().catch(() => {});
    const copy = page.getByRole("button", { name: "Copy request" }).first();
    if (await visible(copy, 800)) await copy.click();
    else api.notes.push("Copy request is not on this screen.");
    await settle(page, api);
    return recorded();
  } finally {
    await cover(page, false);
  }
}

async function shot11(page, api) {
  if (!(await goApplication(page))) return skipped("The application screen is not on this build.");
  for (const tab of ["Section A", "Section B", "Alternative path"]) {
    const link = page
      .getByRole("navigation", { name: "Application sections" })
      .getByRole("link", { name: new RegExp(`^${escapeReg(tab)}\\b`) })
      .first();
    if (await visible(link, 700)) {
      await link.click();
      await sleep(450);
    } else api.notes.push(`${tab} is not on the application tabs.`);
  }
  const risk = page.getByLabel("Risk assessment").first();
  if (await visible(risk, 600)) await risk.scrollIntoViewIfNeeded().catch(() => {});
  const check = page.getByRole("button", { name: /Check completeness|Run pre-flight/ }).first();
  if (await visible(check, 800)) {
    const disabled = await check.isDisabled();
    api.notes.push(
      disabled
        ? "Check completeness stays disabled. Gaps were not filled to unlock it, and no PDF was downloaded."
        : "Check completeness is enabled. It was not clicked, so no PDF was downloaded.",
    );
    await check.scrollIntoViewIfNeeded().catch(() => {});
  } else {
    api.notes.push("Neither Check completeness nor Run pre-flight is on this build.");
  }
  const authority = page.getByLabel(/Which authority will review this/).first();
  if (!(await visible(authority, 400))) {
    api.notes.push(
      "The authority field is not on the application screen. Edmonton and Calgary appear on Describe when that select exists.",
    );
  }
  const walkedAll = ["Manufacturer", "General contractor", "Homebuilder"].every((role) => api.state.roles.has(role));
  await settle(page, api, walkedAll ? ALL_LOWER : undefined);
  return recorded();
}

export const STEPS = [
  { id: "1", title: "Three applicants, one template", route: "#/", run: shot1 },
  { id: "2", title: "Manufacturer intake", route: "#/describe", run: shot2 },
  { id: "3", title: "The fastening article", route: "#/code-check", run: shot3 },
  { id: "4", title: "Section C lookup", route: "#/section-c", run: shot4 },
  { id: "5", title: "What the evidence must address", route: "#/application?tab=D", run: shot5 },
  { id: "6", title: "It will not invent the listing", route: "#/application?tab=D", run: shot6 },
  { id: "7", title: "General contractor, tested system first", route: "#/describe", run: shot7 },
  { id: "8", title: "It will not write the engineering judgment", route: "#/application?tab=D", run: shot8 },
  { id: "9", title: "Homebuilder, one house, one variance", route: "#/describe", run: shot9 },
  { id: "10", title: "Officer, administrative completeness", route: "#/officer", run: shot10 },
  { id: "11", title: "Same record, two authorities", route: "#/application", run: shot11 },
];

export async function runWalkthrough(page, opts) {
  const apiBase = {
    holdMs: opts.holdMs ?? 1600,
    framesDir: opts.framesDir,
    repoRoot: opts.repoRoot,
    webRoot: opts.webRoot,
    state: { sawWho: false, roles: new Set() },
  };
  const results = [];
  for (const step of STEPS) {
    const notes = [];
    const frames = [];
    const api = { ...apiBase, step, notes, frames };
    try {
      const outcome = await step.run(page, api);
      results.push({ id: step.id, title: step.title, route: step.route, notes, frames, ...outcome });
    } catch (error) {
      results.push({
        id: step.id,
        title: step.title,
        route: step.route,
        status: "skipped",
        reason: `Step threw and was skipped: ${error instanceof Error ? error.message : String(error)}`,
        notes,
        frames,
      });
    }
  }
  return results;
}
