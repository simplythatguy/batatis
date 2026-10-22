import { useEffect, useState } from "react";
import { Notices } from "../components";
import { groupGaps, isProfessionalHold, professionalFlagLines } from "../humanReview";
import { professionalConfirmed } from "../professional";
import { useCase } from "../store";
import type { Case, Gap } from "../types";
import { forkOf, scopeRedirect } from "../intakeView";
import { buildDeck, deckProgress, gapKey } from "./deck";
import { readOnlyStatus } from "./applications";
import { useCurrentApplication } from "./begin";
import { BeforeYouSubmit, ForkNote } from "./ReadCards";
import { calmHref } from "./routes";
import { rankedIn } from "./relevance";
import { useSession } from "./session";
import { useRelevance } from "./useRelevance";
import { CIcon, Dot, Eyebrow, Kbd, type DotTone } from "./ui";

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

/** The engineer callout, only from the professional logic already on the case. Never invented. */
export function engineerNeed(c: Case, gaps: Gap[]): { title: string; line: string } | null {
  const confirmed = professionalConfirmed(c.facts);
  const hold = gaps.some(isProfessionalHold);
  if (c.practiceOfEngineering === true && !confirmed) {
    return { title: "Your case and proof needs an engineer or architect", line: professionalFlagLines(c)[0] };
  }
  if (c.practiceOfEngineering === "unknown" && !confirmed) {
    return { title: "Your case and proof may need an engineer or architect", line: professionalFlagLines(c)[0] };
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
      <a className="cf-engineer-link" href="#/questions?focus=section-d">Open your case and proof <CIcon name="arrow" size={13} /></a>
    </section>
  );
}

function worst(gaps: Gap[]): DotTone {
  if (gaps.some((g) => g.severity === "blocking")) return "blocking";
  if (gaps.length) return "warning";
  return "done";
}

/** Before an application exists: what the review will hold, and the one way to start it. */
export function NothingYet({ title, lede, page }: { title: string; lede: string; page: "review" | "application" }) {
  const sections = [
    { letter: "A", title: "About you" },
    { letter: "B", title: "Your project" },
    { letter: "C", title: "Which rules apply" },
    { letter: "D", title: "Your case and proof" },
  ];
  return (
    <div className="cf-review is-empty">
      <div className="cf-review-main">
        <h1 className="cf-h1" tabIndex={-1}>{title}</h1>
        <p className="cf-lede is-sm">{lede}</p>
        <div className="cf-row-actions">
          <a className="cf-btn is-primary" href="#/">Describe your project</a>
        </div>
        <div className="cf-list-label">Still needed</div>
        <ul className="cf-rows">
          <li className="cf-row">
            <Dot tone="blocking" />
            <span className="cf-row-text">A description of what you’re building differently</span>
            <a className="cf-row-go" href="#/">Describe <CIcon name="arrow" size={13} /></a>
          </li>
        </ul>
      </div>
      <aside className="cf-glass cf-sections" aria-label={page === "review" ? "Your application" : "The variance form"}>
        <Eyebrow plain>Your application</Eyebrow>
        <ul className="cf-sec-list">
          {sections.map((s) => (
            <li key={s.letter} className="cf-sec">
              <span className="cf-sec-letter" aria-hidden="true">{s.letter}</span>
              <div className="cf-sec-t"><div>{s.title} <span className="cf-faint">· Section {s.letter}</span></div><div className="cf-faint">Not started</div></div>
              <Dot tone="pending" />
            </li>
          ))}
        </ul>
        <p className="cf-faint cf-small cf-disclaimer">Checks administrative completeness only. It never says the design complies or is safe.</p>
      </aside>
    </div>
  );
}

export function Review() {
  const { phase } = useCase();
  const { app } = useCurrentApplication();
  if (phase !== "case") return <NothingYet page="review" title="Nothing to review yet." lede="Describe what you’re building and Batatis lists what your application still needs, section by section." />;
  if (app?.status === "refused") {
    const s = readOnlyStatus(app.status, app.authority);
    return (
      <div className="cf-review">
        <div className="cf-review-main">
          <h1 className="cf-h1" tabIndex={-1}>{s.heading}</h1>
          <p className="cf-lede is-sm">{s.note}</p>
          <div className="cf-row-actions"><a className="cf-btn is-primary" href="#/application">View application</a></div>
        </div>
      </div>
    );
  }
  return <CaseReview />;
}

function CaseReview() {
  const { c, gaps, notices, engineGaps, gapsSource, checkStatus, checkNote, checkDetail, requestCheck, reading } = useCase();
  const session = useSession();
  const [showAll, setShowAll] = useState(false);
  const deck = buildDeck(c, gaps, { seen: new Set(session.seen), includeDone: true, identify: reading.identify });
  const { done, total } = deckProgress(deck);
  const openCards = deck.filter((i) => !i.done && !i.optional).length;
  const blocking = gaps.filter((g) => g.severity === "blocking");
  const warnings = gaps.length - blocking.length;
  const checked = checkStatus === "ready" || checkStatus === "needs_answers";
  const groups = groupGaps(gaps, new Map(engineGaps.map((g) => [g.id, g.section])));
  const pick = (...keys: string[]) => keys.flatMap((k) => groups.get(k) ?? []);
  const need = engineerNeed(c, gaps);
  // Rings never count as Section C; this only points at the library.
  const rel = useRelevance();
  const likely = rankedIn(rel.display, rel.cutoffs, ["high"], rel.rerank).length;
  const fork = forkOf(c);
  const pre = c.intake?.record.plan?.pre_application;
  const departures = c.sectionC.filter((r) => c.candidates.find((a) => a.id === r.candidateId)?.answer === "yes").length;

  const sections = [
    { letter: "A", title: "About you", gaps: pick("A"), ok: "Owner, representative and address are in" },
    { letter: "B", title: "Your project", gaps: pick("B", "facts"), ok: "Site, scope and your alternative are in" },
    {
      letter: "C",
      title: "Which rules apply",
      gaps: pick("C"),
      ok: c.sectionC.length ? `${plural(c.sectionC.length, "rule")} · looked up from the code, not AI-written` : "No rule chosen yet",
      empty: c.sectionC.length === 0,
    },
    { letter: "D", title: "Your case and proof", gaps: pick("D", "process"), ok: "Nothing missing" },
  ];

  const go = () => { location.hash = openCards ? "#/questions" : "#/application"; };
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (e.key !== "Enter" || e.defaultPrevented || document.querySelector("dialog[open]")) return;
      const t = e.target as HTMLElement;
      if (t !== document.body && t.tagName !== "H1") return;
      // While a check runs, Enter waits for it rather than leaving the page mid-check.
      if (checkStatus === "running") return;
      e.preventDefault();
      if (!checked) void requestCheck(checkStatus === "unavailable");
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
        {fork && !scopeRedirect(c) && (
          <section className="cf-review-fork" aria-labelledby="cf-fork-h">
            <h2 id="cf-fork-h" className="cf-list-label">Your path</h2>
            <ForkNote fork={fork} />
          </section>
        )}
        {pre && !scopeRedirect(c) && <BeforeYouSubmit pre={pre} />}
      </div>

      <aside className="cf-glass cf-sections" aria-label="Your application">
        <Eyebrow plain>Your application</Eyebrow>
        <ul className="cf-sec-list">
          {sections.map((s) => {
            // An empty Section C is not complete: no reference has been confirmed yet.
            const tone: DotTone = "empty" in s && s.empty && !s.gaps.length ? "pending" : worst(s.gaps);
            const engineer = s.letter === "D" && need;
            const summary = s.gaps.length
              ? `${engineer ? "Engineer needed · " : ""}${plural(s.gaps.length, "item")} left`
              : engineer ? "Engineer needed" : s.letter === "C" && !departures && c.sectionC.length ? `${s.ok} · no departure confirmed` : s.ok;
            return (
              <li key={s.letter} className="cf-sec">
                <span className="cf-sec-letter" aria-hidden="true">{s.letter}</span>
                <div className="cf-sec-t">
                  <div>{s.title} <span className="cf-faint">· Section {s.letter}</span></div>
                  <div className="cf-faint">
                    {summary}
                    {s.letter === "C" && <> · <a className="cf-inline-link" href={likely ? "#/code?filter=attention" : "#/code"}>Browse the code</a></>}
                    {s.letter === "C" && likely > 0 && <div className="cf-faint">{plural(likely, "article")} likely relate to your project</div>}
                  </div>
                </div>
                <Dot tone={engineer && tone === "done" ? "warning" : tone} />
                <span className="cf-sr">{tone === "done" ? "complete" : tone === "blocking" ? "required items missing" : tone === "pending" ? "not started" : "open questions"}</span>
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
