/**
 * Walkthrough for the Batatis demo recording.
 *
 * Ids, titles, and primary routes match docs/demo/script.md (7 shots).
 * Overlay caption is `Shot N · <title>`. The lower third is the script's
 * EXAMPLE DATA line for the case actually on screen.
 *
 * Recording order follows the script: Case C stays open through shots 2, 4, 5,
 * and 7's Case C frame. Reset runs before shot 3 and wipes Case C. Shot 6 is
 * last, with Case A still open. Case B is named on shot 1 and is not walked.
 *
 * A screen that is not in the build is skipped and logged. The runner does not
 * invent article numbers, listings, test results, professional opinions, or
 * stills. It does not upload a PDF, click Try an example, or open Accuracy.
 */
import { existsSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const LOWER = {
  A: "EXAMPLE DATA · Case A · Manufacturer",
  B: "EXAMPLE DATA · Case B · General contractor",
  C: "EXAMPLE DATA · Case C · Homebuilder",
  officer: "EXAMPLE DATA · Sample officer package",
};

const ALL_LOWER = `${LOWER.A}\n${LOWER.B}\n${LOWER.C}`;

const CASES = {
  A: {
    role: "Manufacturer",
    authority: "Edmonton",
    lower: LOWER.A,
    text: "We make EPW NailBase CI-50, a 50 mm insulating sheathing panel, and we want it approved across Alberta so builders can nail vinyl siding straight into the facer. One pilot house: 0000 Example Way NW, Edmonton. Owner not decided. No legal description. No permit yet.",
  },
  C: {
    role: "Homebuilder",
    authority: "Edmonton",
    lower: LOWER.C,
    text: "Two-storey infill at 0000 Example Crescent NW, Edmonton, about 210 m², no sprinklers. Heated slab with R-7.5 under it. Unvented low-slope roof, spray foam thickness still TBD. Bedroom 3 window clear opening 400 mm by 780 mm. What needs a variance?",
  },
};

const OPEN_QUESTION_HOLD_MS = 3500;
const REAL_ADDRESS = "11821 73 Avenue NW";
const FICTIONAL_ADDRESS = "100 Example Street NW";

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

function exampleLabel(lower) {
  if (!lower) return "EXAMPLE DATA";
  if (lower.includes("EXAMPLE DATA")) return lower;
  return `EXAMPLE DATA\n${lower}`;
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
        background: "rgba(20,20,20,0.92)",
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
        background: "#fff7ed",
        color: "#7c2d12",
        border: "2px solid #c2410c",
        font: "700 16px/1.35 ui-sans-serif, system-ui, sans-serif",
        padding: "8px 12px",
        borderRadius: "6px",
        pointerEvents: "none",
        whiteSpace: "pre",
        maxWidth: "460px",
      });
      low.textContent = lower || "";
      low.style.display = lower ? "block" : "none";
      low.setAttribute("data-example-data", lower && lower.includes("EXAMPLE DATA") ? "true" : "false");
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

async function maskRealAddress(page, api) {
  const replaced = await page.evaluate(
    ({ from, to }) => {
      let count = 0;
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      let node = walker.nextNode();
      while (node) {
        if (node.nodeValue && node.nodeValue.includes(from)) {
          node.nodeValue = node.nodeValue.split(from).join(to);
          count += 1;
        }
        node = walker.nextNode();
      }
      for (const el of document.querySelectorAll("input, textarea")) {
        if (typeof el.value === "string" && el.value.includes(from)) {
          el.value = el.value.split(from).join(to);
          count += 1;
        }
      }
      const still =
        document.body.innerText.includes(from) ||
        [...document.querySelectorAll("input, textarea")].some((el) => (el.value || "").includes(from));
      return { count, still };
    },
    { from: REAL_ADDRESS, to: FICTIONAL_ADDRESS },
  );
  if (replaced.count) {
    api.notes.push(
      `Replaced ${replaced.count} on-screen occurrence(s) of ${REAL_ADDRESS} with ${FICTIONAL_ADDRESS}. The frame is labelled EXAMPLE DATA.`,
    );
  }
  return replaced;
}

async function settle(page, api, lower, { holdMs, suffix } = {}) {
  const label = exampleLabel(lower);
  const masked = await maskRealAddress(page, api);
  if (masked.still) {
    return {
      ok: false,
      reason: `${REAL_ADDRESS} is still on screen. The shot was not captured with that address.`,
    };
  }
  await overlay(page, { caption: `Shot ${api.step.id} · ${api.step.title}`, lower: label });
  await sleep(holdMs ?? api.holdMs);
  const file = join(
    api.framesDir,
    `shot-${api.step.id.padStart(2, "0")}-${slug(api.step.title)}${suffix ? `-${suffix}` : ""}.png`,
  );
  await page.screenshot({ path: file });
  api.frames.push(file);
  return { ok: true };
}

async function goHash(page, hash) {
  const target = hash.startsWith("#") ? hash : `#${hash}`;
  await page.evaluate((next) => {
    if (location.hash !== next) location.hash = next;
  }, target);
  await sleep(350);
}

async function openReviewGaps(page, api) {
  const summary = page.locator("summary").filter({ hasText: "Review gaps" }).first();
  if (await visible(summary, 2500)) {
    const details = summary.locator("xpath=ancestor::details[1]");
    const isOpen = await details.evaluate((el) => el.open).catch(() => false);
    if (!isOpen) {
      await summary.scrollIntoViewIfNeeded().catch(() => {});
      await summary.click();
      await sleep(250);
    }
    return;
  }
  api.notes.push("Review gaps is not on this screen.");
}

async function showLedger(page, api) {
  const ledger = page.getByRole("heading", { name: "Fact ledger" }).first();
  if (!(await visible(ledger, 800))) {
    api.notes.push("Fact ledger is not on this screen.");
    return;
  }
  await ledger.scrollIntoViewIfNeeded().catch(() => {});
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
    return { ok: true, mode: "role" };
  }
  if (await visible(describeHeading(page), 1500)) {
    return {
      ok: false,
      reason: "Who are you? is not on this build, so this case was not started over the fixture.",
    };
  }
  return { ok: false, reason: "Neither Who are you? nor the describe screen is on this build." };
}

async function fillIntake(page, api, spec) {
  const started = await ensureRole(page, api, spec.role);
  if (!started.ok) return started;
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
  api.notes.push("Did not upload a PDF.");
  await sleep(500);
  await openReviewGaps(page, api);
  await showLedger(page, api);
  if (await visible(box, 500)) await box.scrollIntoViewIfNeeded().catch(() => {});
  api.state.caseOpen = true;
  return { ok: true, mode: "role", lower: spec.lower };
}

async function goDescribe(page) {
  if (await visible(describeHeading(page), 400)) return true;
  const nav = navLink(page, "Describe");
  if (await visible(nav, 800)) await nav.click();
  else await goHash(page, "/describe");
  return visible(describeHeading(page), 8000);
}

async function goCodeCheck(page) {
  const button = page.getByRole("button", { name: "Continue to code check" }).first();
  if (await visible(button, 800)) await button.click();
  else {
    const link = page.getByRole("link", { name: "Continue to code check" }).first();
    if (await visible(link, 800)) await link.click();
    else {
      const nav = navLink(page, "Code check");
      if (!(await visible(nav, 800))) return false;
      await nav.click();
    }
  }
  return visible(h1(page, "Code check"), 8000);
}

async function goSectionC(page, api) {
  const button = page.getByRole("button", { name: "Continue to Section C" }).first();
  if (await visible(button, 800)) await button.click();
  else {
    const link = page.getByRole("link", { name: "Continue to Section C" }).first();
    if (await visible(link, 800)) await link.click();
  }
  if (await visible(h1(page, /Section C/), 2500)) return true;
  const nav = navLink(page, "Section C");
  if (!(await visible(nav, 800))) return false;
  await nav.click();
  if (!(await visible(h1(page, /Section C/), 8000))) return false;
  if (api) api.notes.push("Continue to Section C did not leave Code check. Section C was opened from the sidebar.");
  return true;
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

async function answerNotSure(page, api) {
  const cards = page.locator("article").filter({ hasText: "Your words" });
  const count = await cards.count();
  const topics = [];
  let clicked = 0;
  for (let i = 0; i < count; i += 1) {
    const card = cards.nth(i);
    const topic = (await card.locator("h2").first().innerText().catch(() => "")).trim();
    if (topic) topics.push(topic);
    const button = card.getByRole("button", { name: "Not sure", exact: true });
    if (await visible(button, 500)) {
      await card.scrollIntoViewIfNeeded().catch(() => {});
      await button.click();
      clicked += 1;
    }
  }
  api.notes.push(
    count
      ? `Answered Not sure on ${clicked} Your words card(s)${topics.length ? `: ${topics.join("; ")}` : ""}. Did not answer Yes or No.`
      : "No Your words card is on this screen, so Not sure was not clicked.",
  );
  const openQ = page.getByText("Open question", { exact: true }).last();
  if (clicked && (await visible(openQ, 1000))) {
    await openQ.scrollIntoViewIfNeeded().catch(() => {});
    return true;
  }
  if (clicked) {
    api.notes.push("Not sure was clicked, but the Open question label was not on screen. That sentence was not invented.");
  }
  return false;
}

async function searchDivisionB(page, query, acceptId) {
  const box = page.getByLabel("Search Division B").first();
  if (!(await visible(box, 1000))) {
    return { note: "Search Division B is not on this build. No article id was typed in." };
  }
  await box.fill(query);
  const form = box.locator("xpath=ancestor::form[1]");
  const search = form.getByRole("button", { name: "Search", exact: true });
  if (!(await visible(search, 800))) {
    return { note: `The Search button for "${query}" is not on this screen. No article id was typed in.` };
  }
  await search.click();
  const finished = page
    .getByText(/\d+ provisions returned|No provisions returned|did not return|could not be reached|unreachable|Failed to fetch|Bad Gateway|ERR_/)
    .first();
  if (!(await visible(finished, 8000))) {
    return { note: `Search for "${query}" did not report a result. No article id was typed in.` };
  }
  const text = await page.locator("main").innerText();
  if (
    /did not return|unreachable|could not be reached|bad gateway|failed to fetch|err_/i.test(text) &&
    !/\d+ provisions returned/.test(text)
  ) {
    return {
      note: `Search for "${query}" did not return (no engine or code database). ${acceptId} was not typed in.`,
    };
  }
  const rows = page.locator("li").filter({ has: page.getByRole("button", { name: "Add to this check" }) });
  const count = await rows.count();
  let matched = null;
  const seen = [];
  for (let i = 0; i < count; i += 1) {
    const row = rows.nth(i);
    const idText = (await row.locator(".article-id").first().innerText().catch(() => "")).trim();
    if (idText) seen.push(idText);
    if (idText === acceptId) matched = row;
  }
  if (!matched) {
    return {
      note: `Search for "${query}" did not show a row whose id is ${acceptId}${seen.length ? ` (rows: ${seen.join(", ")})` : ""}. Nothing was added.`,
    };
  }
  await matched.getByRole("button", { name: "Add to this check" }).click();
  await sleep(400);
  const card = page.locator("article").filter({ hasText: acceptId }).last();
  const yes = card.getByRole("button", { name: "Yes", exact: true });
  if (await visible(yes, 1500)) await yes.click();
  else return { added: acceptId, note: `Added ${acceptId} from the returned rows. The Yes button was not on that card.` };
  return { added: acceptId, note: `Added ${acceptId} from the returned search rows and answered Yes on that card.` };
}

async function resetCase(page, api) {
  const button = page.getByRole("button", { name: "Reset case" }).first();
  if (!(await visible(button, 1500))) return false;
  await button.click();
  await sleep(400);
  const who = await visible(h1(page, "Who are you?"), 4000);
  if (!who) return false;
  api.state.sawWho = true;
  api.state.caseOpen = false;
  api.state.caseC = false;
  api.state.caseA = false;
  const note = page.getByText("Cleared. Nothing from the previous case is kept.").first();
  if (await visible(note, 800)) {
    api.notes.push("Reset case showed: Cleared. Nothing from the previous case is kept.");
  } else {
    api.notes.push("Reset case returned to Who are you?. The cleared-note sentence was not on screen.");
  }
  return true;
}

async function noteCheckCompleteness(page, api) {
  const check = page.getByRole("button", { name: /Check completeness|Run pre-flight/ }).first();
  if (!(await visible(check, 800))) {
    api.notes.push("Neither Check completeness nor Run pre-flight is on this build. No PDF was downloaded.");
    return;
  }
  const disabled = await check.isDisabled();
  api.notes.push(
    disabled
      ? "Check completeness stays disabled. It was not clicked, and no PDF was downloaded."
      : "Check completeness is enabled. It was not clicked, so no PDF was downloaded.",
  );
  await check.scrollIntoViewIfNeeded().catch(() => {});
}

async function shot1(page, api) {
  await goHash(page, "/");
  const who = h1(page, "Who are you?");
  if (!(await visible(who, 2000))) {
    return skipped("Who are you? is not on this build. This checkout opens the describe screen on the fixture case.");
  }
  api.state.sawWho = true;
  api.notes.push("Try an example was left unclicked.");
  const frame = await settle(page, api, ALL_LOWER);
  if (!frame.ok) return skipped(frame.reason);
  return recorded();
}

async function shot2(page, api) {
  const filled = await fillIntake(page, api, CASES.C);
  if (!filled.ok) return skipped(filled.reason);
  if (!(await visible(describeHeading(page), 2000))) return skipped("The describe screen is not showing.");
  api.state.caseC = true;
  const frame = await settle(page, api, filled.lower);
  if (!frame.ok) return skipped(frame.reason);
  return recorded();
}

async function shot3(page, api) {
  if (!api.state.sawWho) {
    return skipped("Who are you? is not on this build, so the manufacturer case cannot be started.");
  }
  if (!(await resetCase(page, api))) return skipped("Reset case is not available, so Case A was not started.");
  const filled = await fillIntake(page, api, CASES.A);
  if (!filled.ok || filled.mode !== "role") {
    return skipped(filled.reason || "Manufacturer did not open an empty describe screen.");
  }
  api.state.caseA = true;
  const paste = await settle(page, api, CASES.A.lower, { suffix: "paste" });
  if (!paste.ok) return skipped(paste.reason);
  if (!(await goCodeCheck(page))) return skipped("Code check did not open for the manufacturer case.");
  const sawOpen = await answerNotSure(page, api);
  const frame = await settle(page, api, CASES.A.lower, {
    holdMs: sawOpen ? Math.max(api.holdMs, OPEN_QUESTION_HOLD_MS) : api.holdMs,
    suffix: "open-question",
  });
  if (!frame.ok) return skipped(frame.reason);
  return recorded();
}

async function shot4(page, api) {
  if (!api.state.caseC) return skipped("Case C is not the open case, so the code-identification shot was not recorded.");
  if (!(await visible(h1(page, "Code check"), 400)) && !(await goCodeCheck(page))) {
    return skipped("Code check is not on this build.");
  }
  await answerNotSure(page, api);
  const search = await searchDivisionB(page, "bedroom window unobstructed", "9.9.10.1.(2)");
  api.notes.push(search.note);
  if (search.added) {
    const reference = page
      .locator("article")
      .filter({ hasText: search.added })
      .locator("summary")
      .filter({ hasText: "Code reference" })
      .first();
    if (await visible(reference, 800)) {
      await reference.click();
      api.notes.push("Opened Code reference on the row that was added.");
    } else api.notes.push("Code reference disclosure was not on the added row.");
  }
  const searchBox = page.getByLabel("Search Division B").first();
  if (await visible(searchBox, 500)) await searchBox.scrollIntoViewIfNeeded().catch(() => {});
  const searchFrame = await settle(page, api, CASES.C.lower, { suffix: "search" });
  if (!searchFrame.ok) return skipped(searchFrame.reason);
  if (!(await goSectionC(page, api))) return skipped("Section C is not on this build.");
  const offline = page.getByText(/Offline sample|not a lookup for this case|bundled offline sample|Lookup failed|did not return|could not be reached/);
  if (await visible(offline, 1200)) {
    api.notes.push("Section C did not show a live lookup. No objective, function, or intent was invented.");
  }
  if (search.added) {
    const row = page.getByRole("row").filter({ hasText: search.added }).first();
    if (await visible(row, 1000)) await row.click();
    else api.notes.push(`Section C has no row for ${search.added}. No attribution was typed in.`);
  } else {
    api.notes.push("No article was added, so no Section C row was selected.");
  }
  api.notes.push("Ranked list still is not in this build. Omitted. No ranked caption was added.");
  api.notes.push("Benchmark card is not in this build. Omitted.");
  api.notes.push("Eval still is not in this build. Omitted. #/accuracy was not opened.");
  const frame = await settle(page, api, CASES.C.lower);
  if (!frame.ok) return skipped(frame.reason);
  return recorded();
}

async function shot5(page, api) {
  if (!api.state.caseC) return skipped("Case C is not the open case, so Section D was not recorded.");
  if (!(await goApplication(page, "Alternative path"))) {
    return skipped("Alternative path is not an application tab on this build.");
  }
  const risk = page.getByLabel("Risk assessment").first();
  if (await visible(risk, 800)) await risk.scrollIntoViewIfNeeded().catch(() => {});
  else api.notes.push("Risk assessment is not on the alternative path.");
  api.notes.push("Process fields were left empty. Nothing was typed into them.");
  await openReviewGaps(page, api);
  const altFrame = await settle(page, api, CASES.C.lower, { suffix: "alternative-path" });
  if (!altFrame.ok) return skipped(altFrame.reason);
  if (!(await goApplication(page, "Section D"))) return skipped("Section D is not an application tab on this build.");
  const heading = page.getByRole("heading", { name: "Section D and professional screening" }).first();
  if (!(await visible(heading, 5000))) {
    return skipped("The Section D tab opened without the professional screening heading.");
  }
  const limit = page.getByText(/does not write the evidence|not a licence decision|This is not a licence decision/i).first();
  if (await visible(limit, 1000)) {
    api.notes.push("The on-screen limit line is visible. It was not typed by the recorder.");
    await limit.scrollIntoViewIfNeeded().catch(() => {});
  } else {
    api.notes.push(
      "The limit line is not on screen. Section D routes did not return a card, and no evidence or judgement was invented.",
    );
  }
  const frame = await settle(page, api, CASES.C.lower, { suffix: "section-d" });
  if (!frame.ok) return skipped(frame.reason);
  return recorded();
}

async function waitOfficerLoaded(page) {
  const loading = page.getByText(/Loading the package…|Reviewing the example package…|Missing items will appear here/).first();
  if (await visible(loading, 1000)) {
    await page
      .getByText(/Online review unavailable|Online administrative review|No missing|Your application appears to be missing/)
      .first()
      .waitFor({ timeout: 8000 })
      .catch(() => {});
  }
  await sleep(300);
}

function namedButton(page, names) {
  return page.getByRole("button", { name: new RegExp(`^(${names.map(escapeReg).join("|")})$`) }).first();
}

async function shot6(page, api) {
  if (!api.state.caseOpen) {
    return skipped("No case is open, so Officer review stays on Who are you?. The planted package was not recorded.");
  }
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
      return skipped("Officer review is the Not built yet placeholder. The planted package was not recorded.");
    }
    if (await visible(h1(page, "Who are you?"), 400)) {
      return skipped("Officer review sent the browser back to Who are you?. The planted package was not recorded.");
    }
    if (await visible(page.getByText("does not open the sample package").first(), 800)) {
      return skipped("Officer review says this application does not open the sample package. The planted package was not recorded.");
    }
    const before = namedButton(page, ["Before fixes", "Original example"]);
    if (!(await visible(before, 8000))) {
      const toolbar = page.getByRole("group", { name: "Package version" }).first();
      const onScreen = (await visible(toolbar, 500)) ? (await toolbar.innerText()).replace(/\s+/g, " ").trim() : "";
      return skipped(
        onScreen
          ? `Officer review package controls read "${onScreen}". Neither Before fixes nor Original example is on screen, so the planted package was not recorded.`
          : "Officer review opened without a package version control, so the planted package was not recorded.",
      );
    }
    await cover(page, false);
    const beforeName = (await before.innerText()).replace(/\s+/g, " ").trim();
    api.notes.push(`The officer screen is one planted package. Version control on screen: ${beforeName}. Case A, B, and C labels were not overlaid.`);
    await before.click();
    await waitOfficerLoaded(page);
    const beforeFrame = await settle(page, api, LOWER.officer, { suffix: "before" });
    if (!beforeFrame.ok) return skipped(beforeFrame.reason);
    const after = namedButton(page, ["After fixes", "Updated example"]);
    if (await visible(after, 800)) {
      const afterName = (await after.innerText()).replace(/\s+/g, " ").trim();
      api.notes.push(`Second version control on screen: ${afterName}.`);
      await after.click();
    } else api.notes.push("The second package version control is not on this screen.");
    await waitOfficerLoaded(page);
    const request = page.getByRole("heading", { name: "Information request" }).first();
    if (await visible(request, 2000)) await request.scrollIntoViewIfNeeded().catch(() => {});
    else api.notes.push("Information request is not on this screen.");
    const copy = namedButton(page, ["Copy request", "Copy example request"]);
    if (await visible(copy, 800)) await copy.scrollIntoViewIfNeeded().catch(() => {});
    else api.notes.push("Copy request is not on this screen.");
    const afterFrame = await settle(page, api, LOWER.officer, { suffix: "after" });
    if (!afterFrame.ok) return skipped(afterFrame.reason);
    const shown = await page.evaluate((from) => document.body.innerText.includes(from), REAL_ADDRESS);
    if (shown) return skipped(`${REAL_ADDRESS} is on the officer screen. The shot was not kept.`);
    return recorded();
  } finally {
    await cover(page, false);
  }
}

async function authorityFrame(page, api, spec, suffix) {
  if (!(await goDescribe(page))) return skipped("The describe screen is not available for the authority select.");
  const authority = page.getByLabel(/Which authority will review this/).first();
  if (await visible(authority, 800)) {
    await authority.scrollIntoViewIfNeeded().catch(() => {});
    const value = await authority.inputValue().catch(() => "");
    api.notes.push(
      value
        ? `Authority select value is "${value}". It was not changed on this frame.`
        : "The authority select is empty. It was not given a new value on this frame.",
    );
  } else api.notes.push("Which authority will review this? is not on this screen.");
  const describeFrame = await settle(page, api, spec.lower, { suffix: `${suffix}-authority` });
  if (!describeFrame.ok) return skipped(describeFrame.reason);
  if (!(await goApplication(page, "Alternative path"))) {
    return skipped("The application screen is not on this build for the gaps frame.");
  }
  await openReviewGaps(page, api);
  await noteCheckCompleteness(page, api);
  const appFrame = await settle(page, api, spec.lower, { suffix: `${suffix}-application` });
  if (!appFrame.ok) return skipped(appFrame.reason);
  return recorded();
}

async function shot7(page, api) {
  if (api.frame === "A") {
    if (!api.state.caseA) return skipped("Case A is not the open case, so its authority frame was not recorded.");
    api.notes.push("Case A authority frame.");
    return authorityFrame(page, api, CASES.A, "case-a");
  }
  if (!api.state.caseC) return skipped("Case C is not the open case, so its authority frame was not recorded.");
  api.notes.push("Case C authority frame.");
  return authorityFrame(page, api, CASES.C, "case-c");
}

export const STEPS = [
  { id: "1", title: "Three applicants (0:18)", route: "#/", run: shot1 },
  { id: "2", title: "Homebuilder paste (0:10)", route: "#/describe", run: shot2 },
  { id: "3", title: "Not sure (0:23)", route: "#/", run: shot3 },
  { id: "4", title: "Code identification (0:45)", route: "#/section-c", run: shot4 },
  { id: "5", title: "Section D, then the limit (0:24 + 0:08)", route: "#/application?tab=alt", run: shot5 },
  { id: "6", title: "Officer, one planted package (0:36)", route: "#/officer", run: shot6 },
  { id: "7", title: "Authority, gaps still open (0:16)", route: "#/describe", run: shot7 },
];

function mergeParts(step, parts) {
  const failed = parts.filter((part) => part.status !== "recorded");
  const notes = parts.flatMap((part) => part.notes || []);
  const frames = parts.flatMap((part) => part.frames || []);
  if (failed.length) {
    return {
      id: step.id,
      title: step.title,
      route: step.route,
      status: "skipped",
      reason: failed.map((part) => part.reason).filter(Boolean).join(" "),
      notes,
      frames,
    };
  }
  return { id: step.id, title: step.title, route: step.route, status: "recorded", notes, frames };
}

export async function runWalkthrough(page, opts) {
  const apiBase = {
    holdMs: opts.holdMs ?? 1600,
    framesDir: opts.framesDir,
    state: { sawWho: false, caseOpen: false, caseC: false, caseA: false },
  };
  const stepById = new Map(STEPS.map((step) => [step.id, step]));

  async function exec(id, extra) {
    const step = stepById.get(id);
    const notes = [];
    const frames = [];
    const api = { ...apiBase, step, notes, frames, ...extra };
    try {
      const outcome = await step.run(page, api);
      return { id: step.id, title: step.title, route: step.route, notes, frames, ...outcome };
    } catch (error) {
      return {
        id: step.id,
        title: step.title,
        route: step.route,
        status: "skipped",
        reason: `Step threw and was skipped: ${error instanceof Error ? error.message : String(error)}`,
        notes,
        frames,
      };
    }
  }

  // Script order: 1, 2, 4, 5, 7 (Case C), reset inside 3, 7 (Case A), 6.
  const shot1Result = await exec("1");
  const shot2Result = await exec("2");
  const shot4Result = await exec("4");
  const shot5Result = await exec("5");
  const shot7c = await exec("7", { frame: "C" });
  const shot3Result = await exec("3");
  const shot7a = await exec("7", { frame: "A" });
  const shot6Result = await exec("6");
  const shot7Result = mergeParts(stepById.get("7"), [shot7c, shot7a]);

  return [shot1Result, shot2Result, shot3Result, shot4Result, shot5Result, shot6Result, shot7Result].sort(
    (a, b) => Number(a.id) - Number(b.id),
  );
}

/** Deck slots from the screenshot list. Filenames are the PNG basenames. */
export const DECK_STILLS = [
  { id: "shot-s08-roles", file: "shot-s08-roles.png" },
  { id: "shot-s02-describe", file: "shot-s02-describe.png" },
  { id: "shot-s03-not-sure", file: "shot-s03-not-sure.png" },
  { id: "shot-s04-search", file: "shot-s04-search.png" },
  { id: "shot-s04-benchmark", file: "shot-s04-benchmark.png" },
  { id: "shot-s05-eval", file: "shot-s05-eval.png" },
  { id: "shot-s06-section-d", file: "shot-s06-section-d.png" },
  { id: "shot-s07-officer", file: "shot-s07-officer.png" },
  { id: "shot-s09-locked", file: "shot-s09-locked.png" },
  { id: "shot-s09-scc-form", file: "shot-s09-scc-form.png" },
];

function pngSize(buffer) {
  if (buffer.length < 24 || buffer.readUInt32BE(12) !== 0x49484452) return { width: 0, height: 0 };
  return { width: buffer.readUInt32BE(16), height: buffer.readUInt32BE(20) };
}

async function saveStill(page, api, lower, filePath) {
  const label = exampleLabel(lower);
  const masked = await maskRealAddress(page, api);
  if (masked.still) {
    return { ok: false, reason: `${REAL_ADDRESS} is still on screen. The still was not saved.` };
  }
  await overlay(page, { caption: "", lower: label });
  await sleep(300);
  const buffer = await page.screenshot({ type: "png" });
  const size = pngSize(buffer);
  if (size.width !== 1440 || size.height !== 900) {
    return { ok: false, reason: `Screenshot was ${size.width}×${size.height}, not 1440×900.` };
  }
  writeFileSync(filePath, buffer);
  return { ok: true, width: size.width, height: size.height };
}

export async function runDeckStills(page, opts) {
  const outDir = opts.outDir;
  const api = {
    holdMs: 400,
    framesDir: outDir,
    step: { id: "0", title: "still" },
    notes: [],
    frames: [],
    state: { sawWho: false, caseOpen: false, caseC: false, caseA: false },
  };
  const byId = new Map();

  function drop(id) {
    const slot = DECK_STILLS.find((item) => item.id === id);
    const filePath = join(outDir, slot.file);
    if (existsSync(filePath)) rmSync(filePath);
  }

  function finish(id, outcome) {
    const slot = DECK_STILLS.find((item) => item.id === id);
    if (outcome.status !== "captured") drop(id);
    byId.set(id, {
      id,
      file: slot.file,
      notes: outcome.notes || [],
      ...outcome,
    });
  }

  async function capture(id, lower) {
    const slot = DECK_STILLS.find((item) => item.id === id);
    const saved = await saveStill(page, api, lower, join(outDir, slot.file));
    const notes = [...api.notes];
    api.notes.length = 0;
    if (!saved.ok) return finish(id, { status: "skipped", reason: saved.reason, notes });
    return finish(id, { status: "captured", width: saved.width, height: saved.height, notes });
  }

  function skip(id, reason) {
    const notes = [...api.notes];
    api.notes.length = 0;
    return finish(id, { status: "skipped", reason, notes });
  }

  try {
    await goHash(page, "/");
    const who = h1(page, "Who are you?");
    const roles = ["Manufacturer", "General contractor", "Homebuilder"];
    const missingRole = [];
    if (await visible(who, 2000)) {
      api.state.sawWho = true;
      for (const label of roles) {
        if (!(await visible(roleButton(page, label), 1000))) missingRole.push(label);
      }
    }
    if (!api.state.sawWho) {
      skip("shot-s08-roles", "Who are you? is not on this build.");
    } else if (missingRole.length) {
      skip("shot-s08-roles", `Role buttons not on screen: ${missingRole.join(", ")}.`);
    } else {
      api.notes.push("Try an example was left unclicked.");
      await capture("shot-s08-roles", ALL_LOWER);
    }

    const filledC = api.state.sawWho ? await fillIntake(page, api, CASES.C) : { ok: false, reason: "Who are you? is not on this build, so Case C was not pasted." };
    if (!filledC.ok) {
      skip("shot-s02-describe", filledC.reason);
    } else {
      api.state.caseC = true;
      const body = await page.locator("main").innerText();
      if (!body.includes("0000 Example Crescent")) {
        skip("shot-s02-describe", "The Case C paragraph is not in the description. The still was not saved.");
      } else {
        const gaps = ["Owner", "Mailing address", "Legal description"].filter((label) => body.includes(label));
        api.notes.push(gaps.length ? `Missing-item text on screen: ${gaps.join(", ")}.` : "Owner, mailing address, and legal description were not named on this screen.");
        if (!body.includes("Review gaps")) {
          skip("shot-s02-describe", "Review gaps is not on this screen. The describe still was not saved.");
        } else {
          const summary = page.locator("summary").filter({ hasText: "Review gaps" }).first();
          if (await visible(summary, 500)) await summary.scrollIntoViewIfNeeded().catch(() => {});
          await capture("shot-s02-describe", CASES.C.lower);
        }
      }
    }

    if (!api.state.caseC) {
      skip("shot-s04-search", "Case C is not open, so the bedroom-window search was not run.");
    } else {
      if (!(await visible(h1(page, "Code check"), 400)) && !(await goCodeCheck(page))) {
        skip("shot-s04-search", "Code check is not on this build.");
      } else {
        await answerNotSure(page, api);
        const search = await searchDivisionB(page, "bedroom window unobstructed", "9.9.10.1.(2)");
        api.notes.push(search.note);
        if (!search.added) {
          skip(
            "shot-s04-search",
            "Search did not show a returned row for 9.9.10.1.(2). No article id was typed in, and the Section C lookup was not drawn.",
          );
        } else if (!(await goSectionC(page, api))) {
          skip("shot-s04-search", "Section C is not on this build, so the lookup still was not saved.");
        } else {
          const row = page.getByRole("row").filter({ hasText: search.added }).first();
          if (!(await visible(row, 1500))) {
            skip("shot-s04-search", `Section C has no row for ${search.added}. The lookup still was not drawn.`);
          } else {
            await row.scrollIntoViewIfNeeded().catch(() => {});
            await capture("shot-s04-search", CASES.C.lower);
          }
        }
      }
    }

    skip(
      "shot-s04-benchmark",
      "The ranked list and benchmark card are not in this app build. The still was not drawn.",
    );
    skip(
      "shot-s05-eval",
      "The eval still is not a screen in this build. #/accuracy was not opened, and the figures were not drawn.",
    );

    if (!api.state.caseC) {
      skip("shot-s06-section-d", "Case C is not open, so Section D was not captured.");
    } else if (!(await goApplication(page, "Section D"))) {
      skip("shot-s06-section-d", "Section D is not an application tab on this build.");
    } else {
      const heading = page.getByRole("heading", { name: "Section D and professional screening" }).first();
      if (!(await visible(heading, 5000))) {
        skip("shot-s06-section-d", "Section D and professional screening is not on this build.");
      } else {
        const limit = page.getByText("This tool does not write the evidence or the professional opinion.").first();
        if (await visible(limit, 800)) {
          api.notes.push("The on-screen limit line is visible.");
          await limit.scrollIntoViewIfNeeded().catch(() => {});
        } else {
          api.notes.push(
            "The sentence \"This tool does not write the evidence or the professional opinion.\" is not on this screen. It was not added.",
          );
          await heading.scrollIntoViewIfNeeded().catch(() => {});
        }
        await capture("shot-s06-section-d", CASES.C.lower);
      }
    }

    if (!api.state.caseC) {
      skip("shot-s09-locked", "Case C is not open, so the application still was not captured.");
    } else if (!(await goApplication(page))) {
      skip("shot-s09-locked", "The application screen is not on this build.");
    } else {
      await openReviewGaps(page, api);
      const check = page.getByRole("button", { name: /Check completeness|Run pre-flight/ }).first();
      if (!(await visible(check, 800))) {
        skip("shot-s09-locked", "Check completeness is not on this build. The locked still was not drawn.");
      } else if (!(await check.isDisabled())) {
        skip(
          "shot-s09-locked",
          "Check completeness is enabled while gaps are open. The disabled control is not on this build, and the still was not faked.",
        );
      } else {
        api.notes.push("Check completeness is disabled. It was not clicked. No PDF was downloaded.");
        await check.scrollIntoViewIfNeeded().catch(() => {});
        await capture("shot-s09-locked", CASES.C.lower);
      }
    }

    if (!api.state.sawWho) {
      skip("shot-s03-not-sure", "Who are you? is not on this build, so the manufacturer case cannot be started.");
    } else if (!(await resetCase(page, api))) {
      skip("shot-s03-not-sure", "Reset case is not available, so the Not sure still was not captured.");
    } else {
      const filledA = await fillIntake(page, api, CASES.A);
      if (!filledA.ok) {
        skip("shot-s03-not-sure", filledA.reason);
      } else {
        api.state.caseA = true;
        if (!(await goCodeCheck(page))) {
          skip("shot-s03-not-sure", "Code check did not open for the manufacturer case.");
        } else {
          await answerNotSure(page, api);
          const cards = page.locator("article").filter({ hasText: "Your words" });
          const count = await cards.count();
          let pressed = 0;
          for (let i = 0; i < count; i += 1) {
            const button = cards.nth(i).getByRole("button", { name: "Not sure", exact: true });
            if ((await button.getAttribute("aria-pressed").catch(() => "")) === "true") pressed += 1;
          }
          if (pressed < 2) {
            skip(
              "shot-s03-not-sure",
              `Not sure is pressed on ${pressed} Your words card(s), not two. The still was not saved.`,
            );
          } else {
            await cards.first().scrollIntoViewIfNeeded().catch(() => {});
            await capture("shot-s03-not-sure", CASES.A.lower);
          }
        }
      }
    }

    if (!api.state.caseOpen) {
      skip("shot-s07-officer", "No case is open, so Officer review does not show the planted package.");
    } else {
      const nav = navLink(page, "Officer review");
      if (!(await visible(nav, 1500))) {
        skip("shot-s07-officer", "Officer review is not in the navigation.");
      } else {
        const href = (await nav.getAttribute("href")) || "#/officer";
        await page.evaluate((next) => {
          location.hash = next.startsWith("#") ? next : `#${next}`;
        }, href);
        await sleep(400);
        if (!(await visible(h1(page, "Officer review"), 8000))) {
          skip("shot-s07-officer", "Officer review did not open.");
        } else if (await visible(page.getByRole("heading", { name: "Not built yet" }), 800)) {
          skip("shot-s07-officer", "Officer review is the Not built yet placeholder.");
        } else if (await visible(page.getByText("does not open the sample package").first(), 800)) {
          skip("shot-s07-officer", "Officer review says this application does not open the sample package.");
        } else {
          const before = namedButton(page, ["Before fixes", "Original example"]);
          if (!(await visible(before, 8000))) {
            skip("shot-s07-officer", "Officer review opened without a package version control.");
          } else {
            await before.click();
            await waitOfficerLoaded(page);
            const after = namedButton(page, ["After fixes", "Updated example"]);
            if (await visible(after, 800)) {
              api.notes.push(`Version controls on screen: ${(await before.innerText()).trim()}, ${(await after.innerText()).trim()}.`);
              await after.click();
              await waitOfficerLoaded(page);
            }
            const copy = namedButton(page, ["Copy request", "Copy example request"]);
            if (await visible(copy, 800)) await copy.scrollIntoViewIfNeeded().catch(() => {});
            else api.notes.push("Copy request is not on this screen.");
            await capture("shot-s07-officer", LOWER.officer);
          }
        }
      }
    }

    skip(
      "shot-s09-scc-form",
      "The filled SCC form is an engine PDF. Check completeness was not clicked, and this run does not call the engine, so the form was not captured.",
    );
  } catch (error) {
    const reason = `Stills stopped: ${error instanceof Error ? error.message : String(error)}`;
    for (const slot of DECK_STILLS) {
      if (!byId.has(slot.id)) finish(slot.id, { status: "skipped", reason, notes: [] });
    }
  }

  return DECK_STILLS.map((slot) => byId.get(slot.id) || { id: slot.id, file: slot.file, status: "skipped", reason: "Not reached.", notes: [] });
}
