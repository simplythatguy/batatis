import { useEffect, useState } from "react";
import { Notices } from "../components";
import { groupGaps, isProfessionalHold, professionalFlagLines } from "../humanReview";
import { professionalConfirmed } from "../professional";
import { useCase } from "../store";
import type { Case, Gap } from "../types";
import { buildDeck, deckProgress, gapKey } from "./deck";
import { calmHref } from "./routes";
import { useSession } from "./session";
import { CIcon, Dot, Eyebrow, Kbd, type DotTone } from "./ui";

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

/** The engineer callout, only from the professional logic already on the case. Never invented. */
export function engineerNeed(c: Case, gaps: Gap[]): { title: string; line: string } | null {
  const confirmed = professionalConfirmed(c.facts);
  const hold = gaps.some(isProfessionalHold);
  if (c.practiceOfEngineering === true && !confirmed) {
    return { title: "An engineer or architect is required for Section D", line: professionalFlagLines(c)[0] };
  }
  if (c.practiceOfEngineering === "unknown" && !confirmed) {
    return { title: "Section D may need an engineer or architect", line: professionalFlagLines(c)[0] };
  }
  if (hold) {
    return { title: "The official PDF is on hold for a registered professional", line: "A professional item is routed to the officer until an engineer or architect confirms a seal or registration number." };
  }
  return null;
}

export function EngineerCallout({ c, gaps }: { c: Case; gaps: Gap[] }) {
  const need = engineerNeed(c, gaps);
  if (!need) return null;
  return (
    <section className="cf-engineer" aria-labelledby="cf-engineer-title">
      <h2 className="cf-engineer-h" id="cf-engineer-title"><CIcon name="warn" />{need.title}</h2>
      <p>{need.line}</p>
      <p>Batatis can list what that evidence must address, but it can’t write it.</p>
      <a className="cf-engineer-link" href="#/questions?focus=section-d">Open Section D <CIcon name="arrow" size={13} /></a>
    </section>
  );
}

function worst(gaps: Gap[]): DotTone {
  if (gaps.some((g) => g.severity === "blocking")) return "blocking";
  if (gaps.length) return "warning";
  return "done";
}

export function Review() {
  const { c, gaps, notices, engineGaps, gapsSource, checkStatus, checkNote, checkDetail, requestCheck } = useCase();
  const session = useSession();
  const [showAll, setShowAll] = useState(false);
  const deck = buildDeck(c, gaps, { seen: new Set(session.seen), includeDone: true });
  const { done, total } = deckProgress(deck);
  const openCards = deck.filter((i) => !i.done && !i.optional).length;
  const blocking = gaps.filter((g) => g.severity === "blocking");
  const warnings = gaps.length - blocking.length;
  const checked = checkStatus === "ready" || checkStatus === "needs_answers";
  const groups = groupGaps(gaps, new Map(engineGaps.map((g) => [g.id, g.section])));
  const pick = (...keys: string[]) => keys.flatMap((k) => groups.get(k) ?? []);
  const need = engineerNeed(c, gaps);
  const departures = c.sectionC.filter((r) => c.candidates.find((a) => a.id === r.candidateId)?.answer === "yes").length;

  const sections = [
    { letter: "A", title: "Applicant", gaps: pick("A"), ok: "Owner, representative and address are in" },
    { letter: "B", title: "Project & alternative", gaps: pick("B", "facts"), ok: "Site, scope and your alternative are in" },
    {
      letter: "C",
      title: "Code references",
      gaps: pick("C"),
      ok: c.sectionC.length ? `${plural(c.sectionC.length, "sentence")} · looked up, not AI-written` : "No code reference yet",
    },
    { letter: "D", title: "Evidence & your case", gaps: pick("D", "process"), ok: "Nothing missing" },
  ];

  const go = () => { location.hash = openCards ? "#/questions" : "#/application"; };
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (e.key !== "Enter" || e.defaultPrevented || document.querySelector("dialog[open]")) return;
      const t = e.target as HTMLElement;
      if (t !== document.body && t.tagName !== "H1") return;
      e.preventDefault();
      if (!checked && checkStatus !== "running") void requestCheck(checkStatus === "unavailable");
      else go();
    };
    document.addEventListener("keydown", on);
    return () => document.removeEventListener("keydown", on);
  });

  let headline: string;
  let lede = "";
  if (checkStatus === "running") {
    headline = "Checking your application…";
    lede = checkNote;
  } else if (checkStatus === "unavailable") {
    headline = "The check couldn’t finish.";
    lede = checkNote;
  } else if (checkStatus === "stale") {
    headline = "You changed something since the last check.";
    lede = checkNote;
  } else if (!checked) {
    headline = "Let’s check your application.";
    lede = "Batatis saves your draft, looks for the code that applies and lists anything missing. Nothing is submitted.";
  } else if (blocking.length) {
    headline = `Almost there. ${plural(blocking.length, "thing")} ${blocking.length === 1 ? "stands" : "stand"} between you and the official PDF.`;
  } else if (warnings) {
    headline = `Nothing required is missing. ${plural(warnings, "open question")} to look at.`;
  } else {
    headline = "Nothing required is missing.";
  }

  const shown = showAll ? gaps : gaps.slice(0, 6);
  return (
    <div className="cf-review">
      <div className="cf-review-main">
        <Eyebrow>Review</Eyebrow>
        <h1 className="cf-h1" tabIndex={-1}>{headline}</h1>
        {lede && <p className="cf-lede is-sm" role="status">{lede}</p>}
        {!checked && (
          <div className="cf-row-actions">
            <button type="button" className="cf-btn is-primary" disabled={checkStatus === "running"} onClick={() => void requestCheck(checkStatus === "unavailable")}>
              {checkStatus === "running" ? "Checking…" : checkStatus === "unavailable" ? "Try the check again" : "Check my application"} <Kbd>↵</Kbd>
            </button>
          </div>
        )}
        {checkStatus === "unavailable" && checkDetail && (
          <details className="cf-tech"><summary>Technical detail</summary><p>{checkDetail}</p></details>
        )}

        <div className="cf-metrics">
          <div className="cf-tile cf-metric">
            <div className="cf-metric-k">Complete</div>
            <div className="cf-metric-v">{done}<span className="cf-faint">/{total}</span></div>
          </div>
          <div className="cf-tile cf-metric">
            <div className="cf-metric-k">Left to answer</div>
            <div className="cf-metric-v">{gaps.length}{blocking.length > 0 && <small>{blocking.length} required</small>}</div>
          </div>
        </div>

        <div className="cf-list-label">Still needed</div>
        {gapsSource !== "engine" && <p className="cf-faint cf-small cf-list-note">From this browser’s list. The online check can add more.</p>}
        {gaps.length === 0 ? (
          <p className="cf-faint cf-row-empty">Nothing on the list.</p>
        ) : (
          <ul className="cf-rows">
            {shown.map((g) => {
              const key = gapKey(c, g);
              const href = key ? `#/questions?focus=${encodeURIComponent(key)}` : calmHref(g.href);
              return (
                <li key={g.id} className="cf-row">
                  <Dot tone={g.severity} />
                  <span className="cf-row-text">{g.label}</span>
                  <a className="cf-row-go" href={href}>{key ? "Answer" : "Open"} <CIcon name="arrow" size={13} /></a>
                </li>
              );
            })}
          </ul>
        )}
        {gaps.length > 6 && (
          <button type="button" className="cf-btn is-ghost is-sm" aria-expanded={showAll} onClick={() => setShowAll((v) => !v)}>
            {showAll ? "Show fewer" : `Show all ${gaps.length}`}
          </button>
        )}
        {notices.length > 0 && <div className="cf-notices"><Notices notices={notices} /></div>}
        <EngineerCallout c={c} gaps={gaps} />
      </div>

      <aside className="cf-glass cf-sections" aria-label="Your application">
        <Eyebrow plain>Your application</Eyebrow>
        <ul className="cf-sec-list">
          {sections.map((s) => {
            const tone = worst(s.gaps);
            const engineer = s.letter === "D" && need;
            const summary = s.gaps.length
              ? `${engineer ? "Engineer needed · " : ""}${plural(s.gaps.length, "item")} left`
              : engineer ? "Engineer needed" : s.letter === "C" && !departures && c.sectionC.length ? `${s.ok} · no departure confirmed` : s.ok;
            return (
              <li key={s.letter} className="cf-sec">
                <span className="cf-sec-letter" aria-hidden="true">{s.letter}</span>
                <div className="cf-sec-t">
                  <div>Section {s.letter} · {s.title}</div>
                  <div className="cf-faint">{summary}</div>
                </div>
                <Dot tone={engineer && tone === "done" ? "warning" : tone} />
                <span className="cf-sr">{tone === "done" ? "complete" : tone === "blocking" ? "required items missing" : "open questions"}</span>
              </li>
            );
          })}
        </ul>
        <div className="cf-sec-actions">
          {openCards > 0 ? (
            <>
              <a className="cf-btn is-primary is-grow" href="#/questions">Answer {openCards} remaining {checked && <Kbd>↵</Kbd>}</a>
              <a className="cf-btn" href="#/application">Preview</a>
            </>
          ) : (
            <a className="cf-btn is-primary is-grow" href="#/application">Preview application {checked && <Kbd>↵</Kbd>}</a>
          )}
        </div>
        <p className="cf-faint cf-small cf-disclaimer">Checks administrative completeness only. It never says the design complies or is safe.</p>
      </aside>
    </div>
  );
}
