import { useState } from "react";
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

function Pairs({ row }: { row: SectionCRow }) {
  if (!row.pairs.length) return <span className="muted-text">No objective or function in the attribution table for this provision</span>;
  return (
    <ul className="plain-list pairs">
      {row.pairs.map((p) => (
        <li key={p.bracket}>
          <span className="pair-group">
            {p.objectives.map((o) => (
              <abbr key={o} className="code-term" title={CODE_TERMS[o]}>
                {o}
              </abbr>
            ))}
          </span>
          <span className="meta">·</span>
          <span className="pair-group">
            {p.functions.map((f) => (
              <abbr key={f} className="code-term" title={CODE_TERMS[f]}>
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
  const rows = c.sectionC.filter((r) => candidateById(c, r.candidateId)?.answer !== "no");
  const [selected, setSelected] = useState(rows[0]?.candidateId);
  const sel = rows.find((r) => r.candidateId === selected) ?? rows[0];
  const selCand = sel && candidateById(c, sel.candidateId);
  const open = unresolvedCandidates(c);

  return (
    <>
      <PanelHeader title="Section C · Objectives, functions and intent" meta="Lookup from the attribution tables" />
      <GapStrip gaps={gaps} />
      <div className="pane scroll-body">
        <p className="meta intro">
          Objectives and functions come from NBC(AE) 2023, 2nd printing, Table 9.38.1.1., by lookup after you confirm a
          departure. Rows still waiting for your answer are shown greyed and are not exported.
        </p>
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
                    key={r.candidateId}
                    className={`${r === sel ? "selected" : ""} ${confirmed ? "" : "unconfirmed"}`}
                    tabIndex={0}
                    aria-selected={r === sel}
                    onClick={() => setSelected(r.candidateId)}
                    onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), setSelected(r.candidateId))}
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
                <span className="meta">Retrieved verbatim · {selCand?.quote.citation}</span>
              </div>
              <blockquote className="cite-block quote">{selCand?.quote.text}</blockquote>
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
              {sel.intent.map((i) => (
                <blockquote key={i.text} className="cite-block quote intent-block">
                  {i.objective && <span className="meta">{i.objective} · </span>}{i.text}
                </blockquote>
              ))}
            </section>
            <section className="ai-block">
              <div className="block-label">
                <span className="label-pill ai-pill">AI-written</span>
                <span className="meta">Explanation, not code text</span>
              </div>
              <p className="ai-explain">{sel.explanation}</p>
            </section>
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
