import { useEffect, useMemo, useRef, useState } from "react";
import { engine, EngineError, type CodeHit } from "../api/client";
import { toViewRow, useProvisionText, useSectionC, type SectionCSource } from "../api/sectionC";
import { CODE_EDITION } from "../config";
import { applyIdentifyPlan, CONFIRM_UNAVAILABLE, DECISION_UNAVAILABLE, planIdentify, readDecisionBody } from "../identify";
import { failureKind, sectionCQuoteLabel } from "../rules";
import { DemoFallback, GapStrip, PanelHeader, StatusPill } from "../components";
import { CODE_TERMS } from "../fixture";
import { candidateById, unresolvedCandidates } from "../model";
import { useCase } from "../store";
import type { SectionCRow } from "../types";

function AttributionCell({ row }: { row: SectionCRow }) {
  if (row.attributionStatus === "direct") return <span className="label-pill">Direct row</span>;
  if (row.attributionStatus === "inherited")
    return (
      <span className="label-pill" title={`Uses the table row for ${row.inheritedFrom}`}>
        Inherited · {row.inheritedFrom}
      </span>
    );
  return <span className="label-pill">No row in table</span>;
}

const rowKey = (r: SectionCRow) => `${r.candidateId}:${r.provision}`;
const term = (r: SectionCRow, code: string) => r.terms?.[code] ?? CODE_TERMS[code];

/** Where the rows came from: the engine's lookup, or the bundled sample when the engine is unreachable. */
function SourceLabel({ source, error }: { source: SectionCSource; error?: string }) {
  if (source === "live") return <StatusPill dot="done">Live lookup</StatusPill>;
  if (source === "loading") return <StatusPill dot="pending">Looking up…</StatusPill>;
  if (source === "cached") {
    return (
      <span className="label-pill" title={error}>
        <span className="status-dot warning" />
        Cached demo run
      </span>
    );
  }
  return (
    <span className="label-pill" title={error}>
      <span className="status-dot blocking" />
      Lookup failed
    </span>
  );
}

function Pairs({ row }: { row: SectionCRow }) {
  if (!row.pairs.length) return <span className="muted-text">No objective or function in the attribution table for this provision</span>;
  return (
    <ul className="plain-list pairs">
      {row.pairs.map((p) => (
        <li key={p.bracket}>
          <span className="pair-group">
            {p.objectives.map((o) => (
              <abbr key={o} className="code-term" title={term(row, o)}>
                {o}
              </abbr>
            ))}
          </span>
          <span className="meta">·</span>
          <span className="pair-group">
            {p.functions.map((f) => (
              <abbr key={f} className="code-term" title={term(row, f)}>
                {f}
              </abbr>
            ))}
          </span>
        </li>
      ))}
    </ul>
  );
}

const SUGGESTED = "Suggested by search, confirm before submitting";

function ProvisionSearch() {
  const { c, dispatch, engineId } = useCase();
  const [query, setQuery] = useState(c.description);
  const [hits, setHits] = useState<CodeHit[]>([]);
  const [note, setNote] = useState("");
  const edited = useRef(false);

  useEffect(() => {
    if (!edited.current) setQuery(c.description);
  }, [c.description]);

  async function runSearch(text: string) {
    const q = text.trim();
    if (q.length < 3) {
      setNote("Type a few words from your description to search.");
      setHits([]);
      return;
    }
    setNote("Searching the code database…");
    try {
      const rows = await engine.search(q, { division: "B", limit: 8 });
      setHits(rows);
      setNote(rows.length ? `${rows.length} provisions. Pick the one that fits what you are proposing.` : "No provisions matched those words.");
    } catch (e) {
      setHits([]);
      setNote(e instanceof EngineError ? e.detail : "The code database did not answer.");
    }
  }

  useEffect(() => {
    const prose = c.description.trim();
    if (prose.length < 8) return;
    const ctl = new AbortController();
    let cancelled = false;
    (async () => {
      if (engineId) {
        try {
          const ranked = await engine.identify(engineId, prose, [], ctl.signal);
          if (cancelled) return;
          const plan = planIdentify(ranked, 5);
          if (plan.articles.length) {
            applyIdentifyPlan(dispatch, plan);
            setNote(plan.note);
            return;
          }
        } catch (e) {
          if (ctl.signal.aborted || cancelled) return;
          if (!(e instanceof EngineError) || failureKind(e.status, e.detail) !== "missing-route") {
            /* search below is the path on this engine */
          }
        }
      }
      if (!cancelled) await runSearch(prose);
    })();
    return () => {
      cancelled = true;
      ctl.abort();
    };
    // Search again when the description changes. The box stays editable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [engineId, c.description]);

  return (
    <form
      className="field"
      onSubmit={(e) => {
        e.preventDefault();
        void runSearch(query);
      }}
    >
      <label htmlFor="section-c-search">Search the code for a provision</label>
      <input
        id="section-c-search"
        value={query}
        onChange={(e) => {
          edited.current = true;
          setQuery(e.target.value);
        }}
      />
      <button type="submit" className="btn">
        Search
      </button>
      {note && (
        <p className="field-note" role="status">
          {note}
        </p>
      )}
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
              <p className="meta">{SUGGESTED}</p>
              <button
                type="button"
                className="btn"
                onClick={() => {
                  if (c.candidates.some((x) => x.provision === h.id)) return;
                  dispatch({
                    type: "addCandidate",
                    candidate: {
                      id: `search-${h.id}`,
                      topic: h.article_title || h.title || h.id,
                      provision: h.id,
                      part: Number(h.id.split(".")[0]) || 0,
                      benchmark: false,
                      identified: true,
                      suggestion: "search",
                      quote: { text: h.text, citation: h.citation ?? "No citation returned" },
                      departure: "do something other than what this sentence requires",
                      clarifyingQuestion: "Which part of this sentence does the design not follow?",
                      answer: null,
                    },
                  });
                  setNote(`${h.id} is in the table. Confirm it before you submit.`);
                }}
              >
                Use this provision
              </button>
            </li>
          ))}
        </ul>
      )}
    </form>
  );
}

export function SectionC() {
  const { c, gaps, dispatch, engineId, saveDraft } = useCase();
  // Confirmed departures and the ones still awaiting an answer; a "no" drops the provision.
  const [attempt, setAttempt] = useState(0);
  const [confirmNote, setConfirmNote] = useState("");
  const wanted = useMemo(
    () =>
      c.candidates
        .filter((a) => /^\d/.test(a.provision) && (a.answer === "yes" || (a.suggestion === "search" && a.answer === null)))
        .map((a) => ({ candidateId: a.id, provision: a.provision })),
    [c.candidates],
  );
  const confirmedWithoutArticle = c.candidates.some((a) => a.answer === "yes" && !/^\d/.test(a.provision));
  const { rows, source, error, status } = useSectionC(wanted, c.sectionC, attempt);
  const [selected, setSelected] = useState<string>();
  const sel = rows.find((r) => rowKey(r) === selected) ?? rows[0];
  const selCand = sel && candidateById(c, sel.candidateId);
  const liveText = useProvisionText(source === "live" ? sel?.provision : undefined, attempt);
  const fromCodedb = liveText.state === "live";
  const quoteLabel = sectionCQuoteLabel(fromCodedb);
  const quote = fromCodedb
    ? { text: liveText.text, citation: liveText.citation }
    : selCand && selCand.provision === sel?.provision
      ? selCand.quote
      : null;
  const open = unresolvedCandidates(c);
  const yesKey = c.candidates
    .filter((a) => a.answer === "yes" && /^\d/.test(a.provision))
    .map((a) => a.provision)
    .join("|");

  useEffect(() => {
    if (!engineId || !yesKey) return;
    const provisions = yesKey.split("|");
    const ctl = new AbortController();
    void engine.confirmIdentify(engineId, provisions, ctl.signal).catch((err: unknown) => {
      if (ctl.signal.aborted) return;
      if (err instanceof EngineError && failureKind(err.status, err.detail) === "missing-route") {
        setConfirmNote(CONFIRM_UNAVAILABLE);
      }
    });
    return () => ctl.abort();
  }, [engineId, yesKey]);

  return (
    <>
      <PanelHeader title="Section C · Objectives, functions and intent" meta="Lookup from the attribution tables" />
      <GapStrip gaps={gaps} />
      <div className="pane scroll-body">
        <div className="sc-source">
          {source === "live" && rows.length === 0 ? (
            <StatusPill dot="pending">No provisions picked yet</StatusPill>
          ) : (
            <SourceLabel source={source} error={error} />
          )}
          {source === "live" && rows.length > 0 && <span className="meta">Rows from the engine's code database for this case</span>}
        </div>
        {confirmNote && (
          <p className="empty" role="status">
            {confirmNote}
          </p>
        )}
        <p className="meta intro">
          Objectives and functions come from {CODE_EDITION}, by lookup after you confirm a departure that names an article. Rows are not invented when no article is known.
        </p>
        {source === "cached" && (
          <p className="field-note" role="status">
            <span className="status-dot warning" />
            Cached demo run. The engine did not return a live lookup ({error}). These rows were saved with the example.
          </p>
        )}
        {(source === "cached" || source === "error") && failureKind(status ?? 0, error ?? "") === "unreachable" && (
          <DemoFallback reason={error ?? "The engine could not be reached."} onRetry={() => setAttempt((n) => n + 1)} />
        )}
        {(source === "cached" || source === "error") && failureKind(status ?? 0, error ?? "") !== "unreachable" && (
          <p className="field-note" role="status">
            <span className="status-dot warning" />
            {error ?? "The lookup did not return."}{" "}
            <button type="button" className="btn" onClick={() => setAttempt((n) => n + 1)}>
              Retry
            </button>
          </p>
        )}
        <ProvisionSearch />
        {!rows.length && (
          <div className="empty-guide">
            <h2 className="section-title">This table is empty</h2>
            <p>
              {confirmedWithoutArticle
                ? "You confirmed a departure, and no Division B article is attached. Search above and pick the provision that fits. This table stays empty until you do, so it does not invent a row."
                : "Nothing is listed yet. Search above. Results come from the code database. Pick a provision, then confirm it before you submit."}
            </p>
          </div>
        )}
        {rows.length > 0 && <div className="table-wrap">
          <table className="table sc-table">
            <thead>
              <tr>
                <th>Your answer</th>
                <th>Provision</th>
                <th>Attribution</th>
                <th>Objective · Function</th>
                <th>
                  Intent <span className="th-note">NBC 2020 Intent Statements, explanatory only</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const cand = candidateById(c, r.candidateId);
                const confirmed = cand?.answer === "yes";
                return (
                  <tr
                    key={rowKey(r)}
                    className={`${r === sel ? "selected" : ""} ${confirmed ? "" : "unconfirmed"}`}
                    tabIndex={0}
                    aria-selected={r === sel}
                    onClick={() => setSelected(rowKey(r))}
                    onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), setSelected(rowKey(r)))}
                  >
                    <td data-label="Your answer">
                      {cand?.suggestion && cand.answer !== "yes" && (
                        <span className="meta cell-sub">{cand.suggestion === "search" ? SUGGESTED : "Suggested from your description, confirm before submitting"}</span>
                      )}
                      {confirmed ? (
                        <StatusPill dot="done">Departure</StatusPill>
                      ) : (
                        <StatusPill dot={cand?.answer === "not-sure" ? "warning" : "blocking"}>
                          {cand?.answer === "not-sure" ? "Not sure" : "Unanswered"}
                        </StatusPill>
                      )}
                    </td>
                    <td data-label="Provision">
                      <span className="article-id">{r.provision}</span>
                      <span className="meta cell-sub">{cand?.topic}</span>
                    </td>
                    <td data-label="Attribution">
                      <AttributionCell row={r} />
                      {r.differs && (
                        <span className="label-pill differs" title={r.differsDetail}>
                          <span className="status-dot warning" />
                          Attribution differs
                        </span>
                      )}
                    </td>
                    <td data-label="Objective · Function">
                      <Pairs row={r} />
                    </td>
                    <td data-label="Intent">
                      {!r.intent.length && <span className="muted-text">None for this provision</span>}
                      {r.intent.map((i) => (
                        <span key={i.text} className="intent-text">
                          {i.text}
                        </span>
                      ))}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>}

        {sel && (
          <div className="sc-detail">
            <section className="source-block">
              <div className="block-label">
                <span className="label-pill">{quoteLabel.pill}</span>
                <span className="meta">
                  {quoteLabel.meta}
                  {quote?.citation ? ` · ${quote.citation}` : liveText.state === "error" ? ` · ${liveText.message}` : ""}
                </span>
              </div>
              <blockquote className="cite-block quote">
                {fromCodedb ? quote?.text : liveText.state === "loading" ? "Loading the provision text…" : (quote?.text ?? "No code sentence is available for this row.")}
              </blockquote>
              <p className="meta">
                Section C row: {sel.citation}
                {sel.attributionStatus === "inherited" && ` · uses the table row of ${sel.inheritedFrom}`}
                {sel.attributionStatus === "no-row" && " · the attribution table has no row for it"}
              </p>
              {sel.differs && (
                <p className="field-note">
                  <span className="status-dot warning" />
                  {sel.differsDetail}
                </p>
              )}
            </section>
            <section className="source-block">
              <div className="block-label">
                <span className="label-pill">NBC 2020 Intent Statements</span>
                <span className="meta">Explanatory only, not part of NBC(AE) 2023</span>
              </div>
              {!sel.intent.length && <p className="meta">No NBC 2020 intent statement for this provision.</p>}
              {sel.intent.map((i) => (
                <blockquote key={i.text} className="cite-block quote intent-block">
                  {i.objective && <span className="meta">{i.objective} · </span>}{i.text}
                </blockquote>
              ))}
            </section>
            {selCand?.suggestion && selCand.answer !== "yes" && (
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => {
                  dispatch({ type: "answerCandidate", id: selCand.id, answer: "yes" });
                  const provisions = [
                    ...new Set(
                      c.candidates
                        .filter((a) => /^\d/.test(a.provision) && (a.answer === "yes" || a.id === selCand.id))
                        .map((a) => a.provision),
                    ),
                  ];
                  void (async () => {
                    const id = engineId ?? (await saveDraft());
                    if (!id) return;
                    if (selCand.suggestion === "identify") {
                      try {
                        const body = await engine.decide(id, selCand.provision, "yes");
                        const read = readDecisionBody(body, selCand.provision);
                        if (read.row) dispatch({ type: "noteSectionC", rows: [toViewRow(read.row, selCand.id)] });
                      } catch (err: unknown) {
                        if (err instanceof EngineError && failureKind(err.status, err.detail) === "missing-route") {
                          setConfirmNote(DECISION_UNAVAILABLE);
                        }
                      }
                    }
                    await engine.sectionD(id, provisions).catch(() => undefined);
                  })();
                }}
              >
                Confirm this provision
              </button>
            )}
            {sel.explanation && (
              <section className="ai-block">
                <div className="block-label">
                  <span className="label-pill ai-pill">AI-written</span>
                  <span className="meta">Explanation, not code text</span>
                </div>
                <p className="ai-explain">{sel.explanation}</p>
              </section>
            )}
          </div>
        )}
      </div>
      <div className="footer-bar">
        <span className="status-note" role="status">
          {open.length ? `${open.length} row${open.length > 1 ? "s" : ""} wait for your answer in Code check. ` : ""}
          Not sure does not block Continue.
        </span>
        <a className="btn btn-ghost" href="#/code-check">
          Back
        </a>
        <button type="button" className="btn btn-primary" onClick={() => (location.hash = "#/application?tab=D")}>
          Continue to application
        </button>
      </div>
    </>
  );
}
