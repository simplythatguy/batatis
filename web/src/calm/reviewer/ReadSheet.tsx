/**
 * The application as the applicant sent it: the paper sheet, A to D and the alternative path. A field
 * with a finding carries a dot and one word (Ask, Dismissed, Look) that opens that finding; a field the
 * applicant changed since the last return says so, with the earlier value on hover.
 */
import type { ReactNode } from "react";
import type { Case, Finding, FindingState, ReviewSession, RulebookGap } from "../../api/types.gen";
import { CODE_EDITION } from "../../config";
import { localField } from "../../intakeFields";
import { RetainedSourceFiles } from "../../RetainedSourceFiles";
import { CodeRef } from "./CodeRef";
import { OpenFileLink } from "./OpenFileLink";
import { citationView, documentView, isPeer, sectionCView } from "./packageView";
import { sentPhrase } from "./queue";
import type { SheetView } from "./sheet";
import { anchoredItems, changedFields, SECTIONS, type Section, type SheetAnchor, type WorkspaceRow } from "./workspaceView";

const TITLE: Record<Section, string> = { A: "A · Applicant", B: "B · Project", C: "C · Code references", process: "Alternative path · the applicant’s own words", D: "D · Supporting documents" };

function Marker({ f, state, onOpen }: { f: Finding; state: FindingState | undefined; onOpen: (key: string) => void }) {
  const s = state?.state ?? "verify";
  const word = s === "dismissed" ? "Dismissed" : s === "ask" ? "Ask" : "Look";
  const tone = s === "dismissed" ? "pending" : f.severity;
  return (
    <button type="button" className="rw-mark" onClick={() => onOpen(f.key)} title={f.label}
      aria-label={`${f.label}: ${word.toLowerCase()}. Open the finding.`}>
      <span className={`cf-dot is-${tone}${s === "verify" ? " is-ring" : ""}`} aria-hidden="true" />{word}
    </button>
  );
}

export function ReadSheet({ c, sheet, rows, anchors, session, rulebook, states, historical, professional, questions, onOpen }: {
  c: Case;
  sheet: SheetView;
  rows: WorkspaceRow[];
  anchors: SheetAnchor[];
  session: ReviewSession | null;
  rulebook: RulebookGap[];
  states: Map<string, FindingState>;
  historical: boolean;
  professional: ReactNode;
  questions: ReactNode;
  onOpen: (key: string) => void;
}) {
  const changes = historical ? new Map() : changedFields(c);
  const findings = anchoredItems((session?.findings ?? []).filter((f) => !isPeer(f)), anchors);
  const gaps = anchoredItems(rulebook, anchors);
  const files = session?.files ?? [];

  const marks = (anchor: string) => (
    <>
      {(findings.get(anchor) ?? []).map((f) => <Marker key={f.key} f={f} state={states.get(f.key)} onOpen={onOpen} />)}
      {(gaps.get(anchor) ?? []).map((g) => <span key={g.id} className="rw-mark is-static" title={g.message}><span className="cf-dot is-blocking" aria-hidden="true" />Required</span>)}
    </>
  );
  const row = (anchor: string, label: ReactNode, value: ReactNode, field: string) => {
    const change = changes.get(localField(field));
    return (
      <div key={anchor} className="rw-kv">
        <span className="rw-k">{label}</span>
        <span className="rw-v">
          {value}
          {change && <span className="rw-chg" title={`Before: ${change.before || "—"}`}>Changed</span>}
          {marks(anchor)}
        </span>
      </div>
    );
  };

  const refs = anchors.filter((a) => a.section === "C" && a.field.startsWith("section_c."));
  const docs = anchors.filter((a) => a.section === "D" && a.field.startsWith("evidence."));
  const peer = session?.findings.find(isPeer);

  return (
    <article className="cf-sheet rw-sheet" aria-label="Application">
      <h2>Safety Codes Variance · Part 1</h2>
      <div className="cf-sheet-sub">{CODE_EDITION}{!historical && c.submitted_at ? ` · sent ${sentPhrase(c.submitted_at)}` : ""}</div>

      {SECTIONS.map((section) => (
        <section key={section} aria-label={TITLE[section]}>
          <h4>{TITLE[section]}</h4>
          {rows.filter((r) => r.section === section).map((r) => row(r.id, r.label, r.reading.value
            ? <span className="rw-text">{r.reading.value}{r.reading.unconfirmed && <span className="rw-quiet"> · not confirmed</span>}</span>
            : r.reading.required ? <span className="cf-sheet-missing">— missing</span> : <span className="rw-quiet">—</span>, r.field))}

          {section === "C" && refs.map((a) => {
            const cite = session?.citations.find((x) => (x.provision_id || x.text) === a.label);
            const checks = session?.section_c.filter((x) => x.provision_id === a.label) ?? [];
            const canonical = cite?.canonical_citation || (!historical ? c.section_c.find((x) => x.provision_id === a.label)?.citation : null);
            const tones = [cite && citationView(cite), ...checks.map(sectionCView)].filter(Boolean) as { tone: string; status: string }[];
            const worst = tones.find((t) => t.tone === "blocking") ?? tones.find((t) => t.tone === "warning") ?? tones[0];
            return row(a.id, <span className="pr-mono">{a.label}</span>, (
              <>
                {canonical && <CodeRef citation={canonical} />}
                {worst && <span className="rw-mark is-static" title={tones.map((t) => t.status).join(" · ")}><span className={`cf-dot is-${worst.tone}`} aria-hidden="true" />{worst.status}</span>}
              </>
            ), a.field);
          })}
          {section === "C" && !refs.length && <p className="rw-quiet">No code reference on file</p>}

          {section === "D" && (
            <>
              {docs.map((a) => {
                const id = a.field.slice("evidence.".length);
                const read = session?.documents.find((d) => d.id === id);
                const listed = sheet.documents.find((d) => d.id === id);
                const view = read ? documentView(read) : null;
                const fileId = read ? files.find((f) => f.name === read.file)?.file_id : historical ? null : listed?.fileId;
                const facts = view ? view.cells.filter((x) => x.known).map((x) => x.value) : [listed?.type, listed?.author, listed?.date].filter(Boolean);
                return row(a.id, a.label, (
                  <>
                    <span className="rw-text">{facts.join(" · ") || "—"}</span>
                    {fileId ? <OpenFileLink caseId={c.id} fileId={fileId} name={read?.file || listed?.fileName || a.label} label="Open" /> : <span className="cf-sheet-missing"> · no file</span>}
                  </>
                ), a.field);
              })}
              {professional}
              <RetainedSourceFiles caseId={c.id} />
            </>
          )}
          {section === "process" && findings.has("process:file-checklist") && row("process:file-checklist", "Division C file", null, "div_c")}
          {(findings.has(`${section}:end`) || gaps.has(`${section}:end`)) && row(`${section}:end`, "Other", null, "")}
        </section>
      ))}

      {questions}
      {peer && <p className="rw-quiet rw-peer"><span className="cf-dot is-warning" aria-hidden="true" />Peer review may help · your call</p>}
    </article>
  );
}
