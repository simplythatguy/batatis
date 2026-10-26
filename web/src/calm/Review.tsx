import { useEffect, useState } from "react";
import { Notices } from "../components";
import { groupGaps, professionalHoldKind, professionalHoldReason } from "../humanReview";
import { useCase } from "../store";
import type { Case, Gap } from "../types";
import { scopeRedirect } from "../intakeView";
import { buildDeck, caseRules, deckProgress, gapKey } from "./deck";
import { readOnlyStatus } from "./applications";
import { useCurrentApplication } from "./begin";
import { BeforeYouSubmit } from "./ReadCards";
import { calmHref } from "./routes";
import { rankedIn } from "./relevance";
import { useSession } from "./session";
import { useDeckExtras } from "./useDeckExtras";
import { useRelevance } from "./useRelevance";
import { Icon24, type IconName } from "./icons";
import { CIcon, CompletenessNote, Dot, Eyebrow, Kbd, type DotTone } from "./ui";
import { confirmedProvisions } from "../provisions";
import { preparationGaps } from "./preparation";
import { ApplicantDrafts } from "./ApplicantDrafts";

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

/** The engineer callout, only from the professional logic already on the case. Never invented. */
export function engineerNeed(_c: Case, gaps: Gap[]): { title: string; line: string; summary: string } | null {
  const kind = professionalHoldKind(gaps);
  const line = professionalHoldReason(gaps);
  if (!line) return null;
  if (kind === "requirement") return { title: "The officer must determine the professional requirement", line, summary: "Officer determination pending" };
  if (kind === "source") return { title: "The professional requirement needs source review", line, summary: "Source review pending" };
  return { title: "Complete the required professional information and work", line, summary: "Professional information needed" };
}

export function EngineerCallout({ c, gaps, readOnly = false }: { c: Case; gaps: Gap[]; readOnly?: boolean }) {
  const need = engineerNeed(c, gaps);
  if (!need) return null;
  const officerPending = gaps.some((g) => g.severity === "blocking" && g.submissionBlocking === false);
  return (
    <section className="cf-engineer" aria-labelledby="cf-engineer-title">
      <h2 className="cf-engineer-h" id="cf-engineer-title"><CIcon name="warn" />{need.title}</h2>
      <p>{need.line}</p>
      <p>Batatis can draft your evidence plan. Professional analysis and evidence come from your engineer or architect.</p>
      {officerPending && <p>Official PDF and administrative acceptance stay on hold until the officer resolves the requirement.</p>}
      {!readOnly && <a className="cf-engineer-link" href={officerPending ? "#/application" : "#/questions?focus=section-d"}>{officerPending ? "Preview and submit" : "Open your case and proof"} <CIcon name="arrow" size={13} /></a>}
    </section>
  );
}

function worst(gaps: Gap[]): DotTone {
  if (gaps.some((g) => g.severity === "blocking")) return "blocking";
  if (gaps.length) return "warning";
  return "done";
}

/** One neutral icon per official section; the label beside it stays the Section A–D name. */
const SECTION_ICON: Record<string, IconName> = { A: "user", B: "file", C: "book", D: "review" };

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
              <span className="cf-sec-icon" aria-hidden="true"><Icon24 name={SECTION_ICON[s.letter] ?? "file"} size={18} /></span>
              <div className="cf-sec-t"><div>{s.title} <span className="cf-faint">· Section {s.letter}</span></div><div className="cf-faint">Not started</div></div>
              <Dot tone="pending" />
            </li>
          ))}
        </ul>
        <CompletenessNote />
      </aside>
    </div>
  );
}

/** Show the current case’s review or the instructions to start an application. */
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
          <p className="cf-lede is-sm">{s.note} {s.next}</p>
          <div className="cf-row-actions"><a className="cf-btn is-primary" href="#/application">View application</a></div>
          <ApplicantDrafts />
        </div>
      </div>
    );
  }
  return <CaseReview />;
}

/** Summarize shared gaps, deck progress and rule departures for the current case. */
function CaseReview() {
  const { c, gaps: currentGaps, notices, engineGaps, gapsSource, checkStatus, checkNote, checkDetail, requestCheck, reading, applicationStatus } = useCase();
  const { app, readOnly } = useCurrentApplication();
  const gaps = readOnly && gapsSource !== "engine" ? [] : currentGaps;
  const session = useSession();
  const [showAll, setShowAll] = useState(false);
  const { options } = useDeckExtras();
  const ruleFlags = caseRules(c, options).filter((r) => r.state === "departs").length;
  const deck = buildDeck(c, gaps, { ...options, seen: new Set(session.seen), includeDone: true, identify: reading.identify });
  const { done, total } = deckProgress(deck);
  const openCards = deck.filter((i) => !i.done && !i.optional).length;
  const blocking = gaps.filter((g) => g.severity === "blocking");
  const work = preparationGaps(c, gaps);
  const applicantBlocking = work.applicant.filter((g) => g.severity === "blocking");
  const officerPending = work.officer;
  const warnings = gaps.length - blocking.length;
  const checked = checkStatus === "ready" || checkStatus === "needs_answers";
  const applicantComplete = checked && !applicantBlocking.length && !work.checkNeeded.length && officerPending.some((g) => g.severity === "blocking");
  const status = readOnlyStatus(app?.status ?? applicationStatus, app?.authority ?? c.authority);
  const groups = groupGaps(gaps, new Map(engineGaps.map((g) => [g.id, g.section])));
  const pick = (...keys: string[]) => keys.flatMap((k) => groups.get(k) ?? []);
  const need = engineerNeed(c, gaps);
  // Rings never count as Section C; this only points at the library.
  const rel = useRelevance();
  const likely = rankedIn(rel.display, rel.cutoffs, ["high"], rel.rerank).length;
  const pre = c.intake?.record.plan?.pre_application;
  const departures = confirmedProvisions(c).length;

  const sections = [
    { letter: "A", title: "About you", gaps: pick("A"), ok: "Owner, representative and address are in" },
    { letter: "B", title: "Your project", gaps: pick("B", "facts"), ok: "Site, scope and your alternative are in" },
    {
      letter: "C",
      title: "Which rules apply",
      gaps: pick("C"),
      ok: departures ? `${plural(departures, "confirmed rule")} · looked up from the code, not AI-written` : "No rule confirmed yet",
      empty: departures === 0,
    },
    { letter: "D", title: "Your case and proof", gaps: pick("D", "process"), ok: "Nothing missing" },
  ];

  const go = () => { location.hash = !readOnly && !applicantComplete && openCards ? "#/questions" : "#/application"; };
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
  if (readOnly) {
    headline = status.heading;
    lede = `${status.note} ${status.next}`;
    if (checkStatus === "running" || checkStatus === "unavailable") lede += ` ${checkNote}`;
  } else if (checkStatus === "running") {
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
  } else if (applicantComplete) {
    headline = "Ready to submit for review.";
    lede = "Your required answers are in. The officer must determine the professional requirement; official PDF and administrative acceptance stay on hold.";
  } else if (applicantBlocking.length) {
    headline = `Almost there. ${plural(applicantBlocking.length, "thing")} ${applicantBlocking.length === 1 ? "stands" : "stand"} between you and submission.`;
  } else if (warnings) {
    headline = `Nothing required is missing. ${plural(warnings, "open question")}${!work.applicant.length && officerPending.length ? " with the officer" : " to look at"}.`;
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
              {checkStatus === "running" ? "Checking…" : readOnly ? "Check saved application" : checkStatus === "unavailable" ? "Try the check again" : "Check my application"} <Kbd>↵</Kbd>
            </button>
          </div>
        )}
        {checkStatus === "unavailable" && checkDetail && (
          <details className="cf-tech"><summary>Technical detail</summary><p>{checkDetail}</p></details>
        )}

        <ApplicantDrafts />

        <div className="cf-metrics">
          <div className="cf-tile cf-metric">
            <div className="cf-metric-k">{readOnly ? "Saved application" : applicantComplete ? "Required answers" : "Complete"}</div>
            <div className="cf-metric-v">{readOnly || applicantComplete ? checked ? <span className="cf-faint">Checked</span> : "—" : <>{done}<span className="cf-faint">/{total}</span></>}</div>
          </div>
          <div className="cf-tile cf-metric">
            <div className="cf-metric-k">{readOnly ? "Open administrative items" : "Left for you"}</div>
            <div className="cf-metric-v">{readOnly && !checked ? "—" : readOnly ? gaps.length : work.applicant.length}{applicantBlocking.length > 0 && <small>{applicantBlocking.length} required</small>}{officerPending.length > 0 && <small>{officerPending.length} with the officer</small>}{work.checkNeeded.length > 0 && <small>Check your changed application</small>}</div>
          </div>
        </div>

        {(gaps.length > 0 || (readOnly && !checked)) && (
          <div className="cf-list-label" title={!readOnly && gapsSource !== "engine" ? "From this browser’s list. The online check can add more." : undefined}>{applicantComplete ? "With the officer" : readOnly ? "Saved-record requirements" : "Still needed"}</div>
        )}
        {gaps.length === 0 ? (
          readOnly && !checked && <p className="cf-faint cf-row-empty">No current check yet.</p>
        ) : (
          <ul className="cf-rows">
            {shown.map((g) => {
              const key = gapKey(c, g);
              const href = key ? `#/questions?focus=${encodeURIComponent(key)}` : calmHref(g.href);
              return (
                <li key={g.id} className="cf-row">
                  <Dot tone={g.severity} />
                  <span className="cf-row-text">{g.label}</span>
                  {work.officer.includes(g) ? <span className="cf-faint cf-small">For the officer</span> : work.checkNeeded.includes(g) ? <span className="cf-faint cf-small">Check needed</span> : !readOnly && <a className="cf-row-go" href={href}>{g.id === "keyword-triage" ? "Review leads" : key ? "Answer" : "Open"} <CIcon name="arrow" size={13} /></a>}
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
        <EngineerCallout c={c} gaps={gaps} readOnly={readOnly} />
        {pre && !scopeRedirect(c) && <BeforeYouSubmit pre={pre} />}
      </div>

      <aside className="cf-glass cf-sections" aria-label="Your application">
        <Eyebrow plain>Your application</Eyebrow>
        <ul className="cf-sec-list">
          {sections.map((s) => {
            // An empty Section C is not complete: no reference has been confirmed yet.
            const sectionWork = preparationGaps(c, s.gaps);
            const officerOnly = s.gaps.length > 0 && sectionWork.officer.length === s.gaps.length;
            const tone: DotTone = readOnly && !checked ? "pending" : officerOnly ? "warning" : "empty" in s && s.empty && !s.gaps.length ? "pending" : worst(s.gaps);
            const engineer = s.letter === "D" && need;
            const summary = readOnly && !checked ? "Check the saved application" : s.letter === "C" ? `${s.ok}${s.gaps.length ? ` · ${plural(s.gaps.length, "unresolved item")}` : ""}` : sectionWork.checkNeeded.length && !sectionWork.applicant.length ? "Check your changed application" : officerOnly ? "Officer determination pending" : s.gaps.length
              ? `${engineer ? `${engineer.summary} · ` : ""}${plural(s.gaps.length, "item")} left`
              : engineer ? engineer.summary : s.ok;
            return (
              <li key={s.letter} className="cf-sec">
                <span className="cf-sec-icon" aria-hidden="true"><Icon24 name={SECTION_ICON[s.letter] ?? "file"} size={18} /></span>
                <div className="cf-sec-t">
                  <div>{s.title} <span className="cf-faint">· Section {s.letter}</span></div>
                  <div className="cf-faint">
                    {summary}
                    {s.letter === "C" && <> · <a className="cf-inline-link" href={likely ? "#/code?filter=attention" : "#/code"}>Browse the code</a></>}
                    {s.letter === "C" && likely > 0 && <div className="cf-faint">{plural(likely, "article")} likely relate to your project</div>}
                    {s.letter === "C" && ruleFlags > 0 && <div className="cf-faint">{plural(ruleFlags, "rule check")} {ruleFlags === 1 ? "flags" : "flag"} a departure · <a className="cf-inline-link" href="#/questions?first=code">See {ruleFlags === 1 ? "it" : "them"}</a></div>}
                  </div>
                </div>
                <Dot tone={engineer && tone === "done" ? "warning" : tone} />
                <span className="cf-sr">{officerOnly ? "officer determination pending" : tone === "done" ? "complete" : tone === "blocking" ? "required items missing" : tone === "pending" ? "not started" : "open questions"}</span>
              </li>
            );
          })}
        </ul>
        <div className="cf-sec-actions">
          {!readOnly && !applicantComplete && openCards > 0 ? (
            <>
              <a className="cf-btn is-primary is-grow" href="#/questions">Answer {openCards} remaining {checked && <Kbd>↵</Kbd>}</a>
              <a className="cf-btn" href="#/application">Preview</a>
            </>
          ) : (
            <a className="cf-btn is-primary is-grow" href="#/application">Preview application {checked && <Kbd>↵</Kbd>}</a>
          )}
        </div>
        <CompletenessNote />
      </aside>
    </div>
  );
}
