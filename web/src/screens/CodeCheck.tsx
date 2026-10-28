import { useEffect, useLayoutEffect, useState } from "react";
import { engine, EngineError, type CodeHit } from "../api/client";
import { CodeQuote, ServiceUnavailable, CheckAction, DraftNote, GapStrip, Icon, PanelHeader, StatusPill, type Dot } from "../components";
import { CODE_EDITION } from "../config";
import { answeredYes, unresolvedCandidates } from "../model";
import { useRoute } from "../router";
import { withinProvision } from "../provisions";
import { exitCountWarning, failureKind, QUOTE_LABEL, quoteKind } from "../rules";
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

function CandidateCard({
  a,
  index,
  total,
  onAnswer,
}: {
  a: Candidate;
  index: number;
  total: number;
  onAnswer: (candidate: Candidate, answer: CandidateAnswer) => void;
}) {
  const { c, dispatch } = useCase();
  const [storeys, setStoreys] = useState("");
  const isStoreys = a.id === "desc-storeys";
  const savedCount = c.questions.find(q => q.id === "q-desc-storeys")?.answer;
  const s = isStoreys && savedCount ? { dot: "done" as const, label: "Count recorded" } : STATUS[a.answer ?? "none"];
  const kind = quoteKind(a);
  return (
    <article className="card" id={`cand-${a.id}`} tabIndex={-1} aria-labelledby={`cand-${a.id}-topic`}>
      <div className="card-head">
        <span className="meta">
          {index + 1} of {total}
        </span>
        <h2 className="card-topic" id={`cand-${a.id}-topic`}>
          {a.topic}
        </h2>
        {/^\d/.test(a.provision) && <span className="meta">{a.provision}</span>}
        {a.benchmark && a.answer === "yes" && <span className="label-pill">Main requirement</span>}
        {a.suggestion && a.answer === null && <span className="label-pill">Suggested</span>}
        <StatusPill dot={s.dot}>{s.label}</StatusPill>
      </div>
      <details className="code-said compact-help"><summary>{kind === "code" ? "Code wording" : "Why this appears"}</summary>
        <div className="block-label">
          <span className={`label-pill${kind === "ranking" ? " ai-pill" : ""}`}>{QUOTE_LABEL[kind].pill}</span>
          <span className="meta">{QUOTE_LABEL[kind].meta}</span>
        </div>
        {kind === "code" ? (
          <CodeQuote text={a.quote.text} />
        ) : kind === "ranking" ? (
          <p className="ai-explain">{a.quote.text}</p>
        ) : kind === "missing" ? null : (
          <blockquote className="cite-block quote">{a.quote.text}</blockquote>
        )}
      </details>
      {isStoreys ? <form className="field" onSubmit={e => {
        e.preventDefault();
        if (!Number.isInteger(Number(storeys)) || Number(storeys) < 1) return;
        dispatch({ type: "setStoreyCount", value: storeys });
      }}><label htmlFor="storey-count">How many storeys does the building have?</label>
        <input id="storey-count" type="number" min="1" step="1" value={storeys || savedCount || ""} onChange={e => setStoreys(e.target.value)} />
        <div className="btn-row"><button className="btn" type="submit">Save count</button><button className="btn" type="button" onClick={() => { setStoreys(""); dispatch({ type: "setStoreyCount", value: "" }); }}>Not sure</button></div>
      </form> : <><p className="ask">
        Does your design <strong>{a.departure}</strong> instead?
      </p>
      <div className="segmented" role="group" aria-label={`Answer for ${a.topic}`}>
        {ANSWERS.map((o) => (
          <button
            key={o.value}
            type="button"
            className="btn"
            aria-pressed={a.answer === o.value}
            onClick={() => onAnswer(a, o.value)}
          >
            {o.label}
          </button>
        ))}
      </div>
      </>}
      {a.answer === "not-sure" && (
        <div className="followup">
          <div className="meta">Open question</div>
          <p>{a.clarifyingQuestion}</p>
          <p className="meta">Logged as an open question. Not sure does not block Continue. Section C does not treat this as a confirmed departure.</p>
        </div>
      )}
      {exitCountWarning(a.provision, a.topic) && (
        <p className="field-note" role="status">
          <span className="status-dot warning" /> {exitCountWarning(a.provision, a.topic)}
        </p>
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

/**
 * Record a code-check answer. For an article code identification offered, the store also sends the
 * decision (with the case version), so the engine writes its Section C row and, for Not sure,
 * binds the officer's open question.
 */
export function useCandidateAnswer() {
  const { decide, confirmDeparture } = useCase();
  // Kept per card, so an error on one card never shows on the next; a new answer clears it.
  const [note, setNote] = useState<{ id: string; text: string } | null>(null);
  function onAnswer(candidate: Candidate, answer: CandidateAnswer, onError?: () => void) {
    setNote(null);
    void decide(candidate, answer).then((error) => {
      if (!error) return;
      setNote({ id: candidate.id, text: error });
      onError?.();
    });
  }
  /** Yes is not a departure until the applicant says what the design does instead. */
  async function onDeparture(candidate: Candidate, departure: string) {
    setNote(null);
    const error = await confirmDeparture(candidate, departure);
    if (error) setNote({ id: candidate.id, text: error });
    return error;
  }
  return { onAnswer, onDeparture, decisionNote: note?.text ?? "", decisionNoteFor: (id: string) => (note?.id === id ? note.text : "") };
}

type Filter = "all" | "open" | "yes";

export function CodeCheck() {
  const { c, gaps, dispatch, saveDraft, checkStatus, noteLookupFailure } = useCase();
  const route = useRoute();
  const focusedProvision = c.candidates.find(a => `cand-${a.id}` === route.params.get("focus"))?.provision;
  const { onAnswer, decisionNote } = useCandidateAnswer();
  const [cardIndex, setCardIndex] = useState(0);
  const [reviewProvision, setReviewProvision] = useState<string | null>(focusedProvision ?? null);
  const [searchOpen, setSearchOpen] = useState(checkStatus === "unavailable");
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<CodeHit[]>([]);
  const [searchNote, setSearchNote] = useState("");
  const [searchError, setSearchError] = useState("");
  const [searchDown, setSearchDown] = useState(false);
  const [adding, setAdding] = useState<string | null>(null);
  const open = unresolvedCandidates(c);
  const yes = answeredYes(c);
  const counts: Record<Filter, number> = { all: c.candidates.length, open: open.length, yes: yes.length };
  const shown = c.candidates.filter((a) => filter === "all" || (filter === "open" ? open.includes(a) : a.answer === "yes"));
  const labels: Record<Filter, string> = { all: "All", open: "Needs an answer", yes: "Departures" };

  useEffect(() => {
    if (!focusedProvision) return;
    setFilter("all");
    setReviewProvision(focusedProvision);
    setSearchOpen(false);
  }, [focusedProvision]);

  const reviewIndex = reviewProvision ? shown.findIndex(a => withinProvision(a.provision, reviewProvision)) : -1;
  const currentIndex = reviewIndex >= 0 ? reviewIndex : Math.min(cardIndex, shown.length - 1);
  const focusedId = reviewProvision ? shown[currentIndex]?.id : undefined;
  useLayoutEffect(() => {
    if (!focusedId || searchOpen) return;
    const card = document.getElementById(`cand-${focusedId}`);
    card?.focus({ preventScroll: true });
    card?.scrollIntoView({ block: "start", behavior: "instant" });
  }, [focusedId, searchOpen]);
  function reviewAdded(provision: string) {
    setFilter("all");
    setSearchOpen(false);
    setReviewProvision(provision);
  }

  return (
    <>
      <PanelHeader title="Code check" meta={CODE_EDITION} />
      {(checkStatus === "ready" || checkStatus === "needs_answers") && <GapStrip gaps={gaps} />}
      <div className="toolbar" role="toolbar" aria-label="Filter">
        {(Object.keys(labels) as Filter[]).map((f) => (
          <button key={f} type="button" className="pill" data-active={filter === f} aria-pressed={filter === f} onClick={() => { setFilter(f); setCardIndex(0); setReviewProvision(null); }}>
            {labels[f]} <span className="tab-count">{counts[f]}</span>
          </button>
        ))}
      </div>
      <div className="pane scroll-body">
        <div className="content-col stack">
          {decisionNote && (
            <p className="empty" role="status">
              {decisionNote}
            </p>
          )}
          <CheckAction />
          <details className="disclosure manual-search" open={searchOpen} onToggle={e => setSearchOpen(e.currentTarget.open)}>
            <summary>Search code manually</summary>
          <form
            className="field"
            onSubmit={(e) => {
              e.preventDefault();
              const q = query.trim();
              if (!q) {
                setSearchNote("Type a few words to search.");
                setSearchError("");
                setSearchDown(false);
                return;
              }
              setSearchNote("Searching…");
              setSearchError("");
              setSearchDown(false);
              engine
                .search(q, { division: "B", limit: 8 })
                .then((rows) => {
                  setHits(rows);
                  setSearchNote(rows.length ? `${rows.length} provisions returned.` : "No provisions returned.");
                })
                .catch((err: unknown) => {
                  setHits([]);
                  setSearchNote("");
                  const down = err instanceof EngineError && failureKind(err.status, err.detail) === "unreachable";
                  setSearchDown(down);
                  noteLookupFailure(err instanceof Error ? err.message : String(err));
                  setSearchError(err instanceof EngineError ? err.detail : "The review service did not respond.");
                });
            }}
          >
            <label htmlFor="code-search">Code keywords or article number</label>
            <input id="code-search" value={query} onChange={(e) => setQuery(e.target.value)} />
            <button type="submit" className="btn">
              Search
            </button>
            {searchNote && (
              <p className="field-note" role="status">
                {searchNote}
              </p>
            )}
            {searchError && searchDown && (
              <ServiceUnavailable
                reason={searchError}
                onRetry={() => document.getElementById("code-search")?.closest("form")?.requestSubmit()}
              />
            )}
            {searchError && !searchDown && (
              <div className="field-note" role="status">
                <span className="status-dot warning" /> Search unavailable. Try again. <details><summary>Technical detail</summary>{searchError}</details>
                <button type="button" className="btn" onClick={() => document.getElementById("code-search")?.closest("form")?.requestSubmit()}>
                  Retry
                </button>
              </div>
            )}
          </form>
          {hits.length > 0 && (
            <ul className="plain-list">
              {hits.map((h) => (
                <li key={h.id} className="card">
                  <div className="card-head">
                    <span className="article-id">{h.id}</span>
                    {h.article_title && <span className="card-topic">{h.article_title}</span>}
                    <span className="label-pill">Code text</span>
                  </div>
                  {h.text.trim() ? (
                    <CodeQuote text={h.text} />
                  ) : (
                    <p className="meta">Article heading. Its sentences load when you add it.</p>
                  )}
                  <p className="mono meta">{h.citation ?? "No citation returned"}</p>
                  <button
                    type="button"
                    className="btn"
                    disabled={adding === h.id}
                    onClick={async () => {
                      const existing = c.candidates.find((x) => x.provision === h.id);
                      if (existing) {
                        setSearchNote(`${h.id} is already on this check.`);
                        reviewAdded(h.id);
                        return;
                      }
                      let text = h.text.trim();
                      if (!text) {
                        setAdding(h.id);
                        setSearchNote(`Loading the wording of ${h.id}…`);
                        try {
                          text = (await engine.provision(h.id, "B")).text.trim();
                        } catch {
                          text = "";
                        } finally {
                          setAdding(null);
                        }
                      }
                      dispatch({
                        type: "addCandidate",
                        candidate: {
                          id: `search-${h.id}`,
                          topic: h.article_title || h.title || h.id,
                          provision: h.id,
                          part: Number(h.id.split(".")[0]) || 0,
                          benchmark: false,
                          quote: { text, citation: h.citation ?? "No citation returned", source: "code" },
                          identified: true,
                          departure: "do something other than what this sentence requires",
                          clarifyingQuestion: "Which part of this sentence does the design not follow?",
                          answer: null,
                        },
                      });
                      reviewAdded(h.id);
                      setSearchNote(
                        text
                          ? `Added ${h.id} to this check. Answer the new card before Section C.`
                          : `Added ${h.id} to this check. Its wording did not load; the citation is under Code reference. Answer the new card before Section C.`,
                      );
                    }}
                  >
                    Add to this check
                  </button>
                </li>
              ))}
            </ul>
          )}
          </details>
          {shown.length ? (
            shown.slice(currentIndex, currentIndex + 1).map((a) => (
              <CandidateCard key={a.id} a={a} index={c.candidates.indexOf(a)} total={c.candidates.length} onAnswer={onAnswer} />
            ))
          ) : (
            <p className="empty">
              {filter === "yes"
                ? "No confirmed departures yet."
                : filter === "open"
                  ? "No requirements need an answer."
                  : c.candidates.length
                    ? "No requirements to review."
                    : "No provisions selected yet."}
            </p>
          )}
          {shown.length > 1 && <div className="step-controls">
            <button type="button" className="btn" disabled={currentIndex === 0} onClick={() => { setReviewProvision(null); setCardIndex(currentIndex - 1); }}>Previous</button>
            <span className="meta">{Math.min(currentIndex + 1, shown.length)} of {shown.length}</span>
            <button type="button" className="btn" disabled={currentIndex >= shown.length - 1} onClick={() => { setReviewProvision(null); setCardIndex(currentIndex + 1); }}>Next question</button>
          </div>}
        </div>
      </div>
      <div className="footer-bar">
        <DraftNote />
        <button type="button" className="btn" onClick={() => void saveDraft()}>
          Save draft
        </button>
        <a className="btn btn-ghost" href="#/application?tab=B&step=last">
          Back
        </a>
        <button
          type="button"
          className={checkStatus === "not_requested" || checkStatus === "unavailable" ? "btn" : "btn btn-primary"}
          onClick={() => { location.hash = "#/section-c"; }}
        >
          Continue
        </button>
      </div>
    </>
  );
}
