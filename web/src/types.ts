/**
 * Case model shared by every screen. Mirrors the engine case record (2-week-build.md,
 * "Accuracy"): every value on screen is a Fact with a kind and a source. Nothing is typed by
 * the tool; it points to a source, computes from sources, or proposes for the user to confirm.
 */

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
  /** Set once a file route has actually read the bytes. */
  read: boolean;
  /** Set when the upload attempt failed. Empty while a try is in flight. */
  error?: string;
  sha256?: string;
  /** True only when the engine could not be reached. A missing route is not this. */
  unreachable?: boolean;
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
  /** Set when search or identify suggested the provision and the applicant has not confirmed it. */
  suggestion?: "search" | "identify";
  /**
   * False when the card is a question drawn from the applicant's words
   * and no article has been ranked for it yet.
   */
  identified?: boolean;
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
  /** Objective and function titles by code (live rows carry them from the engine). */
  terms?: Record<string, string>;
  /** AI-written, never code text. Absent on live lookup rows until the engine writes explanations. */
  explanation?: string;
}

export type ProcessFieldId =
  | "rationale"
  | "risk"
  | "mitigation"
  | "assumptions"
  | "maintenance"
  | "qualifications";

/** Empty until the applicant picks. PUT /cases/{id}/jurisdiction records the choice. */
export type AuthorityId = "" | "calgary" | "edmonton";

export type GapSeverity = "blocking" | "warning";

export interface Gap {
  id: string;
  severity: GapSeverity;
  label: string;
  /** Hash route that fixes the gap. */
  href: string;
}

export type ApplicantType = "manufacturer" | "contractor" | "homebuilder" | "builder" | "designer" | "owner";

export interface Case {
  id: string;
  title: string;
  applicantType: ApplicantType;
  /** Set only when this case was opened from "Try an example". */
  exampleId?: string;
  codeEdition: string;
  /** Empty until the applicant picks an authority. Sent only on POST /cases. */
  authority: AuthorityId;
  description: string;
  files: CaseFile[];
  facts: Fact[];
  questions: Question[];
  candidates: Candidate[];
  sectionC: SectionCRow[];
  /** Written by the applicant only; the tool supplies prompts, never content. */
  process: Record<ProcessFieldId, string>;
  /**
   * True when the Division C screen or a Section D issue says practice of engineering applies.
   * Applicant yes/no answers do not set this, and they do not clear it.
   */
  practiceOfEngineering?: true | false | "unknown";
}
