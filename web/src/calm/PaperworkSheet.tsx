import { useLayoutEffect, useRef, useState } from "react";
import { AUTHORITIES, authorityUnsure, officeChoiceAction, officeCoverage, officeSuggestion } from "../config";
import { localField } from "../intakeFields";
import { legalFromFacts, sourceLine } from "../intakeView";
import { DETAIL_FIELDS, factFor, valueText } from "../model";
import { useCase } from "../store";
import { AuthorityPicker } from "./AuthorityPicker";
import { DatePicker } from "./DatePicker";
import type { DeckItem } from "./deck";
import { cleanReadValue, clearJourneyAnswerAction, itemOpen, journeyAnswerAction, journeyAnswers } from "./journey";
import { Icon24 } from "./icons";
import { Dot } from "./ui";
import type { useDeckExtras } from "./useDeckExtras";

/** The form field a row edits: a planner question carries its own id, the field lives on the question. */
const fieldOf = (row: DeckItem): string => (row.plan ? localField(row.plan.field) : row.ref);

/** Three small groups instead of one long list; anything unlisted joins the last group. */
const GROUPS = [
  { name: "People", fields: ["owner", "applicant_role", "representative", "mailingAddress"] },
  { name: "Site", fields: ["municipalAddress", "legalDescription", "authority", "scope"] },
  { name: "Request", fields: ["date", "permit"] },
];
const SHORT_LABEL: Record<string, string> = { applicant_role: "Your part", scope: "Sites covered", date: "Request date", permit: "Permit number" };

type RowDraft = { kind: "answer"; value: string; defaulted?: boolean } | { kind: "later" | "not_sure" };

/** Under Office: where Batatis has not checked the office's own steps (everywhere but Calgary and Edmonton), it says it stops, and who to ask. */
function officeLine(value: string) {
  const office = officeCoverage(value);
  return office && !office.covered ? <p className="cf-pw-office"><Dot tone="warning" />Batatis doesn’t prepare applications here. {office.ask}</p> : null;
}

/** Edits and defaults belong to this sheet until the applicant presses Done. */
export function PaperworkSheet({ item, focusRow, onDone }: { item: DeckItem; focusRow: string | null; onDone: () => void; extras?: ReturnType<typeof useDeckExtras>["extras"] }) {
  const { c, dispatch } = useCase();
  const [drafts, setDrafts] = useState<Record<string, RowDraft>>({});
  const root = useRef<HTMLFormElement>(null);
  const rows = item.paperworkRows ?? [];
  useLayoutEffect(() => {
    const row = focusRow ? Array.from(root.current?.querySelectorAll<HTMLElement>("[data-paperwork-row]") ?? []).find((el) => el.dataset.paperworkRow === focusRow) : null;
    const target = row ?? root.current;
    target?.querySelector<HTMLElement>("input, button, summary, textarea")?.focus({ preventScroll: true });
    row?.scrollIntoView({ block: "nearest" });
  }, [focusRow]);
  // A legal description read as lot, block and plan parts is shown joined, as the form writes it.
  const savedValue = (id: string) => cleanReadValue(valueText(factFor(c, id)))
    || (id === "legalDescription" ? legalFromFacts(c.facts) : "");
  const answer = (key: string, value: string, defaulted = false) => setDrafts((draft) => ({ ...draft, [key]: { kind: "answer", value, defaulted } }));

  function save() {
    for (const row of rows) {
      const draft = drafts[row.key];
      if (!draft) continue;
      for (const previous of journeyAnswers(c).values()) {
        if (previous.stage === "paperwork" && (previous.field === row.ref || previous.field === fieldOf(row))) dispatch(clearJourneyAnswerAction({ ...row, key: previous.key }));
      }
      if (draft.kind !== "answer") {
        if (row.kind === "authority") {
          dispatch({ type: "setAuthority", authority: "" });
          dispatch(officeChoiceAction("unsure"));
        } else dispatch({ type: "setDetail", field: fieldOf(row), value: "", section: row.section });
        dispatch(journeyAnswerAction(row, draft.kind));
      } else {
        dispatch(clearJourneyAnswerAction(row));
        if (row.kind === "authority") {
          dispatch({ type: "setAuthority", authority: draft.value });
          dispatch(officeChoiceAction(draft.value));
        } else dispatch({ type: "setDetail", field: fieldOf(row), value: draft.value.trim(), section: row.section });
      }
    }
    setDrafts({});
    onDone();
  }

  const groupOf = (row: DeckItem) => GROUPS.findIndex((g) => g.fields.includes(row.kind === "authority" ? "authority" : fieldOf(row)));
  const grouped = GROUPS.map((g, n) => ({ ...g, rows: rows.filter((row) => (groupOf(row) < 0 ? GROUPS.length - 1 : groupOf(row)) === n) })).filter((g) => g.rows.length);

  function renderRow(row: DeckItem) {
    const draft = drafts[row.key];
    const field = fieldOf(row);
    const fact = factFor(c, row.kind === "authority" ? "office.choice" : field) ?? (field === "legalDescription" ? factFor(c, "lot") ?? factFor(c, "plan") : undefined);
    const saved = row.kind === "authority" ? c.authority : savedValue(field);
    const value = draft?.kind === "answer" ? draft.value : draft ? "" : saved;
    const deferred = draft && draft.kind !== "answer" ? draft.kind : !draft ? row.deferred ?? (row.settled ? "not_sure" : undefined) : undefined;
    const detail = DETAIL_FIELDS.find((d) => d.id === field);
    const choices = row.choices ?? Object.entries(detail?.options ?? {}).map(([value, label]) => ({ value, label }));
    const legacyRoles: Record<string, string> = { homebuilder: "Builder or contractor", builder: "Builder or contractor", "architect-engineer": "Architect or engineer" };
    const choiceLabel = choices.find((choice) => choice.value === value)?.label ?? (field === "applicant_role" ? legacyRoles[value] : undefined) ?? value.trim();
    const label = row.kind === "authority" ? "Office" : SHORT_LABEL[field] ?? row.title;
    const choose = (picked: string, defaulted = false) => answer(row.key, picked, defaulted);
    const current = (id: string) => {
      const other = rows.find((r) => fieldOf(r) === id);
      const d = other ? drafts[other.key] : undefined;
      return d?.kind === "answer" ? d.value.trim() : d ? "" : savedValue(id);
    };
    const owner = current("owner");
    const site = current("municipalAddress");
    const office = row.kind === "authority" ? officeSuggestion(c) : null;
    const suggestions = field === "representative" ? [{ label: "No representative", value: "No representative" }, ...(owner ? [{ label: "Same as the owner", value: owner }] : [])]
      : field === "mailingAddress" && site ? [{ label: "Same as the site address", value: site }]
        : field === "date" && row.suggestedValue ? [{ label: "Today", value: row.suggestedValue }]
          : field === "scope" && site ? [{ label: "One building site", value: "site" }]
            : office ? [{ label: office.name, value: office.id }] : [];
    // Only a value read from a file says where it came from; the applicant's own answers need no badge.
    const fromFile = !draft && saved && fact?.source.type === "file" ? sourceLine(c, fact) : "";
    const placeholder = deferred === "later" ? "Later" : deferred ? "Not sure" : row.optional ? "Optional" : "Add";
    return <div key={row.key} className={`cf-pw-row${value ? "" : " is-empty"}`} data-paperwork-row={row.key} data-open={!row.optional && itemOpen(row) ? "" : undefined} role="group" aria-label={label}>
      <span className="cf-pw-label">{label}</span>
      <div className="cf-pw-value">
        {row.kind === "authority"
          ? <AuthorityPicker compact options={AUTHORITIES} value={value} unsure={Boolean(deferred || (!draft && authorityUnsure(c)))} label="Office" onPick={(picked) => picked === "unsure" ? setDrafts((d) => ({ ...d, [row.key]: { kind: "not_sure" } })) : choose(picked)} />
          : choices.length > 0 ? <details className="cf-pw-choice">
            <summary aria-label={`${label}: ${choiceLabel || placeholder}`}>
              <span className={choiceLabel ? "" : "cf-pw-placeholder"}>{choiceLabel || placeholder}</span><Icon24 name="down" size={14} />
            </summary>
            <div className="cf-pw-options">{choices.map((choice) => <button type="button" key={choice.value} className="cf-link-btn" aria-pressed={value === choice.value} onClick={(e) => { choose(choice.value); e.currentTarget.closest("details")?.removeAttribute("open"); }}>{choice.label}</button>)}</div>
          </details>
          : field === "date" ? <DatePicker id={row.key} label={label} value={value} onChange={choose} />
            : <input id={row.key} type="text" className="cf-pw-input" aria-label={label} placeholder={placeholder} value={value} onChange={(e) => choose(e.target.value)} />}
        {row.kind === "authority" && !deferred && officeLine(value)}
        {!value && !deferred && suggestions.length > 0 && <div className="cf-pw-suggest">{suggestions.map((s) => <button key={s.label} type="button" className="cf-link-btn" onClick={() => choose(s.value, true)}>{s.label}</button>)}</div>}
      </div>
      <span className="cf-pw-end">
        {fromFile ? <span className="cf-pw-source" title={fromFile}><Icon24 name="file" size={14} /><span className="cf-sr">From {fromFile}</span></span>
          : !value && !deferred ? <button type="button" className="cf-link-btn cf-pw-later" aria-label={`Later: ${label}`} aria-pressed={deferred === "later"} onClick={() => setDrafts((d) => ({ ...d, [row.key]: { kind: "later" } }))}>Later</button> : null}
      </span>
    </div>;
  }

  return <form ref={root} className="cf-paperwork" aria-label="Last details for the form" onSubmit={(e) => { e.preventDefault(); save(); }}>
    {grouped.map((g) => <section key={g.name} className="cf-pw-group" aria-label={g.name}>
      <h3 className="cf-pw-group-h">{g.name}</h3>
      {g.rows.map(renderRow)}
    </section>)}
    <div className="cf-ok-row" data-deck-foot><button type="submit" className="cf-btn is-primary is-lg">Done <Icon24 name="check" size={16} /></button></div>
  </form>;
}
