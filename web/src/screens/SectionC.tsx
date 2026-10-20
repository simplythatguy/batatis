import { useMemo, useState } from "react";
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

export function SectionC() {
  const { c, gaps } = useCase();
  // Confirmed departures and the ones still awaiting an answer; a "no" drops the provision.
  const wanted = useMemo(
    () => c.candidates.filter((a) => a.answer !== "no").map((a) => ({ candidateId: a.id, provision: a.provision })),
    [c.candidates],
  );
  const { rows, source, error } = useSectionC(wanted, c.sectionC);
  const [selected, setSelected] = useState<string>();
  const sel = rows.find((r) => rowKey(r) === selected) ?? rows[0];
  const selCand = sel && candidateById(c, sel.candidateId);
  const liveText = useProvisionText(source === "live" ? sel?.provision : undefined);
  const quote = liveText ?? (selCand && selCand.provision === sel?.provision ? selCand.quote : null);
  const open = unresolvedCandidates(c);

  return (
    <>
      <PanelHeader title="Section C · Objectives, functions and intent" meta="Lookup from the attribution tables" />
      <GapStrip gaps={gaps} />
      <div className="pane scroll-body">
        <div className="sc-source">
          <SourceLabel source={source} error={error} />
          {source === "live" && <span className="meta">Rows from the engine's code database for this case</span>}
        </div>
        <p className="meta intro">
          Objectives and functions come from NBC(AE) 2023, 2nd printing, Table 9.38.1.1., by lookup after you confirm a
          departure. Rows still waiting for your answer are shown greyed and are not exported.
        </p>
        {source === "offline" && (
          <p className="field-note" role="status">
            <span className="status-dot warning" />
            The engine is not reachable, so these rows are a bundled offline sample, not a lookup for this case.
          </p>
        )}
        <div className="table-wrap">
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
        </div>

        {sel && (
          <div className="sc-detail">
            <section className="source-block">
              <div className="block-label">
                <span className="label-pill">Code text</span>
                <span className="meta">Retrieved verbatim · {quote?.citation ?? sel.citation}</span>
              </div>
              <blockquote className="cite-block quote">{quote?.text ?? "Loading the provision text…"}</blockquote>
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
          {open.length ? `${open.length} row${open.length > 1 ? "s" : ""} wait for your answer in Code check` : ""}
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
