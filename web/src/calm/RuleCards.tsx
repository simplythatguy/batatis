/**
 * Coded-rule pieces for the deck (docs/api/rules.md): the numbers a result used and where each came
 * from, the quiet "not yet reviewed" line, and "Show the code" with the sentence, how Batatis compared
 * it and what it did not check. A result is a departure flag, never a finding about the design.
 */
import { useId, useState } from "react";
import { useProvisionText } from "../api/sectionC";
import { NrcCredit } from "../components";
import type { RuleIndex } from "../rules/evaluate";
import { DEPARTS_NEXT, NOT_REVIEWED, numbersUsed, plainLabel, valueWithUnit, type ShownRule } from "./rulesView";
import { codeHref } from "./routes";
import { CIcon, Dot } from "./ui";

/** The rule's sentence (verbatim from the code database), the comparison and what was not checked. */
function RuleCode({ rule }: { rule: ShownRule }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const text = useProvisionText(open ? rule.provision.id : undefined);
  const computed = rule.computed.filter((x) => x.value !== null && typeof x.value !== "boolean");
  return (
    <div className="cf-showcode">
      <button type="button" className="cf-link-btn cf-showcode-toggle" aria-expanded={open} aria-controls={id} onClick={() => setOpen((v) => !v)}>
        <CIcon name="doc" size={14} />{open ? "Hide the code" : "Show the code"}
      </button>
      {open && (
        <div id={id} className="cf-codebox">
          <div className="cf-codebox-head">
            <span className="cf-mono">{rule.provision.id}</span>
            <span className="cf-codebox-title">{rule.title}</span>
          </div>
          {text.state === "live" ? (
            <blockquote className="cf-code-text">{text.text}</blockquote>
          ) : (
            <p className="cf-faint">{text.state === "error" ? "The wording did not load." : "Loading the code text…"}</p>
          )}
          <div className="cf-code-src">{rule.provision.citation} · Code text, verbatim · <NrcCredit /></div>
          <div className="cf-rule-how">
            <p className="cf-rule-how-h">How Batatis compared it</p>
            <p>{rule.message}</p>
            {rule.next_step && <p>{rule.next_step}</p>}
            {computed.length > 0 && (
              <dl className="cf-rule-calc">
                {computed.map((x) => [
                  <dt key={`${x.name}-k`}>{x.label}</dt>,
                  <dd key={`${x.name}-v`}>{valueWithUnit(x.value, x.unit)}</dd>,
                ])}
              </dl>
            )}
            {rule.assumptions.length > 0 && <p className="cf-faint">Assumed: {rule.assumptions.join(" ")}</p>}
          </div>
          {rule.not_checked.length > 0 && (
            <details className="cf-rule-notchecked">
              <summary>Not checked by this rule ({rule.not_checked.length})</summary>
              <ul>{rule.not_checked.map((n) => <li key={n}>{n}</li>)}</ul>
            </details>
          )}
          <div className="cf-codebox-links">
            <a className="cf-link-btn" href={codeHref(rule.article)}>Open in the code library <CIcon name="arrow" size={13} /></a>
          </div>
        </div>
      )}
    </div>
  );
}

/** A follows/departs result: the numbers, the next step for a departure, and Show the code. */
export function RuleResultView({ rule, index, onCard = false }: { rule: ShownRule; index: RuleIndex; onCard?: boolean }) {
  const rows = numbersUsed(rule, index);
  const unconfirmed = rule.unconfirmed_inputs.map((f) => (index.inputs[f] ? plainLabel(f, index.inputs[f].label) : f).toLowerCase());
  const departs = rule.state === "departs";
  return (
    <div className={`cf-rule${onCard ? " is-on-card" : ""}`}>
      {onCard && (
        <p className="cf-rule-lead">
          <Dot tone={departs ? "warning" : "done"} />
          <span>Batatis compared your numbers: {departs ? "this departs from the code’s standard way." : "this follows the code’s standard way."}</span>
        </p>
      )}
      {rows.length > 0 && (
        <dl className="cf-rule-nums" aria-label="The numbers used">
          {rows.map((r) => (
            <div key={r.label} className={`cf-rule-num${r.muted ? " is-limit" : ""}`}>
              <dt>{r.label}</dt>
              <dd><b>{r.value}</b>{r.origin && <span className="cf-faint"> · {r.origin}</span>}</dd>
            </div>
          ))}
        </dl>
      )}
      {rows.others && rows.others.length > 0 && (
        <details className="cf-rule-notchecked">
          <summary>Your other answers it used ({rows.others.length})</summary>
          <ul>{rows.others.map((r) => <li key={r.label}>{r.label}: <b>{r.value}</b>{r.origin && <span className="cf-faint"> · {r.origin}</span>}</li>)}</ul>
        </details>
      )}
      {unconfirmed.length > 0 && (
        <p className="cf-note"><Dot tone="warning" />Based on {unconfirmed.length === 1 ? "a value" : "values"} you haven’t confirmed yet: {unconfirmed.join(", ")}.</p>
      )}
      {departs && !onCard && <p className="cf-rule-next">{DEPARTS_NEXT}</p>}
      <RuleCode rule={rule} />
      <p className="cf-rule-review">{NOT_REVIEWED}</p>
    </div>
  );
}

/** A number a rule needs: the value with its unit, or Not sure. */
export function RuleNumberInput({ id, label, unit, draft, setDraft, unsure, onUnsure, note }: { id: string; label: string; unit?: string; draft: string; setDraft: (v: string) => void; unsure: boolean; onUnsure: () => void; note: string }) {
  return (
    <>
      <div className="cf-inline-answer">
        <label className="cf-sr" htmlFor={id}>{label}</label>
        <input id={id} className="cf-uline is-number" type="text" inputMode="decimal" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="e.g. 2.5" />
        {unit && <span className="cf-unit">{unit}</span>}
        <button type="button" className="cf-chip" aria-pressed={unsure} onClick={onUnsure}>Not sure</button>
      </div>
      {note && <p className="cf-note" role="alert"><Dot tone="warning" />{note}</p>}
      {!note && unsure && <p className="cf-note"><Dot tone="pending" />Saved as Not sure. The rule stays open and it is not asked again.</p>}
    </>
  );
}
