import { useLayoutEffect, useRef, useState } from "react";
import { AUTHORITIES, authorityUnsure, officeChoiceAction, officeSuggestion } from "../config";
import { sourceLine } from "../intakeView";
import { DETAIL_FIELDS, factFor, valueText } from "../model";
import { useCase } from "../store";
import { AuthorityPicker } from "./AuthorityPicker";
import { DatePicker } from "./DatePicker";
import type { DeckItem } from "./deck";
import { cleanReadValue, clearJourneyAnswerAction, journeyAnswerAction, journeyAnswers } from "./journey";
import { Icon24 } from "./icons";
import { JurisdictionNote } from "./JurisdictionNote";
import type { useDeckExtras } from "./useDeckExtras";

type RowDraft = { kind: "answer"; value: string; defaulted?: boolean } | { kind: "later" | "not_sure" };

/** Edits and defaults belong to this sheet until the applicant presses Done. */
export function PaperworkSheet({ item, focusRow, onDone, extras }: { item: DeckItem; focusRow: string | null; onDone: () => void; extras: ReturnType<typeof useDeckExtras>["extras"] }) {
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
  const answer = (key: string, value: string, defaulted = false) => setDrafts((draft) => ({ ...draft, [key]: { kind: "answer", value, defaulted } }));

  function save() {
    for (const row of rows) {
      const draft = drafts[row.key];
      if (!draft) continue;
      for (const previous of journeyAnswers(c).values()) {
        if (previous.stage === "paperwork" && previous.field === row.ref) dispatch(clearJourneyAnswerAction({ ...row, key: previous.key }));
      }
      if (draft.kind !== "answer") {
        if (row.kind === "authority") {
          dispatch({ type: "setAuthority", authority: "" });
          dispatch(officeChoiceAction("unsure"));
        } else dispatch({ type: "setDetail", field: row.ref, value: "", section: row.section });
        dispatch(journeyAnswerAction(row, draft.kind));
      } else {
        dispatch(clearJourneyAnswerAction(row));
        if (row.kind === "authority") {
          dispatch({ type: "setAuthority", authority: draft.value });
          dispatch(officeChoiceAction(draft.value));
        } else dispatch({ type: "setDetail", field: row.ref, value: draft.value.trim(), section: row.section });
      }
    }
    setDrafts({});
    onDone();
  }

  return <form ref={root} className="cf-paperwork" aria-label="Last details for the form" onSubmit={(e) => { e.preventDefault(); save(); }}>
    <div className="cf-paperwork-rows">{rows.map((row) => {
      const draft = drafts[row.key];
      const fact = factFor(c, row.kind === "authority" ? "office.choice" : row.ref);
      const saved = row.kind === "authority" ? c.authority : cleanReadValue(valueText(fact));
      const value = draft?.kind === "answer" ? draft.value : draft ? "" : saved;
      const deferred = draft && draft.kind !== "answer" ? draft.kind : !draft ? row.deferred ?? (row.settled ? "not_sure" : undefined) : undefined;
      const field = DETAIL_FIELDS.find((field) => field.id === row.ref);
      const choices = row.choices ?? Object.entries(field?.options ?? {}).map(([value, label]) => ({ value, label }));
      const legacyRoles: Record<string, string> = { homebuilder: "Builder or contractor", builder: "Builder or contractor", "architect-engineer": "Architect or engineer" };
      const choiceLabel = choices.find((choice) => choice.value === value)?.label ?? (row.ref === "applicant_role" ? legacyRoles[value] : undefined) ?? value.trim();
      const label = row.kind === "authority" ? "Office" : row.title;
      const source = fact ? sourceLine(c, fact) : "";
      const assumed = fact?.kind === "computed" || fact?.kind === "proposed" || (!fact && row.assumed);
      const sourceChip = !draft && saved && (fact || row.kind === "authority") ? <span className={`cf-source-chip${assumed ? " is-assumed" : ""}`}>{assumed ? "assumed" : fact?.source.type === "file" ? source : "you"}</span> : draft?.kind === "answer" && value ? <span className={`cf-source-chip${draft.defaulted ? " is-assumed" : ""}`}>{draft.defaulted ? "default" : "you"}</span> : null;
      const choose = (picked: string, defaulted = false) => answer(row.key, picked, defaulted);
      const ownerDraft = drafts["field-owner"];
      const owner = ownerDraft?.kind === "answer" ? ownerDraft.value.trim() : ownerDraft ? "" : cleanReadValue(valueText(factFor(c, "owner")));
      const siteDraft = drafts["field-municipalAddress"];
      const site = siteDraft?.kind === "answer" ? siteDraft.value.trim() : siteDraft ? "" : cleanReadValue(valueText(factFor(c, "municipalAddress")));
      const suggestions = row.ref === "representative" ? [{ label: "No representative", value: "No representative" }, ...(owner ? [{ label: "Same as the owner", value: owner }] : [])]
        : row.ref === "mailingAddress" && site ? [{ label: "Same as the site address", value: site }]
          : row.ref === "date" && row.suggestedValue ? [{ label: "Today", value: row.suggestedValue }] : [];
      return <div key={row.key} className="cf-paperwork-row" data-paperwork-row={row.key} role="group" aria-label={label}>
        <div className="cf-paperwork-label"><span>{label}</span>{row.optional && <span className="cf-faint">Optional</span>}</div>
        <div className="cf-paperwork-control">
          {row.kind === "authority" ? <>
            <AuthorityPicker options={AUTHORITIES} value={value} unsure={Boolean(deferred || (!draft && authorityUnsure(c)))} suggested={officeSuggestion(c)} label="Office" onPick={(picked) => picked === "unsure" ? setDrafts((draft) => ({ ...draft, [row.key]: { kind: "not_sure" } })) : choose(picked)} />
            {value && <JurisdictionNote authority={value} unsure={Boolean(deferred)} extras={extras} />}
          </> : choices.length > 0 ? <details className="cf-paperwork-choice">
            <summary aria-label={`${label}: ${choiceLabel || "Choose…"}`}>
              <span>{choiceLabel || "Choose…"}</span><Icon24 name="down" size={14} />
            </summary>
            <div className="cf-paperwork-options">{choices.map((choice) => <button type="button" key={choice.value} className="cf-link-btn" aria-pressed={value === choice.value} onClick={(e) => { choose(choice.value); e.currentTarget.closest("details")?.removeAttribute("open"); }}>{choice.label}</button>)}</div>
          </details> : row.ref === "date" ? <DatePicker id={row.key} label={label} value={value} onChange={choose} />
            : <input id={row.key} type="text" className="cf-paperwork-input" aria-label={label} value={value} onChange={(e) => choose(e.target.value)} />}
          {(sourceChip || deferred) && <div className="cf-paperwork-source">{sourceChip}{deferred && <span className="cf-source-chip">{deferred === "later" ? "Later" : "Not sure"}</span>}</div>}
          {!value && !deferred && suggestions.length > 0 && <div className="cf-paperwork-defaults">{suggestions.map((suggestion) => <button key={suggestion.label} type="button" className="cf-link-btn" onClick={() => choose(suggestion.value, true)}>{suggestion.label} <span className="cf-source-chip is-assumed">default</span></button>)}</div>}
        </div>
        <button type="button" className="cf-link-btn cf-paperwork-later" aria-label={`Later: ${label}`} aria-pressed={deferred === "later"} onClick={() => setDrafts((draft) => ({ ...draft, [row.key]: { kind: "later" } }))}>Later</button>
      </div>;
    })}</div>
    <div className="cf-ok-row" data-deck-foot><button type="submit" className="cf-btn is-primary is-lg">Done <Icon24 name="check" size={16} /></button></div>
  </form>;
}
