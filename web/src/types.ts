/**
 * Case model shared by every screen. Mirrors the engine case record (2-week-build.md,
 * "Accuracy"): every value on screen is a Fact with a kind and a source. Nothing is typed by
 * the tool; it points to a source, computes from sources, or proposes for the user to confirm.
 */

import type { IdentifyMode, IdentifyResult } from "./api/identify";
import type { FactInput, SourceInput } from "./api/types.gen";

/** Fact, Source and their enums are the engine's (engine/models.py via src/api/types.gen.ts).
 *  exact = code database or form; pointed = a span from the user's words or files;
 *  computed = code over exact and pointed values (with `formula` and `inputs`);
 *  proposed = AI judgement, needs a click. */
export type Source = SourceInput;
export type SourceType = Source["type"];
export type FactKind = FactInput["kind"];
export type FactStatus = NonNullable<FactInput["status"]>;

/** A fact as the web holds it: the engine's input shape with the id and status always set.
 *  An engine response `Fact` is assignable to it. `source.bbox` is [x0, y0, x1, y1] in PDF points. */
export type Fact = FactInput & { id: string; status: FactStatus };

export interface CaseFile {
  id: string;
  name: string;
  pages?: number;
  /** Set by the engine once it has read the file. */
  read: boolean;
}

export interface Question {
  id: string;
  text: string;
  /** Why the question is asked, in one line. */
  why: string;
  /** The fact field an answer fills. */
  field: string;
  answer?: string;
}

/** A verbatim span copied from the code database, with its built citation. */
export interface CodeQuote {
  text: string;
  citation: string;
}

export type CandidateAnswer = "yes" | "no" | "not-sure";

/** One candidate departure, confirmed in plain language rather than by article number. */
export interface Candidate {
  id: string;
  /** Plain-language name of what the requirement is about. */
  topic: string;
  provision: string;
  part: number;
  /** The benchmark acceptable solution the design most likely departs from. */
  benchmark: boolean;
  quote: CodeQuote;
  /** One line describing the departure, written for the applicant to accept or reject. */
  departure: string;
  /** Asked when the applicant answers "Not sure". */
  clarifyingQuestion: string;
  answer: CandidateAnswer | null;
}

/** `unavailable`: the source gave no attribution row to look up (not the same as "no row in the table"). */
export type AttributionStatus = "direct" | "inherited" | "no-row" | "unavailable";

/** One bracket from the attribution table: functions paired with objectives. */
export interface AttributionPair {
  bracket: string;
  functions: string[];
  objectives: string[];
}

export interface IntentStatement {
  objective: string | null;
  text: string;
}

/** Section C row: deterministic lookup after the article is confirmed. */
export interface SectionCRow {
  candidateId: string;
  provision: string;
  citation: string;
  pairs: AttributionPair[];
  attributionStatus: AttributionStatus;
  /** Inherited rows: the provision whose table row applies. */
  inheritedFrom?: string;
  /** NBC 2020 Intent Statements, explanatory only. */
  intent: IntentStatement[];
  /** The national 2020 intent statement is attributed differently from NBC(AE) 2023. */
  differs: boolean;
  differsDetail?: string;
  /** Objective and function titles by code (live rows carry them from the engine). */
  terms?: Record<string, string>;
  /** AI-written, never code text. Absent on live lookup rows until the engine writes explanations. */
  explanation?: string;
  /** Rows from an accepted Code ID card: taken from the stored identify payload, not POST /section-c. */
  codeId?: {
    title: string;
    answer: CodeIdAnswer;
    /** Verbatim code text as returned; `clipped` when it is not the whole sentence. */
    quote: string | null;
    clipped: boolean;
    explainer?: { text: string; source: "deterministic" | "ai_written" };
    mode: IdentifyMode;
  };
}

/** The applicant's answer on a Code ID article card. "no" = doesn't apply to this project. */
export type CodeIdAnswer = "yes" | "not-sure" | "no";

/** An open question recorded from Code ID: a "Not sure" card, or "None of these fit" for the officer. */
export interface CodeIdQuestion {
  id: string;
  /** Article id the question is about; null for "none of these fit". */
  provision: string | null;
  text: string;
  why: string;
  to: "applicant" | "officer";
}

/** The last identify run for this case, kept in the browser with the applicant's answers. */
export interface CodeIdRun {
  prose: string;
  result: IdentifyResult;
  /** Keyed by article id (`provision`). */
  answers: Record<string, CodeIdAnswer>;
  questions: CodeIdQuestion[];
  /** Outcome of the last POST /identify/confirm. */
  confirm?: { ok: boolean; provisions: string[]; detail?: string };
}

export type ProcessFieldId = "rationale" | "risk" | "mitigation" | "assumptions";

export type GapSeverity = "blocking" | "warning";

export interface Gap {
  id: string;
  severity: GapSeverity;
  label: string;
  /** Hash route that fixes the gap. */
  href: string;
}

export type ApplicantType = "manufacturer" | "contractor" | "builder" | "designer" | "owner";

export interface Case {
  id: string;
  title: string;
  applicantType: ApplicantType;
  codeEdition: string;
  description: string;
  files: CaseFile[];
  facts: Fact[];
  questions: Question[];
  candidates: Candidate[];
  sectionC: SectionCRow[];
  /** Written by the applicant only; the tool supplies prompts, never content. */
  process: Record<ProcessFieldId, string>;
  /** Engine case id (POST /cases), created on the first Code ID run. */
  engineCaseId?: string;
  /** Code ID results. While absent, Code check shows the fixture candidates as example data. */
  codeId?: CodeIdRun;
}
