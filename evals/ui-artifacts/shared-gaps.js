/**
 * Single gap source for VAR-1042 demo surfaces (intake / SCO / export).
 * Keep lists identical across screens — Opus P0 #3.
 */
export const PROJECT_ID = "VAR-1042";

/** @typedef {{ id: string, severity: 'blocking'|'warning', label: string, section?: string }} Gap */

/** @type {Gap[]} */
export const GAPS = [
  { id: "rep", severity: "blocking", label: "Representative missing", section: "A" },
  { id: "mail", severity: "blocking", label: "Mailing address missing", section: "A" },
  { id: "muni", severity: "blocking", label: "Municipal address missing", section: "B" },
  { id: "risk", severity: "blocking", label: "Risk assessment empty (alternative path)", section: "process" },
  { id: "assumptions", severity: "blocking", label: "Assumptions / limits empty (alternative path)", section: "process" },
  { id: "intent-92531", severity: "blocking", label: "Section C intent empty for 9.25.3.1.", section: "C" },
  { id: "ats-assumption", severity: "warning", label: "ATS legal description marked assumption — verify", section: "B" },
];

export const blockingGaps = () => GAPS.filter((g) => g.severity === "blocking");
export const hasBlockingGaps = () => blockingGaps().length > 0;

export function renderGapStrip(el) {
  if (!el) return;
  el.innerHTML = GAPS.map(
    (g) =>
      `<span class="gap-chip"><span class="status-dot ${g.severity === "blocking" ? "blocking" : "warning"}"></span>${g.label}</span>`
  ).join("");
}

export function renderGapList(el) {
  if (!el) return;
  el.innerHTML = GAPS.map(
    (g) =>
      `<li class="gap-item"><span class="status-dot ${g.severity === "blocking" ? "blocking" : "warning"}"></span><span>${g.label}</span></li>`
  ).join("");
}

export function applyGating() {
  document.querySelectorAll("[data-requires-no-blocking-gaps]").forEach((btn) => {
    if (hasBlockingGaps()) {
      btn.setAttribute("disabled", "true");
      btn.setAttribute("aria-disabled", "true");
      btn.title = "Blocked while administrative gaps remain";
    }
  });
}
