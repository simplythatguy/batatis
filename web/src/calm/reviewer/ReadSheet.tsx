/**
 * The application as the applicant sent it, laid out like the review: one group per section, a label and
 * the applicant's value on each line. Nothing is coloured. A line with an open item is lightly shaded and
 * says what the officer is doing with it (Asking, Look first, Not asking); a line the applicant changed
 * since the last return says so, with the earlier value on hover.
 */
import type { ReactNode } from "react";
import type { Case, Finding, FindingState, ReviewSession, RulebookGap } from "../../api/types.gen";
import { CODE_EDITION } from "../../config";
import { RetainedSourceFiles } from "../../RetainedSourceFiles";
import { Icon24, type IconName } from "../icons";
import { CodeRef } from "./CodeRef";
import { formField, formValue } from "./formFields";
import { OpenFileLink } from "./OpenFileLink";
import { citationView, documentView, isPeer, officerFinding, sectionCView, sentence } from "./packageView";
import { sentPhrase } from "./queue";
import type { SheetView } from "./sheet";
import { anchoredItems, changedFields, SECTIONS, type Section, type SheetAnchor, type WorkspaceRow } from "./workspaceView";

const HEAD: Record<Section, { title: string; sub: string; icon: IconName }> = {
  A: { title: "Applicant", sub: "Section A", icon: "user" },
  B: { title: "Project", sub: "Section B", icon: "file" },
  C: { title: "Code references", sub: "Section C", icon: "book" },
  process: { title: "Alternative path", sub: "In their words", icon: "compose" },
  D: { title: "Supporting documents", sub: "Section D", icon: "clip" },
};

const WORD = { ask: "Asking", verify: "Look first", dismissed: "Not asking" } as const;

/** One word per line, however many items sit on it: the most pressing state, with a count when several share it. */
function Tag({ found, states, onOpen }: { found: Finding[]; states: Map<string, FindingState>; onOpen: (key: string) => void }) {
  const of = (f: Finding) => states.get(f.key)?.state ?? "verify";
  const top = (["ask", "verify", "dismissed"] as const).find((s) => found.some((f) => of(f) === s))!;
  const these = found.filter((f) => of(f) === top);
  const word = `${WORD[top]}${these.length > 1 ? ` · ${these.length}` : ""}`;
  return (
    <button type="button" className="ap-tag" onClick={() => onOpen(these[0].key)} title={found.map((f) => officerFinding(f).title).join(" · ")}
      aria-label={`${these.map((f) => officerFinding(f).title).join(", ")}: ${WORD[top].toLowerCase()}. Open it in the review.`}>{word}</button>
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

  const isOpen = (anchor: string) => (gaps.get(anchor) ?? []).length > 0 || (findings.get(anchor) ?? []).some((f) => states.get(f.key)?.state !== "dismissed");
  const line = (anchor: string, label: string, value: ReactNode, field: string) => {
    const change = changes.get(formField(field));
    const here = findings.get(anchor) ?? [];
    const rules = gaps.get(anchor) ?? [];
    const open = isOpen(anchor);
    return (
      <div key={anchor} className={`ap-line${open ? " is-open" : ""}`}>
        <span className="ap-k">{sentence(label)}</span>
        <span className="ap-v">
          {value ?? <span className="ap-none">Not given</span>}
          {change && <span className="ap-chg" title={`Before: ${formValue(change.before) || "—"}`}>Changed</span>}
        </span>
        {(here.length > 0 || rules.length > 0) && (
          <span className="ap-tags">
            {here.length > 0 && <Tag found={here} states={states} onOpen={onOpen} />}
            {rules.length > 0 && <span className="ap-tag is-static" title={rules.map((g) => g.message).join(" · ")}>Required</span>}
          </span>
        )}
      </div>
    );
  };

  const refs = anchors.filter((a) => a.section === "C" && a.field.startsWith("section_c."));
  // The form's own Section C rows first; provisions only mentioned elsewhere in the text sit apart, folded.
  const formRefs = new Set([...sheet.references.map((r) => r.provision), ...(session?.section_c ?? []).map((x) => x.provision_id)]);
  const cited = refs.filter((a) => formRefs.has(a.label));
  const also = refs.filter((a) => !formRefs.has(a.label));
  const refLine = (a: SheetAnchor, label: string) => {
    const cite = session?.citations.find((x) => (x.provision_id || x.text) === a.label);
    const checks = session?.section_c.filter((x) => x.provision_id === a.label) ?? [];
    const canonical = cite?.canonical_citation || (!historical ? c.section_c.find((x) => x.provision_id === a.label)?.citation : null);
    const tones = [cite && citationView(cite), ...checks.map(sectionCView)].filter(Boolean) as { tone: string; status: string }[];
    const worst = tones.find((t) => t.tone === "blocking") ?? tones.find((t) => t.tone === "warning") ?? tones[0];
    return line(a.id, label, canonical || worst ? (
      <span className="ap-ref">
        {canonical ? <CodeRef citation={canonical} /> : <span className="ap-text">{a.label}</span>}
        {worst && <span className="ap-none">{worst.status}</span>}
      </span>
    ) : <span className="ap-text">{a.label}</span>, a.field);
  };
  const docs = anchors.filter((a) => a.section === "D" && a.field.startsWith("evidence."));
  const peer = session?.findings.find(isPeer);
  const sent = !historical && c.submitted_at ? ` · sent ${sentPhrase(c.submitted_at)}` : "";

  return (
    <article className="ap" aria-label="Application">
      <header className="ap-head">
        <h1 className="cf-h1">Application</h1>
        <p className="cf-lede is-sm">Variance, Part 1 · {CODE_EDITION}{sent}</p>
      </header>

      {SECTIONS.map((section) => (
        <section key={section} id={`sheet-${section === "process" ? "P" : section}`} className="ap-sec" aria-label={HEAD[section].title}>
          <h2 className="ap-sec-h">
            <span className="cf-sec-icon" aria-hidden="true"><Icon24 name={HEAD[section].icon} size={18} /></span>
            <span>{HEAD[section].title}<span className="cf-faint"> · {HEAD[section].sub}</span></span>
          </h2>
          <div className="ap-lines">
            {rows.filter((r) => r.section === section).map((r) => line(r.id, r.label, r.reading.value
              ? <span className="ap-text">{r.reading.value}{r.reading.unconfirmed && <span className="ap-none"> · not confirmed</span>}</span>
              : null, r.field))}

            {section === "C" && cited.map((a) => refLine(a, "Provision"))}
            {section === "C" && !cited.length && <p className="ap-empty">No code reference on file</p>}
            {section === "C" && also.length > 0 && (
              <details className="rw-fold ap-also" open={also.some((a) => isOpen(a.id)) || undefined}>
                <summary className="ap-also-h">Also mentioned in the text · {also.length}</summary>
                {also.map((a) => refLine(a, ""))}
              </details>
            )}

            {section === "D" && docs.map((a) => {
              const id = a.field.slice("evidence.".length);
              const read = session?.documents.find((d) => (a.ids ?? [id]).includes(d.id));
              const listed = sheet.documents.find((d) => d.id === id);
              const view = read ? documentView(read) : null;
              // A case review reads the applicant's stored file; its id is the one they attached.
              const fileId = (read && files.find((f) => f.name === read.file)?.file_id) || (historical ? null : listed?.fileId);
              const facts = view ? view.cells.filter((x) => x.known).map((x) => x.value) : [listed?.type, listed?.author, listed?.date].filter(Boolean);
              return line(a.id, a.label, (
                <span className="ap-ref">
                  {facts.length > 0 && <span className="ap-text">{facts.join(" · ")}</span>}
                  {fileId ? <OpenFileLink caseId={c.id} fileId={fileId} name={read?.file || listed?.fileName || a.label} label="Open" />
                    : <span className="ap-none">No file</span>}
                </span>
              ), a.field);
            })}
            {section === "process" && findings.has("process:file-checklist") && line("process:file-checklist", "Division C file", null, "div_c")}
            {(findings.has(`${section}:end`) || gaps.has(`${section}:end`)) && line(`${section}:end`, "Other items", <span className="ap-none">Not tied to one line</span>, "")}
          </div>
          {section === "D" && (
            <>
              {professional}
              <RetainedSourceFiles caseId={c.id} />
            </>
          )}
        </section>
      ))}

      {questions}
      {peer && <p className="ap-empty">Peer review may help · your call</p>}
    </article>
  );
}
