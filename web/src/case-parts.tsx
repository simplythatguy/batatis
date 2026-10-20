import { useState } from "react";
import { Icon, KindBadge, StatusBadge, StatusIcon } from "./components";
import { useDraft } from "./draft";
import { DETAIL_FIELDS, PROCESS_FIELDS, displayValue, factFor, factLabel, isTyped, valueText, type DetailField } from "./model";
import { useCase } from "./store";
import type { Fact, ProcessFieldId, Question, Source } from "./types";

function sourceLine(s: Source): string {
  const parts = [s.ref];
  if (s.page) parts.push(`p.${s.page}`);
  return parts.join(" · ");
}

function FactRow({ fact }: { fact: Fact }) {
  const { c, dispatch } = useCase();
  const pending = fact.status === "unconfirmed";
  const staleInputs =
    fact.kind === "computed" && (fact.inputs ?? []).some((id) => !c.facts.some((f) => f.id === id));
  const unconfirmedInputs =
    fact.kind === "computed" &&
    (fact.inputs ?? []).some((id) => c.facts.find((f) => f.id === id)?.status === "unconfirmed");
  return (
    <li className="fact" id={`fact-${fact.id}`} tabIndex={-1}>
      <div className="fact-head">
        {pending ? (
          <StatusIcon kind="unconfirmed" label="Not confirmed yet" />
        ) : (
          <StatusIcon kind="confirmed" label={fact.kind === "proposed" ? "Confirmed by you" : "Confirmed"} />
        )}
        <span className="fact-field">{factLabel(fact.field)}</span>
        <KindBadge fact={fact} />
      </div>
      <div className={`fact-value ${staleInputs ? "is-stale" : ""}`}>{displayValue(fact)}</div>
      {fact.formula && <div className="mono fact-formula">{fact.formula}</div>}
      {staleInputs && <div className="field-note">An input changed. The engine recomputes this when connected.</div>}
      {!staleInputs && unconfirmedInputs && (
        <div className="field-note">
          <StatusBadge kind="unconfirmed" size="sm" label="Not confirmed yet" text="Uses a value you have not confirmed yet" />
        </div>
      )}
      <div className="fact-source">
        <span className="meta">
          {fact.kind === "computed"
            ? `Worked out from ${(fact.inputs ?? []).map((id) => c.facts.find((f) => f.id === id)).filter(Boolean).map((f) => factLabel(f!.field).toLowerCase()).join(" and ") || "values that changed"}`
            : `From ${sourceLine(fact.source)}`}
        </span>
        {fact.source.quote && <q className="fact-quote">{fact.source.quote}</q>}
        {fact.kind === "proposed" && fact.confidence != null && (
          <span className="meta">Confidence {Math.round(fact.confidence * 100)}%</span>
        )}
      </div>
      {pending && (
        <div className="btn-row fact-actions">
          <button type="button" className="btn" aria-label={`Confirm ${factLabel(fact.field)}`} onClick={() => dispatch({ type: "confirmFact", id: fact.id })}>
            Confirm
          </button>
          <button type="button" className="btn btn-ghost" aria-label={`Not right: ${factLabel(fact.field)}`} onClick={() => dispatch({ type: "dismissFact", id: fact.id })}>
            Not right
          </button>
        </div>
      )}
    </li>
  );
}

/** All facts as one collapsed row; the model-checked line stays visible under it. */
export function FactLedger() {
  const { c } = useCase();
  const pending = c.facts.filter((f) => f.status === "unconfirmed").length;
  return (
    <details className="disclosure ledger">
      <summary>
        <Icon name="chevron" size={12} />
        <span className="disclosure-title">Facts</span>
        <span className="meta">{c.facts.length}</span>
        {pending > 0 ? (
          <StatusBadge kind="unconfirmed" size="sm" label={`${pending} facts still need your check`} text={pending} />
        ) : (
          c.facts.length > 0 && <StatusIcon kind="confirmed" size="sm" label="All confirmed" />
        )}
        <span className="meta summary-sub">Model-checked from your words. Nothing counts until you confirm.</span>
      </summary>
      {c.facts.length ? (
        <ul className="plain-list ledger-list">
          {c.facts.map((f) => (
            <FactRow key={f.id} fact={f} />
          ))}
        </ul>
      ) : (
        <p className="empty">No facts yet. Describe your idea or drop a file.</p>
      )}
    </details>
  );
}

function QuestionChip({ q }: { q: Question }) {
  const { dispatch } = useCase();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  if (q.answer) {
    return (
      <li className="chip is-answered" id={`q-${q.id}`} tabIndex={-1}>
        <span className="chip-q">
          <StatusIcon kind="confirmed" size="sm" label="Answered" />
          {q.text}
        </span>
        <span className="chip-why">You said: {q.answer}</span>
      </li>
    );
  }
  return (
    <li className="chip" data-open={open}>
      <button type="button" className="chip-button" id={`q-${q.id}`} aria-expanded={open} aria-controls={open ? `answer-${q.id}` : undefined} onClick={() => setOpen(!open)}>
        <span className="chip-q">{q.text}</span>
        <span className="chip-why">Why we ask: {q.why}</span>
      </button>
      {open && (
        <form
          id={`answer-${q.id}`}
          className="chip-answer"
          onSubmit={(e) => {
            e.preventDefault();
            if (text.trim()) dispatch({ type: "answerQuestion", id: q.id, answer: text.trim() });
          }}
        >
          <label className="sr-only" htmlFor={`qa-${q.id}`}>
            Your answer: {q.text}
          </label>
          <input id={`qa-${q.id}`} className="input" autoComplete="off" value={text} onChange={(e) => setText(e.target.value)} placeholder="Your answer" autoFocus />
          <button type="submit" className="btn" disabled={!text.trim()}>
            Save answer
          </button>
        </form>
      )}
    </li>
  );
}

export function QuestionChips() {
  const { c } = useCase();
  const qs = c.questions.slice(0, 5);
  const open = qs.filter((q) => !q.answer).length;
  return (
    <section aria-labelledby="questions-title">
      <div className="ledger-head">
        <h2 id="questions-title" className="section-title">
          A few questions
        </h2>
        {open > 0 ? (
          <StatusBadge kind="open-question" size="sm" label={`${open} open`} text={open} />
        ) : (
          <StatusIcon kind="confirmed" size="sm" label="All answered" />
        )}
      </div>
      <p className="meta questions-note">Not sure? It goes to the officer as an open question.</p>
      <ul className="plain-list chips">
        {qs.map((q) => (
          <QuestionChip key={q.id} q={q} />
        ))}
      </ul>
    </section>
  );
}

function DetailInput({ def }: { def: DetailField }) {
  const { c, dispatch } = useCase();
  const fact = factFor(c, def.id);
  const value = valueText(fact);
  const set = (v: string) => dispatch({ type: "setDetail", field: def.id, value: v, section: def.section });
  const draft = useDraft(value, set);
  const empty = def.required && !draft.value.trim();
  const id = `field-${def.id}`;
  return (
    <div className={`field ${def.multiline ? "full" : ""} ${empty ? "is-empty" : ""}`}>
      <div className="field-label-row">
        {empty && <StatusIcon kind="unconfirmed" size="sm" label="Missing" />}
        <label htmlFor={id}>{def.label}</label>
        {!def.required && <span className="meta optional">Optional</span>}
      </div>
      {def.options ? (
        <select id={id} autoComplete="off" value={value} onChange={(e) => set(e.target.value)} data-empty={!value}>
          <option value="">Select…</option>
          {Object.entries(def.options).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      ) : def.multiline ? (
        <textarea id={id} rows={3} autoComplete="off" value={draft.value} onChange={(e) => draft.onChange(e.target.value)} onBlur={draft.onBlur} />
      ) : (
        <input id={id} autoComplete="off" value={draft.value} onChange={(e) => draft.onChange(e.target.value)} onBlur={draft.onBlur} />
      )}
      <div className="field-foot">
        {fact && !isTyped(fact) ? (
          <span className="field-note">
            {fact.status === "confirmed" ? (
              <StatusIcon kind="confirmed" size="sm" label="Confirmed" />
            ) : (
              <StatusIcon kind="unconfirmed" size="sm" label="Not confirmed yet" />
            )}
            {fact.kind === "proposed" ? "Our guess, from" : "From"} {sourceLine(fact.source)}
            {fact.source.quote && <q className="field-quote">{fact.source.quote}</q>}
            {fact.status === "unconfirmed" && (
              <button type="button" className="btn btn-ghost btn-xs" aria-label={`Confirm ${def.label}`} onClick={() => dispatch({ type: "confirmFact", id: fact.id })}>
                Confirm
              </button>
            )}
          </span>
        ) : fact ? (
          <span className="field-note">Typed by you</span>
        ) : (
          def.hint && <span className="field-note">{def.hint}</span>
        )}
      </div>
    </div>
  );
}

export function DetailFields({ section }: { section: "A" | "B" }) {
  return (
    <div className="form-grid">
      {DETAIL_FIELDS.filter((d) => d.section === section).map((d) => (
        <DetailInput key={d.id} def={d} />
      ))}
    </div>
  );
}

function ProcessField({ id: field, label, prompts }: { id: ProcessFieldId; label: string; prompts: string[] }) {
  const { c, dispatch } = useCase();
  const draft = useDraft(c.process[field], (value) => dispatch({ type: "setProcess", field, value }));
  const empty = !draft.value.trim();
  const id = `field-${field}`;
  return (
    <div className={`field full ${empty ? "is-empty" : ""}`}>
      <div className="field-label-row">
        {empty && <StatusIcon kind="unconfirmed" size="sm" label="Not written yet" />}
        <label htmlFor={id}>{label}</label>
      </div>
      <ul className="plain-list prompts" id={`${id}-prompts`}>
        {prompts.map((t) => (
          <li key={t}>{t}</li>
        ))}
      </ul>
      <textarea
        id={id}
        rows={4}
        autoComplete="off"
        aria-describedby={`${id}-prompts`}
        value={draft.value}
        onChange={(e) => draft.onChange(e.target.value)}
        onBlur={draft.onBlur}
      />
    </div>
  );
}

export function ProcessFields() {
  return (
    <div className="form-grid">
      <p className="meta full section-hint">
        Batatis asks; you write. These answers go into the form exactly as written, and Batatis never drafts them.
      </p>
      {PROCESS_FIELDS.map((p) => (
        <ProcessField key={p.id} {...p} />
      ))}
    </div>
  );
}
