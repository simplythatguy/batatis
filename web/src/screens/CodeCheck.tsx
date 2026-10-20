import { useState } from "react";
import { engine, failureText, type CodeHit } from "../api/client";
import { DemoFallback, DraftNote, GapStrip, Icon, PanelHeader, StatusPill, type Dot } from "../components";
import { answeredYes, unresolvedCandidates } from "../model";
import { useCase } from "../store";
import type { Candidate, CandidateAnswer } from "../types";

const ANSWERS: { value: CandidateAnswer; label: string }[] = [
  { value: "yes", label: "Yes" },
  { value: "no", label: "No" },
  { value: "not-sure", label: "Not sure" },
];

const STATUS: Record<string, { dot: Dot; label: string }> = {
  yes: { dot: "done", label: "Departure confirmed" },
  no: { dot: "pending", label: "Not a departure" },
  "not-sure": { dot: "warning", label: "Not sure yet" },
  none: { dot: "blocking", label: "Needs your answer" },
};

function CandidateCard({ a, index, total }: { a: Candidate; index: number; total: number }) {
  const { dispatch } = useCase();
  const s = STATUS[a.answer ?? "none"];
  return (
    <article className="card" id={`cand-${a.id}`} tabIndex={-1} aria-labelledby={`cand-${a.id}-topic`}>
      <div className="card-head">
        <span className="meta">
          {index + 1} of {total}
        </span>
        <h2 className="card-topic" id={`cand-${a.id}-topic`}>
          {a.topic}
        </h2>
        {a.benchmark && <span className="label-pill">Main requirement</span>}
        <StatusPill dot={s.dot}>{s.label}</StatusPill>
      </div>
      <div className="code-said">
        <div className="block-label">
          <span className="label-pill">
            {a.identified === false ? "Your words" : a.quote.citation.includes("not the code sentence") ? "Case summary" : "Code text"}
          </span>
          <span className="meta">
            {a.identified === false ? "From what you wrote. Not a ranked article." : a.quote.citation.includes("not the code sentence") ? "Cached summary" : "The code says"}
          </span>
        </div>
        <blockquote className="cite-block quote">{a.quote.text}</blockquote>
      </div>
      <p className="ask">
        <span className="label-pill ai-pill">AI-written</span> Does your design <strong>{a.departure}</strong> instead?
      </p>
      <div className="segmented" role="group" aria-label={`Answer for ${a.topic}`}>
        {ANSWERS.map((o) => (
          <button
            key={o.value}
            type="button"
            className="btn"
            aria-pressed={a.answer === o.value}
            onClick={() => dispatch({ type: "answerCandidate", id: a.id, answer: o.value })}
          >
            {o.label}
          </button>
        ))}
      </div>
      {a.answer === "not-sure" && (
        <div className="followup">
          <div className="meta">Open question</div>
          <p>{a.clarifyingQuestion}</p>
          <p className="meta">Logged as an open question. You can continue. Section C does not treat this as a confirmed departure.</p>
        </div>
      )}
      <details className="disclosure ref">
        <summary>
          <Icon name="chevron" size={12} />
          <span className="disclosure-title">Code reference</span>
        </summary>
        <dl className="ref-grid">
          <dt>Provision</dt>
          <dd className="article-id">{a.provision}</dd>
          <dt>Citation</dt>
          <dd className="mono">{a.quote.citation}</dd>
          <dt>Part</dt>
          <dd>Part {a.part}</dd>
        </dl>
      </details>
    </article>
  );
}

type Filter = "all" | "open" | "yes";

export function CodeCheck() {
  const { c, gaps, dispatch, saveDraft } = useCase();
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<CodeHit[]>([]);
  const [searchNote, setSearchNote] = useState("");
  const [searchError, setSearchError] = useState("");
  const open = unresolvedCandidates(c);
  const yes = answeredYes(c);
  const counts: Record<Filter, number> = { all: c.candidates.length, open: open.length, yes: yes.length };
  const shown = c.candidates.filter((a) => filter === "all" || (filter === "open" ? open.includes(a) : a.answer === "yes"));
  const labels: Record<Filter, string> = { all: "All", open: "Needs an answer", yes: "Departures" };
  return (
    <>
      <PanelHeader title="Code check" meta="NBC(AE) 2023 · 2nd printing" />
      <GapStrip gaps={gaps} />
      <div className="toolbar" role="toolbar" aria-label="Filter">
        {(Object.keys(labels) as Filter[]).map((f) => (
          <button key={f} type="button" className="pill" data-active={filter === f} aria-pressed={filter === f} onClick={() => setFilter(f)}>
            {labels[f]} <span className="tab-count">{counts[f]}</span>
          </button>
        ))}
      </div>
      <div className="pane scroll-body">
        <div className="content-col stack">
          <p className="meta intro">
            A departure means your design does something differently from a requirement. Cards from your description are questions, not ranked articles. Identify is command-line only. Search calls GET /code/search and shows only what the code database returns.
          </p>
          <form
            className="field"
            onSubmit={(e) => {
              e.preventDefault();
              const q = query.trim();
              if (!q) {
                setSearchNote("Type a few words to search.");
                setSearchError("");
                return;
              }
              setSearchNote("Searching…");
              setSearchError("");
              engine
                .search(q, { division: "B", limit: 8 })
                .then((rows) => {
                  setHits(rows);
                  setSearchNote(rows.length ? `${rows.length} provisions returned.` : "No provisions returned.");
                })
                .catch((err: unknown) => {
                  setHits([]);
                  setSearchNote("");
                  setSearchError(failureText(err));
                });
            }}
          >
            <label htmlFor="code-search">Search Division B</label>
            <input id="code-search" value={query} onChange={(e) => setQuery(e.target.value)} />
            <button type="submit" className="btn">
              Search
            </button>
            {searchNote && (
              <p className="field-note" role="status">
                {searchNote}
              </p>
            )}
            {searchError && (
              <DemoFallback
                reason={`Search did not return. ${searchError}`}
                onRetry={() => {
                  const form = document.getElementById("code-search");
                  form?.closest("form")?.requestSubmit();
                }}
              />
            )}
          </form>
          {hits.length > 0 && (
            <ul className="plain-list">
              {hits.map((h) => (
                <li key={h.id} className="card">
                  <div className="card-head">
                    <span className="article-id">{h.id}</span>
                    <span className="label-pill">Code text</span>
                  </div>
                  <blockquote className="cite-block quote">{h.text}</blockquote>
                  <p className="mono meta">{h.citation ?? "No citation returned"}</p>
                  <button
                    type="button"
                    className="btn"
                    onClick={() => {
                      if (c.candidates.some((x) => x.provision === h.id)) {
                        setSearchNote(`${h.id} is already on this check.`);
                        document.getElementById(`cand-search-${h.id}`)?.focus();
                        return;
                      }
                      dispatch({
                        type: "addCandidate",
                        candidate: {
                          id: `search-${h.id}`,
                          topic: h.article_title || h.title || h.id,
                          provision: h.id,
                          part: Number(h.id.split(".")[0]) || 0,
                          benchmark: false,
                          quote: { text: h.text, citation: h.citation ?? "No citation returned" },
                          identified: true,
                          departure: "do something other than what this sentence requires",
                          clarifyingQuestion: "Which part of this sentence does the design not follow?",
                          answer: null,
                        },
                      });
                      setSearchNote(`Added ${h.id}. Answer the new card before Section C.`);
                    }}
                  >
                    Add to this check
                  </button>
                </li>
              ))}
            </ul>
          )}
          {shown.length ? (
            shown.map((a) => <CandidateCard key={a.id} a={a} index={c.candidates.indexOf(a)} total={c.candidates.length} />)
          ) : (
            <p className="empty">
              {filter === "yes"
                ? "No confirmed departures yet."
                : filter === "open"
                  ? "No requirements need an answer."
                  : c.candidates.length
                    ? "No requirements to review."
                    : "No cards yet. What you write on Describe becomes the questions here. Or try an example."}
            </p>
          )}
        </div>
      </div>
      <div className="footer-bar">
        <DraftNote />
        <span className="status-note" role="status">
          {open.length ? `Answer ${open.map((a) => a.topic.toLowerCase()).join("; ")} before Section C` : ""}
        </span>
        <button type="button" className="btn" onClick={() => void saveDraft()}>
          Save draft
        </button>
        <a className="btn btn-ghost" href="#/describe">
          Back
        </a>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => {
            if (!open.length) {
              location.hash = "#/section-c";
              return;
            }
            const first = document.getElementById(`cand-${open[0].id}`);
            first?.focus();
            first?.scrollIntoView({ block: "center" });
          }}
        >
          Continue to Section C
        </button>
      </div>
    </>
  );
}
