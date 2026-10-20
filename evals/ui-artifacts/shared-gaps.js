/**
 * Single source of truth for VAR-1042 demo surfaces.
 * Article confirmation status + administrative gaps are derived here so every
 * surface (intake, ranking, Section C, SCO, export) shows the same list.
 */
export const PROJECT_ID = "VAR-1042";
export const PROJECT_LABEL = "VAR-1042 · Straw wall";

/** @typedef {'confirmed'|'pending'|'needs-clarification'|'rejected'} ArticleStatus */

/**
 * Section C attribution data — one object feeds the B03 table and the B05 preview.
 * @type {{ id: string, title: string, rank: number, benchmark: boolean, status: ArticleStatus,
 *   objective: string, fn: string, intent: string|null, intentRef: string|null, excerpt: string }[]}
 */
export const ARTICLES = [
  {
    id: "9.25.2.1.",
    title: "Thermal insulation · exterior walls",
    rank: 1,
    benchmark: true,
    status: "pending",
    objective: "OH1 / OS2",
    fn: "F51 / F20",
    intent: "Limit heat loss through the building envelope so indoor conditions stay acceptable to occupants.",
    intentRef: "A-192",
    excerpt:
      "9.25.2.1. Required Insulation — All walls, ceilings and floors separating conditioned space from unconditioned space or exterior air shall be provided with thermal insulation conforming to…",
  },
  {
    id: "9.25.3.1.",
    title: "Air barrier system",
    rank: 2,
    benchmark: false,
    status: "needs-clarification",
    objective: "OH1",
    fn: "F55",
    intent: null,
    intentRef: null,
    excerpt: "9.25.3.1. Air Barrier Systems — An air barrier system shall be installed to control air leakage…",
  },
];

/** Alternative-path process fields (values, not status words). */
export const PROCESS_FIELDS = [
  { id: "risk", label: "Risk assessment", value: null },
  {
    id: "mitigation",
    label: "Mitigating measures",
    value: "Lime plaster both faces; moisture monitoring at sill plates for the first two heating seasons.",
  },
  { id: "assumptions", label: "Assumptions / limits", value: null },
];

export const STATUS_META = {
  confirmed: { label: "Confirmed", dot: "done" },
  pending: { label: "Pending", dot: "pending" },
  "needs-clarification": { label: "Needs clarification", dot: "warning" },
  rejected: { label: "Rejected", dot: "blocking" },
};

const BASE_GAPS = [
  { id: "rep", severity: "blocking", label: "Representative missing" },
  { id: "mail", severity: "blocking", label: "Mailing address missing" },
  { id: "muni", severity: "blocking", label: "Municipal address missing" },
  { id: "risk", severity: "blocking", label: "Risk assessment empty (alternative path)" },
  { id: "assumptions", severity: "blocking", label: "Assumptions / limits empty (alternative path)" },
];

export function articleCounts(articles = ARTICLES) {
  const c = { all: articles.length, confirmed: 0, pending: 0, "needs-clarification": 0, rejected: 0 };
  articles.forEach((a) => (c[a.status] += 1));
  return c;
}

/** Derived gap list — the only list any surface may render. */
export function getGaps(articles = ARTICLES) {
  const gaps = [...BASE_GAPS];
  const unconfirmed = unconfirmedArticles(articles);
  if (unconfirmed.length) {
    gaps.push({
      id: "confirm",
      severity: "blocking",
      label: `Article${unconfirmed.length > 1 ? "s" : ""} not confirmed: ${unconfirmed.map((a) => a.id).join(", ")}`,
    });
  }
  articles
    .filter((a) => a.status !== "rejected" && !a.intent)
    .forEach((a) => gaps.push({ id: `intent-${a.id}`, severity: "blocking", label: `Section C intent empty for ${a.id}` }));
  gaps.push({ id: "ats-assumption", severity: "warning", label: "ATS legal description marked assumption — verify" });
  return gaps;
}

export const blockingGaps = (articles = ARTICLES) => getGaps(articles).filter((g) => g.severity === "blocking");
export const hasBlockingGaps = (articles = ARTICLES) => blockingGaps(articles).length > 0;

export function gapSummary(articles = ARTICLES) {
  const gaps = getGaps(articles);
  const b = gaps.filter((g) => g.severity === "blocking").length;
  const w = gaps.length - b;
  return `${b} blocking · ${w} warning`;
}

export const unconfirmedArticles = (articles = ARTICLES) =>
  articles.filter((a) => a.status !== "confirmed" && a.status !== "rejected");

const dotClass = (g) => (g.severity === "blocking" ? "blocking" : "warning");

export function renderGapStrip(el, articles = ARTICLES) {
  if (!el) return;
  el.innerHTML = getGaps(articles)
    .map((g) => `<span class="gap-chip"><span class="status-dot ${dotClass(g)}"></span>${g.label}</span>`)
    .join("");
}

export function renderGapList(el, articles = ARTICLES) {
  if (!el) return;
  el.innerHTML = getGaps(articles)
    .map((g) => `<li class="gap-item"><span class="status-dot ${dotClass(g)}"></span><span>${g.label}</span></li>`)
    .join("");
}

export function statusPill(status) {
  const m = STATUS_META[status];
  return `<span class="label-pill" data-status="${status}"><span class="status-dot ${m.dot}"></span>${m.label}</span>`;
}

export function applyGating(articles = ARTICLES) {
  document.querySelectorAll("[data-requires-no-blocking-gaps]").forEach((btn) => {
    const blocked = hasBlockingGaps(articles);
    btn.disabled = blocked;
    btn.setAttribute("aria-disabled", String(blocked));
    btn.title = blocked ? "Blocked while administrative gaps remain" : "";
  });
}

export function renderProjectLabel() {
  document.querySelectorAll("[data-project-label]").forEach((el) => (el.textContent = PROJECT_LABEL));
}
