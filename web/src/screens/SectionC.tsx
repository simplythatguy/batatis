import { useMemo, useState } from "react";
import { useProvisionText, useSectionC, type SectionCSource } from "../api/sectionC";
import { CodeText, Icon, StatusBadge } from "../components";
import { CODE_TERMS } from "../fixture";
import { candidateById } from "../model";
import { useCase } from "../store";
import type { SectionCRow } from "../types";

function ListCell({ row }: { row: SectionCRow }) {
  if (row.attributionStatus === "direct") return <span className="label-pill">Own row</span>;
  if (row.attributionStatus === "inherited")
    return (
      <span className="label-pill" title={`Uses the list row for ${row.inheritedFrom}`}>
        Uses the row for {row.inheritedFrom}
      </span>
    );
  return <span className="label-pill">Not in the list</span>;
}

const rowKey = (r: SectionCRow) => `${r.candidateId}:${r.provision}`;
const term = (r: SectionCRow, code: string) => r.terms?.[code] ?? CODE_TERMS[code];

/** Where the rows came from: the engine's lookup, or the bundled sample when the engine is unreachable. */
function SourceLabel({ source }: { source: SectionCSource }) {
  if (source === "live") return <StatusBadge status="ok" size="sm" label="Live lookup" text="Live lookup" />;
  if (source === "loading") return <span className="meta">Looking up…</span>;
  return <StatusBadge status="attention" size="sm" label="Offline sample" text="Offline sample" />;
}

function Pairs({ row }: { row: SectionCRow }) {
  if (!row.pairs.length) return <span className="muted-text">No objective or function in the objectives and functions list for this provision</span>;
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

/** Section C · Objectives and functions: the Application tab body, also reached at `#/section-c`. */
export function SectionCBody() {
  const { c } = useCase();
  // Provisions you said are different and the ones still awaiting an answer; a "no" drops the provision.
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

  return (
    <div className="stack">
      <div className="sc-source">
        <SourceLabel source={source} />
        <span className="meta">
          Looked up from NBC(AE) 2023, 2nd printing, Table 9.38.1.1. Greyed rows wait for your answer in{" "}
          <a className="text-link" href="#/code-check">
            Code check
          </a>{" "}
          and are not exported.
        </span>
      </div>
      {source === "offline" && (
        <p className="meta" role="status" title={error}>
          Can't reach the checker, so these rows are a bundled sample, not a lookup for this case.
        </p>
      )}
      {source !== "loading" && !rows.length && (
        <p className="empty">
          {c.candidates.length
            ? "No rows: you said none of the code rules differ from your design."
            : "No rows yet. Answer the cards in Code check first."}
        </p>
      )}
      {rows.length > 0 && (
        <div className="table-wrap">
          <table className="table sc-table">
            <thead>
              <tr>
                <th>Your answer</th>
                <th>Provision</th>
                <th>In the list</th>
                <th>Objective · Function</th>
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
                        <StatusBadge kind="confirmed" size="sm" label="Answered" text="Different" />
                      ) : cand?.answer === "not-sure" ? (
                        <StatusBadge kind="open-question" size="sm" label="Open question for the officer" text="Not sure" />
                      ) : (
                        <StatusBadge kind="unconfirmed" size="sm" label="Not answered yet" text="Unanswered" />
                      )}
                    </td>
                    <td data-label="Provision">
                      <span className="article-id">{r.provision}</span>
                      <span className="meta cell-sub">{cand?.topic}</span>
                    </td>
                    <td data-label="In the list">
                      <ListCell row={r} />
                      {r.differs && (
                        <span className="differs" title={r.differsDetail}>
                          <StatusBadge kind="info" size="sm" label="For your information" text="Differs from NBC 2020 intent" />
                        </span>
                      )}
                    </td>
                    <td data-label="Objective · Function">
                      <Pairs row={r} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {sel && (
        <div className="sc-detail">
          <section className="source-block">
            <CodeText text={quote?.text} citation={quote?.citation ?? sel.citation} loading={!quote && source !== "offline"} />
            {(sel.attributionStatus !== "direct" || sel.differs) && (
              <p className="meta">
                {sel.attributionStatus === "inherited" && `Uses the list row of ${sel.inheritedFrom}. `}
                {sel.attributionStatus === "no-row" && "The objectives and functions list has no row for it. "}
                {sel.differs && sel.differsDetail}
              </p>
            )}
          </section>
          <details className="disclosure">
            <summary>
              <Icon name="chevron" size={12} />
              <span className="disclosure-title">Intent and explanation</span>
              <span className="meta">NBC 2020 intent, explanatory only{sel.explanation ? " · AI-written note" : ""}</span>
            </summary>
            <div className="stack">
              {!sel.intent.length && <p className="meta">No NBC 2020 intent statement for this provision.</p>}
              {sel.intent.map((i) => (
                <blockquote key={i.text} className="cite-block quote intent-block">
                  {i.objective && <span className="meta">{i.objective} · </span>}
                  {i.text}
                </blockquote>
              ))}
              <p className="meta">NBC 2020 Intent Statements are explanatory only, not part of NBC(AE) 2023.</p>
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
          </details>
        </div>
      )}
    </div>
  );
}
