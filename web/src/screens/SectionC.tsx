import { useMemo, useState } from "react";
import { MODE_LABEL, codeIdRows, runDetail } from "../api/identify";
import { useProvisionText, useSectionC, type SectionCSource } from "../api/sectionC";
import { GapStrip, PanelHeader, StatusPill } from "../components";
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
  if (row.attributionStatus === "unavailable") return <span className="label-pill">Lookup not available</span>;
  return <span className="label-pill">No row in table</span>;
}

const rowKey = (r: SectionCRow) => `${r.candidateId}:${r.provision}`;
const term = (r: SectionCRow, code: string) => r.terms?.[code] ?? CODE_TERMS[code];

/** Where the rows came from: the engine's lookup, or the bundled sample when the engine is unreachable. */
function SourceLabel({ source, error }: { source: SectionCSource; error?: string }) {
  if (source === "live") return <StatusPill dot="done">Live lookup</StatusPill>;
  if (source === "loading") return <StatusPill dot="pending">Looking up…</StatusPill>;
  return (
    <span className="label-pill" title={error ? `Engine not reachable: ${error}` : undefined}>
      <span className="status-dot warning" />
      Offline sample
    </span>
  );
}

function Pairs({ row }: { row: SectionCRow }) {
  if (!row.pairs.length)
    return (
      <span className="muted-text">
        {row.attributionStatus === "unavailable"
          ? "Objective/function lookup not available for this article"
          : "No objective or function in the attribution table for this provision"}
      </span>
    );
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
          {p.objectives.length > 0 && p.functions.length > 0 && <span className="meta">·</span>}
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

export function SectionC() {
  const { c, gaps } = useCase();
  const run = c.codeId;
  // Once Code ID has run, rows come from the cards marked "Yes" (and, greyed, "Not sure"); the fixture
  // candidates are example data only until then. A "no" drops the provision.
  const wanted = useMemo(
    () => (run ? [] : c.candidates.filter((a) => a.answer !== "no").map((a) => ({ candidateId: a.id, provision: a.provision }))),
    [c.candidates, run],
  );
  const fixture = useSectionC(wanted, c.sectionC);
  const idRows = useMemo(() => codeIdRows(c), [c]);
  const { rows, source, error } = run ? { rows: idRows, source: "live" as const, error: undefined } : fixture;
  const [selected, setSelected] = useState<string>();
  const sel = rows.find((r) => rowKey(r) === selected) ?? rows[0];
  const selCand = sel && !run ? candidateById(c, sel.candidateId) : undefined;
  const liveText = useProvisionText(source === "live" ? sel?.provision : undefined);
  const idQuote = sel?.codeId?.quote ? { text: sel.codeId.quote, citation: sel.citation, clipped: sel.codeId.clipped } : null;
  const quote = liveText ?? idQuote ?? (selCand && selCand.provision === sel?.provision ? selCand.quote : null);
  const clipped = !liveText && !!idQuote?.clipped;
  const open = run ? rows.filter((r) => r.codeId?.answer === "not-sure") : unresolvedCandidates(c);

  return (
    <>
      <PanelHeader title="Section C · Objectives, functions and intent" meta="Lookup from the attribution tables" />
      <GapStrip gaps={gaps} />
      <div className="pane scroll-body">
        {run ? (
          <>
            <div className="sc-source">
              <span className="label-pill">
                <span className={`status-dot ${run.result.mode === "live" ? "done" : run.result.mode === "cached_demo" ? "pending" : "warning"}`} />
                From Code ID · {MODE_LABEL[run.result.mode] ?? run.result.mode}
              </span>
              <span className="meta">{runDetail(run.result)}</span>
            </div>
            <p className="meta intro">
              One row per article you marked “Yes, we do this differently” in Code ID. Provision, citation, code text and
              objective/function codes are copied from that run. Rows marked Not sure are shown greyed and are not exported.
            </p>
            {run.questions.some((q) => q.to === "officer") && (
              <p className="field-note sc-note" role="status">
                <span className="status-dot warning" />
                Open question for the officer: none of the suggested articles fit this project.{" "}
                <a className="text-link" href="#/code-check?focus=none-fit">
                  Review in Code ID
                </a>
              </p>
            )}
            {run.confirm && !run.confirm.ok && (
              <p className="field-note sc-note" role="status">
                <span className="status-dot warning" />
                Saved in this browser; the engine could not write Section C yet ({run.confirm.detail}).
              </p>
            )}
          </>
        ) : (
          <>
            <div className="sc-source">
              <SourceLabel source={source} error={error} />
              {source === "live" && <span className="meta">Rows from the engine's code database for this case</span>}
            </div>
            <p className="meta intro">
              Objectives and functions come from NBC(AE) 2023, 2nd printing, Table 9.38.1.1., by lookup after you confirm a
              departure. Rows still waiting for your answer are shown greyed and are not exported.
            </p>
          </>
        )}
        {source === "offline" && (
          <p className="field-note" role="status">
            <span className="status-dot warning" />
            The engine is not reachable, so these rows are a bundled offline sample, not a lookup for this case.
          </p>
        )}
        {run && !rows.length && (
          <div className="empty-state">
            <h2 className="section-title">No article in Section C yet</h2>
            <p className="meta">
              In Code ID, choose “Yes, we do this differently” on each article your project does differently. Its row appears here
              automatically. If none fit, record a question for the officer there.
            </p>
            <a className="btn" href="#/code-check">
              Go to Code ID
            </a>
          </div>
        )}
        <div className="table-wrap" hidden={!rows.length}>
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
                const cand = run ? undefined : candidateById(c, r.candidateId);
                const confirmed = r.codeId ? r.codeId.answer === "yes" : cand?.answer === "yes";
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
                      {r.codeId ? (
                        <StatusPill dot={confirmed ? "done" : "warning"}>{confirmed ? "Done differently" : "Not sure"}</StatusPill>
                      ) : confirmed ? (
                        <StatusPill dot="done">Departure</StatusPill>
                      ) : (
                        <StatusPill dot={cand?.answer === "not-sure" ? "warning" : "blocking"}>
                          {cand?.answer === "not-sure" ? "Not sure" : "Unanswered"}
                        </StatusPill>
                      )}
                    </td>
                    <td data-label="Provision">
                      <span className="article-id">{r.provision}</span>
                      <span className="meta cell-sub">{r.codeId?.title ?? cand?.topic}</span>
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
                      {!r.intent.length && (
                        <span className="muted-text">{r.codeId ? "Not returned by Code ID" : "None for this provision"}</span>
                      )}
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
        </div>

        {sel && (
          <div className="sc-detail">
            <section className="source-block">
              <div className="block-label">
                <span className="label-pill">Code text</span>
                <span className="meta">
                  {liveText || !sel.codeId ? "Retrieved verbatim" : "Verbatim, as stored with the Code ID run"} ·{" "}
                  {quote?.citation || sel.citation || "citation not returned"}
                </span>
              </div>
              <blockquote className="cite-block quote">
                {quote?.text ?? (sel.codeId ? "No code text was returned for this article." : "Loading the provision text…")}
                {clipped && <span className="clip-mark"> … [clipped — full text in the code]</span>}
              </blockquote>
              <p className="meta">
                Section C row: {sel.citation || sel.provision}
                {sel.attributionStatus === "inherited" && ` · uses the table row of ${sel.inheritedFrom}`}
                {sel.attributionStatus === "no-row" && " · the attribution table has no row for it"}
                {sel.attributionStatus === "unavailable" && " · objective/function lookup not available for this article"}
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
              {!sel.intent.length && (
                <p className="meta">
                  {sel.codeId ? "Code ID does not return intent statements for this article." : "No NBC 2020 intent statement for this provision."}
                </p>
              )}
              {sel.intent.map((i) => (
                <blockquote key={i.text} className="cite-block quote intent-block">
                  {i.objective && <span className="meta">{i.objective} · </span>}{i.text}
                </blockquote>
              ))}
            </section>
            {sel.codeId?.explainer && (
              <section className="explain-block" data-source={sel.codeId.explainer.source}>
                <div className="block-label">
                  <span className="label-pill">Explanation</span>
                  {sel.codeId.explainer.source === "ai_written" && <span className="label-pill ai-pill">AI-written</span>}
                  <span className="meta">
                    {sel.codeId.explainer.source === "ai_written"
                      ? "Not a finding about your design"
                      : "Built from the code database · not a finding about your design"}
                  </span>
                </div>
                <p className="ai-explain">{sel.codeId.explainer.text}</p>
              </section>
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
          {open.length ? `${open.length} row${open.length > 1 ? "s" : ""} marked Not sure in Code ID` : ""}
        </span>
        <a className="btn btn-ghost" href="#/code-check">
          Back
        </a>
        <a className="btn btn-primary" href="#/application?tab=alt">
          Continue to application
        </a>
      </div>
    </>
  );
}
