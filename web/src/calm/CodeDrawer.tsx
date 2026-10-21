import { useEffect, useState } from "react";
import { useProvisionText } from "../api/sectionC";
import { NrcCredit } from "../components";
import { CODE_EDITION } from "../config";
import { canonicalProvision, isProvision } from "../provisions";
import { QUOTE_LABEL, quoteKind } from "../rules";
import { ProvisionSearch } from "../screens/SectionC";
import { useCase } from "../store";
import type { SectionCRow } from "../types";
import { RelevanceRing } from "./RelevanceRing";
import { codeHref } from "./routes";
import { articleOf } from "./useRelevance";
import { CIcon, Eyebrow, Modal } from "./ui";

export interface DrawerState {
  mode: "code" | "search";
  candidateId?: string;
}

function Pairs({ row }: { row: SectionCRow }) {
  if (row.attributionStatus === "no-row" || !row.pairs.length) {
    return <p className="cf-faint">The attribution table has no row for this sentence. Section C says so instead of inventing one.</p>;
  }
  const codes = [...new Set(row.pairs.flatMap((p) => [...p.objectives, ...p.functions]))];
  return (
    <>
      {row.attributionStatus === "inherited" && <p className="cf-faint">Uses the table row of {row.inheritedFrom}.</p>}
      <ul className="cf-pairs">
        {codes.map((code) => (
          <li key={code}>
            <span className="cf-mono">{code}</span>
            <span>{row.terms?.[code] ?? "Title not returned by the lookup."}</span>
          </li>
        ))}
      </ul>
    </>
  );
}

/** Right-side drawer (bottom sheet on phones) with the rule behind a code card. */
export function CodeDrawer({ state, onClose, onAdded }: { state: DrawerState | null; onClose: () => void; onAdded: (candidateId: string) => void }) {
  const { c, sectionCLookup, retrySectionC } = useCase();
  const a = state?.candidateId ? c.candidates.find((x) => x.id === state.candidateId) : undefined;
  const [searching, setSearching] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => setSearching(state?.mode === "search"), [state]);
  const provision = a && isProvision(a.provision) ? a.provision : undefined;
  const live = useProvisionText(state ? provision : undefined, attempt);
  const row = a
    ? c.sectionC.find((r) => r.candidateId === a.id) ?? c.sectionC.find((r) => canonicalProvision(r.provision) === canonicalProvision(a.provision))
    : undefined;
  const kind = a ? quoteKind(a) : "missing";
  const verbatim = live.state === "live" ? { text: live.text, citation: live.citation } : kind === "code" && a ? { text: a.quote.text, citation: a.quote.citation } : null;

  return (
    <Modal open={Boolean(state)} onClose={onClose} labelledBy="cf-drawer-title" className="cf-drawer">
      <div className="cf-drawer-scroll">
        <div className="cf-drawer-head">
          <Eyebrow>{a ? (verbatim ? "Code text · verbatim" : QUOTE_LABEL[kind].pill) : "Code search"}</Eyebrow>
          <button type="button" className="cf-icon-btn is-sm" aria-label="Close" onClick={onClose}>
            <CIcon name="close" size={14} />
          </button>
        </div>
        {a ? (
          <>
            <h3 id="cf-drawer-title" className="cf-drawer-title">{a.topic}</h3>
            {provision && (
              <div className="cf-drawer-meta">
                <RelevanceRing id={provision} />
                <span className="cf-mono cf-faint cf-small">{CODE_EDITION} · Div B · {provision}</span>
              </div>
            )}
            {verbatim ? (
              <>
                <blockquote className="cf-code-text">{verbatim.text}</blockquote>
                <div className="cf-code-src">{verbatim.citation}</div>
                <div className="cf-code-src"><NrcCredit /></div>
              </>
            ) : live.state === "loading" ? (
              <p className="cf-faint cf-sect" role="status">Loading the code text…</p>
            ) : kind === "ranking" ? (
              <div className="cf-ai"><span className="cf-ai-tag">AI-written · why this was ranked · not code text</span>{a.quote.text}</div>
            ) : kind === "summary" || kind === "applicant" ? (
              <>
                <p className="cf-faint cf-small cf-sect">{QUOTE_LABEL[kind].meta}</p>
                <blockquote className="cf-plain-quote">{a.quote.text}</blockquote>
              </>
            ) : (
              <div className="cf-sect">
                <p className="cf-faint">The wording did not load.{live.state === "error" ? ` ${live.message}` : ""}</p>
                {provision && <button type="button" className="cf-btn is-sm" onClick={() => setAttempt((n) => n + 1)}><CIcon name="retry" size={13} />Try again</button>}
              </div>
            )}

            <section className="cf-sect">
              <Eyebrow>Why this rule exists</Eyebrow>
              {row ? (
                row.intent.length ? (
                  <>
                    {row.intent.map((i) => (
                      <p key={i.text} className="cf-muted cf-body">{i.objective ? <span className="cf-mono cf-faint">{i.objective} · </span> : null}{i.text}</p>
                    ))}
                    <div className="cf-code-src">NBC 2020 intent statement · explanatory only, not part of {CODE_EDITION} · <NrcCredit source="intent" /></div>
                  </>
                ) : (
                  <p className="cf-faint cf-body">No NBC 2020 intent statement for this provision.</p>
                )
              ) : sectionCLookup.source === "loading" ? (
                <p className="cf-faint cf-body" role="status">Looking up the Section C row…</p>
              ) : sectionCLookup.source === "error" ? (
                <div className="cf-body"><p className="cf-faint">The Section C lookup did not load.</p><button type="button" className="cf-btn is-sm" onClick={retrySectionC}>Try again</button></div>
              ) : (
                <p className="cf-faint cf-body">{provision ? "Shown once this reference has its Section C row." : "This card comes from your words. No rule has been matched to it yet."}</p>
              )}
              {row?.differs && <p className="cf-note"><span className="cf-dot is-warning" aria-hidden="true" />{row.differsDetail ?? "The NBC 2020 intent statement is attributed differently from NBC(AE) 2023."}</p>}
            </section>

            {row && (
              <section className="cf-sect">
                <Eyebrow>Objectives &amp; functions</Eyebrow>
                <div className="cf-body"><Pairs row={row} /></div>
                <div className="cf-code-src">Looked up from the attribution table, not written by AI.</div>
              </section>
            )}

            {row?.explanation && (
              <div className="cf-ai"><span className="cf-ai-tag">AI explanation · not code text</span>{row.explanation}</div>
            )}
          </>
        ) : (
          <>
            <h3 id="cf-drawer-title" className="cf-drawer-title">Add a code reference</h3>
            <p className="cf-muted cf-body">Search by keywords or an article number. Nothing is added until you choose Use this provision.</p>
          </>
        )}

        <div className="cf-drawer-links">
          {provision && <a className="cf-btn is-sm is-ghost" href={codeHref(articleOf(provision) ?? provision)} onClick={onClose}>Open in code library <CIcon name="arrow" size={13} /></a>}
          <a className="cf-btn is-sm is-ghost" href="#/references" onClick={onClose}>All code references <CIcon name="arrow" size={13} /></a>
          {a && (
            <button type="button" className="cf-btn is-sm is-ghost" aria-expanded={searching} onClick={() => setSearching((v) => !v)}>
              <CIcon name="search" size={13} />Add a code reference
            </button>
          )}
        </div>
        {searching && (
          <div className="cf-embed cf-sect">
            <ProvisionSearch onAdded={(id) => { onAdded(id); }} />
          </div>
        )}
      </div>
    </Modal>
  );
}
