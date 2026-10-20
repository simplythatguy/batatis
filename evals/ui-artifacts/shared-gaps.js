/**
 * Single data model for the VAR-1042 surfaces: intake fields, article confirmation,
 * Section C attributions, Section D plan and the derived gap list. State persists in
 * sessionStorage so edits on one screen show on every other screen.
 * Append `?reset` to any artifact URL to restore the seeded state.
 */
export const PROJECT_ID = "VAR-1042";
export const PROJECT_LABEL = "VAR-1042 · Straw wall";
export const CODE_EDITION = "NBC(AE) 2023";

/** @typedef {'confirmed'|'pending'|'needs-clarification'|'rejected'} ArticleStatus */

/** Seeded registry rows. Sample text is illustrative; verify against the edition before use. */
export const ARTICLES = [
  {
    id: "9.25.2.1.",
    title: "Required insulation",
    rank: 1,
    benchmark: true,
    status: "pending",
    objective: "OH1",
    fn: "F51",
    intent: "Limit heat loss through the building envelope so indoor conditions stay acceptable to occupants.",
    intentRef: "Intent statement 9.25.2.1.(1)",
    excerpt:
      "9.25.2.1. Required Insulation — All walls, ceilings and floors separating heated space from unheated space, the exterior air or the exterior soil shall be provided with sufficient thermal insulation…",
    explainRanking: "Most likely benchmark for the described exterior wall thermal performance. Confirm after verifying edition text.",
    explainSectionC:
      "This article is the benchmark acceptable solution for insulating exterior walls in Part 9 buildings. Your alternative must address the same objectives and functions through equivalent-performance evidence. This panel does not certify compliance.",
  },
  {
    id: "9.25.3.1.",
    title: "Required barrier to air leakage",
    rank: 2,
    benchmark: false,
    status: "needs-clarification",
    objective: "OH1",
    fn: "F55",
    intent: null,
    intentRef: null,
    excerpt:
      "9.25.3.1. Required Barrier to Air Leakage — Thermally insulated wall, ceiling and floor assemblies shall be constructed to include an air barrier system…",
    explainRanking:
      "May apply if the straw-bale assembly relies on plaster as its air barrier. Clarify whether a separate air barrier is proposed before confirming.",
    explainSectionC:
      "Applies only if the plaster finish is relied on as the air barrier. Intent lookup returned no statement; add it before this article can be exported.",
  },
];

const SECTION_D_SEED = [
  {
    id: "hotbox",
    item: "Thermal performance test of the wall assembly (guarded hot box, ASTM C1363)",
    short: "wall assembly thermal test",
    by: "ISO/IEC 17025-accredited lab · not yet named",
    note: null,
  },
  {
    id: "opinion",
    item: "Equivalency opinion for the alternative solution",
    short: "equivalency opinion",
    by: "Applicant's registered professional",
    note: "Not authored by this tool",
  },
];

/** Section D rows; every row without an upload is a shared warning gap. */
export const sectionD = () =>
  SECTION_D_SEED.map((d) => {
    const file = state.uploads[d.id];
    return file
      ? { ...d, uploaded: file, status: "uploaded", statusLabel: `Uploaded · ${file}` }
      : { ...d, uploaded: null, status: "missing", statusLabel: "Required · not uploaded" };
  });

export function sectionDPill(d) {
  return `<span class="label-pill" data-evidence-status="${d.status}"><span class="status-dot ${d.status === "uploaded" ? "done" : "warning"}"></span>${d.statusLabel}</span>`;
}

export function setUpload(id, filename) {
  state.uploads[id] = filename;
  save();
}

export const PROCESS_FIELD_DEFS = [
  { id: "risk", label: "Risk assessment" },
  { id: "mitigation", label: "Mitigating measures" },
  { id: "assumptions", label: "Assumptions / limits" },
];

const DEFAULT_FIELDS = {
  owner: "Amina Okonkwo",
  ownerConfirmed: false,
  rep: "",
  mail: "",
  date: "2026-10-20",
  permit: "",
  juris: "",
  muni: "",
  ats: "NW-12-24-1-W5",
  atsAssumption: true,
  alternative:
    "Load-bearing straw-bale wall assembly as alternative to NBC(AE) Part 9 acceptable solution for exterior walls.",
  risk: "",
  mitigation: "Lime plaster both faces; moisture monitoring at sill plates for the first two heating seasons.",
  assumptions: "",
};

export const JURIS_OPTIONS = { site: "No — site specific", jurisdiction: "Yes — jurisdiction-wide" };

const KEY = "batatis-var-1042";

function seed() {
  return {
    fields: { ...DEFAULT_FIELDS },
    articles: Object.fromEntries(ARTICLES.map((a) => [a.id, a.status])),
    intents: {},
    uploads: {},
    savedAt: null,
  };
}

function load() {
  if (new URLSearchParams(location.search).has("reset")) sessionStorage.removeItem(KEY);
  try {
    const raw = JSON.parse(sessionStorage.getItem(KEY));
    if (raw && raw.fields && raw.articles) return { intents: {}, uploads: {}, ...raw };
  } catch {}
  return seed();
}

export const state = load();

export function save() {
  sessionStorage.setItem(KEY, JSON.stringify(state));
}

export function setField(id, value) {
  state.fields[id] = value;
  save();
}

export function setArticleStatus(id, status) {
  state.articles[id] = status;
  save();
}

export function setIntent(id, text) {
  state.intents[id] = text;
  save();
}

export const getArticles = () =>
  ARTICLES.map((a) => {
    const entered = state.intents[a.id];
    return {
      ...a,
      status: state.articles[a.id] ?? a.status,
      intent: a.intent ?? (entered || null),
      intentRef: a.intent ? a.intentRef : entered ? "Entered by applicant · verify against the code appendix" : null,
    };
  });

export const processFields = () => PROCESS_FIELD_DEFS.map((f) => ({ ...f, value: state.fields[f.id] || null }));

export const STATUS_META = {
  confirmed: { label: "Confirmed", dot: "done" },
  pending: { label: "Pending", dot: "pending" },
  "needs-clarification": { label: "Needs clarification", dot: "warning" },
  rejected: { label: "Rejected", dot: "blocking" },
};

export function articleCounts(articles = getArticles()) {
  const c = { all: articles.length, confirmed: 0, pending: 0, "needs-clarification": 0, rejected: 0 };
  articles.forEach((a) => (c[a.status] += 1));
  return c;
}

export const unconfirmedArticles = (articles = getArticles()) =>
  articles.filter((a) => a.status !== "confirmed" && a.status !== "rejected");

export const sectionCArticles = (articles = getArticles()) => articles.filter((a) => a.status !== "rejected");

const blank = (v) => !String(v ?? "").trim();

/** Derived gap list — the only list any surface may render. */
export function getGaps(articles = getArticles(), f = state.fields) {
  const gaps = [];
  const need = (id, label, href) => blank(f[id]) && gaps.push({ id, severity: "blocking", label, href });
  need("rep", "Representative missing", "01-intake.html#rep");
  need("mail", "Mailing address missing", "01-intake.html#mail");
  need("muni", "Municipal address missing", "01-intake.html#muni");
  need("juris", "Jurisdiction-wide variance not answered", "01-intake.html#juris");
  need("risk", "Risk assessment empty (alternative path)", "01-intake.html#risk");
  need("assumptions", "Assumptions / limits empty (alternative path)", "01-intake.html#assumptions");
  if (!f.ownerConfirmed) {
    gaps.push({
      id: "owner",
      severity: "warning",
      label: "Owner inferred from upload — confirm",
      href: "01-intake.html#owner",
    });
  }
  const unconfirmed = unconfirmedArticles(articles);
  if (unconfirmed.length) {
    gaps.push({
      id: "confirm",
      severity: "blocking",
      label: `Article${unconfirmed.length > 1 ? "s" : ""} not confirmed: ${unconfirmed.map((a) => a.id).join(", ")}`,
      href: "02-article-ranking.html",
    });
  }
  sectionCArticles(articles)
    .filter((a) => !a.intent)
    .forEach((a) =>
      gaps.push({ id: `intent-${a.id}`, severity: "blocking", label: `Section C intent empty for ${a.id}`, href: "03-section-c.html" })
    );
  sectionD()
    .filter((d) => !d.uploaded)
    .forEach((d) =>
      gaps.push({ id: `evidence-${d.id}`, severity: "warning", label: `Evidence not uploaded: ${d.short}`, href: "06-evidence-plan.html" })
    );
  if (f.atsAssumption) {
    gaps.push({ id: "ats", severity: "warning", label: "ATS legal description marked assumption — verify", href: "01-intake.html#ats" });
  }
  return gaps;
}

export const blockingGaps = (articles) => getGaps(articles).filter((g) => g.severity === "blocking");
export const hasBlockingGaps = (articles) => blockingGaps(articles).length > 0;

export function gapSummary(articles) {
  const gaps = getGaps(articles);
  const b = gaps.filter((g) => g.severity === "blocking").length;
  return `${b} blocking · ${gaps.length - b} warning`;
}

const dotClass = (g) => (g.severity === "blocking" ? "blocking" : "warning");

export function renderGapStrip(el, articles) {
  if (!el) return;
  const gaps = getGaps(articles);
  el.hidden = gaps.length === 0;
  el.innerHTML = gaps
    .map((g) => `<a class="gap-chip" href="${g.href}"><span class="status-dot ${dotClass(g)}"></span>${g.label}</a>`)
    .join("");
}

/** `links: false` for reviewer surfaces, where gaps are reported rather than fixed. */
export function renderGapList(el, { articles, links = true } = {}) {
  if (!el) return;
  const gaps = getGaps(articles);
  el.innerHTML = gaps.length
    ? gaps
        .map((g) => {
          const inner = `<span class="status-dot ${dotClass(g)}"></span><span>${g.label}</span>`;
          return links
            ? `<li><a class="gap-item" href="${g.href}">${inner}</a></li>`
            : `<li class="gap-item">${inner}</li>`;
        })
        .join("")
    : `<li class="gap-item"><span class="status-dot done"></span><span>No administrative gaps</span></li>`;
}

export function statusPill(status) {
  const m = STATUS_META[status];
  return `<span class="label-pill" data-status="${status}"><span class="status-dot ${m.dot}"></span>${m.label}</span>`;
}

export function applyGating(articles) {
  const n = blockingGaps(articles).length;
  document.querySelectorAll("[data-requires-no-blocking-gaps]").forEach((btn) => {
    btn.disabled = n > 0;
    btn.title = n ? `Resolve ${n} blocking gaps first` : "";
  });
  return n;
}

const ICONS = {
  intake: '<rect x="2" y="3" width="12" height="10" rx="1.5"/><path d="M5 6.5h6M5 9.5h4"/>',
  ranking: '<path d="M6 4L3 8l3 4M10 4l3 4-3 4"/>',
  sectionC: '<path d="M3 4h10M3 8h10M3 12h6"/>',
  evidence: '<path d="M4 3h6l3 3v7H4V3z"/><path d="M10 3v3h3"/>',
  export: '<path d="M8 3v7M5.5 7.5 8 10l2.5-2.5M3 13h10"/>',
  review: '<circle cx="8" cy="8" r="5"/><path d="M8 5.5v3l2 1"/>',
  person: '<circle cx="8" cy="6" r="2.5"/><path d="M3.5 13c1-2.5 2.8-3.5 4.5-3.5S11.5 10.5 12.5 13"/>',
  project: '<rect x="3" y="3" width="10" height="10" rx="2"/>',
};

const icon = (k) => `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">${ICONS[k]}</svg>`;

const APPLICANT_NAV = [
  ["intake", "Intake", "01-intake.html", "intake"],
  ["ranking", "Code identification", "02-article-ranking.html", "ranking"],
  ["sectionC", "Section C", "03-section-c.html", "sectionC"],
  ["evidence", "Evidence plan", "06-evidence-plan.html", "evidence"],
  ["export", "Export", "05-export.html", "export"],
];

const SCO_NAV = [["review", "Administrative review", "04-sco-review.html", "review"]];

export function renderShell(active, role = "applicant") {
  const el = document.querySelector("[data-shell]");
  if (!el) return;
  const nav = (role === "sco" ? SCO_NAV : APPLICANT_NAV)
    .map(
      ([id, label, href, ic]) =>
        `<a class="nav-item${id === active ? " active" : ""}" href="${href}"${id === active ? ' aria-current="page" data-active="true"' : ""}>${icon(ic)}${label}</a>`
    )
    .join("");
  const meta =
    role === "sco"
      ? `<div class="sidebar-section-label">Role</div><div class="sidebar-meta">${icon("person")}Safety Codes Officer</div>`
      : `<div class="sidebar-section-label">Project</div><div class="sidebar-meta" data-project-label>${icon("project")}${PROJECT_LABEL}</div>`;
  el.innerHTML = `<div class="workspace">Batatis</div><nav class="nav-group" aria-label="Workflow">${nav}</nav><div>${meta}</div>`;
}

export function wireTabs(selector, panelAttr, onChange) {
  const tabs = [...document.querySelectorAll(selector)];
  const key = selector.match(/data-([a-z-]+)/)[1].replace(/-([a-z])/g, (_, c) => c.toUpperCase());
  const select = (tab) => {
    tabs.forEach((t) => {
      const on = t === tab;
      t.classList.toggle("active", on);
      t.dataset.active = String(on);
      t.setAttribute("aria-selected", String(on));
      t.tabIndex = on ? 0 : -1;
    });
    document.querySelectorAll(`[${panelAttr}]`).forEach((p) => {
      p.dataset.active = String(p.getAttribute(panelAttr) === tab.dataset[key]);
    });
    onChange?.(tab.dataset[key]);
  };
  tabs.forEach((t) => {
    t.setAttribute("role", "tab");
    t.addEventListener("click", () => select(t));
  });
  return (value) => select(tabs.find((t) => t.dataset[key] === value) || tabs[0]);
}

export function downloadText(filename, text) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
