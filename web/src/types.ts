/**
 * Case model shared by every screen. Mirrors the engine case record (2-week-build.md,
 * "Accuracy"): every value on screen is a Fact with a kind and a source. Nothing is typed by
 * the tool; it points to a source, computes from sources, or proposes for the user to confirm.
 */

/** exact = code database or form; pointed = a span from the user's words or files;
 *  computed = code over exact and pointed values; proposed = AI judgement, needs a click. */
export type FactKind = "exact" | "pointed" | "computed" | "proposed";

export type SourceType = "code" | "file" | "user_text" | "drawing" | "user_click";

/** PDF user-space box, in points, on `page`. */
export interface BBox {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface Source {
  type: SourceType;
  /** File name, provision citation, or a short description of where the user said it. */
  ref: string;
  page?: number;
  bbox?: BBox;
  /** Verbatim span the value was pointed from. */
  quote?: string;
}

export type FactStatus = "confirmed" | "unconfirmed";

export interface Fact {
  id: string;
  /** Case field this fact fills, e.g. `owner` or `product.permeance`. */
  field: string;
  value: string;
  kind: FactKind;
  source: Source;
  /** 0..1; shown for proposed facts. */
  confidence?: number;
  status: FactStatus;
  /** Computed facts only: the formula, shown as written. */
  formula?: string;
  /** Computed facts only: ids of the facts the formula reads. */
  inputs?: string[];
}

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

export type AttributionStatus = "direct" | "inherited" | "no-row";

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
  /** AI-written, never code text. */
  explanation: string;
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
}
