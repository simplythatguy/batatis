import { useState } from "react";
import { Icon, KindBadge, StatusPill } from "./components";
import { DETAIL_FIELDS, PROCESS_FIELDS, displayValue, factFor, factLabel, isTyped, valueText, type DetailField } from "./model";
import { useCase } from "./store";
import type { Fact, Question, Source } from "./types";

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
        <KindBadge fact={fact} />
        <span className="fact-field">{factLabel(fact.field)}</span>
        {pending && <StatusPill dot="warning">Check</StatusPill>}
      </div>
      <div className={`fact-value ${staleInputs ? "is-stale" : ""}`}>{displayValue(fact)}</div>
      {fact.formula && <div className="mono fact-formula">{fact.formula}</div>}
      {staleInputs && (
        <div className="field-note">
          <span className="status-dot pending" />
          An input changed. The engine recomputes this when connected.
        </div>
      )}
      {!staleInputs && unconfirmedInputs && (
        <div className="field-note">
          <span className="status-dot warning" />
          Uses a value you have not confirmed yet
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
        {fact.kind === "proposed" && !pending && (
          <span className="field-note">
            <span className="status-dot done" />
            Confirmed by you
          </span>
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
        <span className="meta">
          {c.facts.length}
          {pending ? ` · ${pending} to check` : c.facts.length ? " · all confirmed" : ""}
        </span>
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
          <span className="status-dot done" />
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
        <span className="meta">{open ? `${open} open` : "All answered"}</span>
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
  const empty = def.required && !value.trim();
  const id = `field-${def.id}`;
  const set = (v: string) => dispatch({ type: "setDetail", field: def.id, value: v, section: def.section });
  return (
    <div className={`field ${def.multiline ? "full" : ""} ${empty ? "is-empty" : ""}`}>
      <div className="field-label-row">
        {empty && <span className="status-dot pending" />}
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
        <textarea id={id} rows={3} autoComplete="off" value={value} onChange={(e) => set(e.target.value)} />
      ) : (
        <input id={id} autoComplete="off" value={value} onChange={(e) => set(e.target.value)} />
      )}
      <div className="field-foot">
        {fact && !isTyped(fact) ? (
          <span className="field-note">
            <span className={`status-dot ${fact.status === "confirmed" ? "done" : "warning"}`} />
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

export function ProcessFields() {
  const { c, dispatch } = useCase();
  return (
    <div className="form-grid">
      <p className="meta full section-hint">
        Batatis asks; you write. These answers go into the form exactly as written, and Batatis never drafts them.
      </p>
      {PROCESS_FIELDS.map((p) => {
        const empty = !c.process[p.id].trim();
        const id = `field-${p.id}`;
        return (
          <div key={p.id} className={`field full ${empty ? "is-empty" : ""}`}>
            <div className="field-label-row">
              {empty && <span className="status-dot pending" />}
              <label htmlFor={id}>{p.label}</label>
            </div>
            <ul className="plain-list prompts" id={`${id}-prompts`}>
              {p.prompts.map((t) => (
                <li key={t}>{t}</li>
              ))}
            </ul>
            <textarea
              id={id}
              rows={4}
              autoComplete="off"
              aria-describedby={`${id}-prompts`}
              value={c.process[p.id]}
              onChange={(e) => dispatch({ type: "setProcess", field: p.id, value: e.target.value })}
            />
          </div>
        );
      })}
    </div>
  );
}
