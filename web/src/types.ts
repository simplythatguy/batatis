/**
 * Case model shared by every screen. Mirrors the engine case record (2-week-build.md,
 * "Accuracy"): every value on screen is a Fact with a kind and a source. Nothing is typed by
 * the tool; it points to a source, computes from sources, or proposes for the user to confirm.
 */

import type { FactInput, IdentifyResult, IntakeRecord, SourceInput } from "./api/types.gen";
import type { ProfessionalResult, SectionDPlan } from "./api/client";

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
  /** The engine's file id once uploaded; intake reads the file by this id. */
  engineId?: string;
}

/**
 * The latest intake run (docs/api/intake.md): the text it read, the record (pointers, file
 * reports, conflicts, plan) and the ids of the facts this run wrote. Derived from the engine;
 * the facts themselves live in `Case.facts` like every other value.
 */
export interface IntakeState {
  /** Null when a reopened record cannot be matched to the current description. */
  text: string | null;
  /** Visit-local file edits invalidate the last run, including removal of every file. */
  filesChanged?: true;
  record: IntakeRecord;
  factIds: string[];
  /** This run's facts as read (browser field names), so a confirmed card still shows what it confirmed. */
  facts: Fact[];
}

export interface Question {
  id: string;
  text: string;
  /** Why the question is asked, in one line. */
  why: string;
  /** The fact field an answer fills. */
  field: string;
  answer?: string;
  /** Set when article ranking or an article decision created the question. */
  kind?: "intake" | "article";
  /** Code-check card, kept when the id is replaced by the engine's question id. */
  cardId?: string;
}

/** The text on a card, with its built citation. */
export interface CodeQuote {
  text: string;
  citation: string;
  /**
   * Where `text` came from. Only "code" is verbatim code-database text.
   * "ranking" is the AI's reason for ranking the article; "summary" is a cached case summary.
   * Absent on older cards: the citation decides (see `quoteKind`).
   */
  source?: "code" | "ranking" | "summary";
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
  /** The answer is shown but the engine has not stored it yet; the card stays open so answering sends it again. */
  pending?: boolean;
  /** Set when search or identify suggested the provision and the applicant has not confirmed it. */
  suggestion?: "search" | "identify";
  /** For code identification: committed under the calibrated Part 9 rule, or one of the quoted choices. */
  rank?: "committed" | "choice";
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

/** Empty until chosen. Saved API authorities remain portable beyond the current picker options. */
export type AuthorityId = string;

export type GapSeverity = "blocking" | "warning";

export interface Gap {
  id: string;
  severity: GapSeverity;
  label: string;
  /** Hash route that fixes the gap. */
  href: string;
  /** Engine or local field, used to drop a second copy of the same item. */
  field?: string;
  /** False only when the current completeness check explicitly permits an officer handoff. */
  submissionBlocking?: boolean;
}

/**
 * One staged write for POST /cases/{id}/evidence, optionally binding a verified owned upload.
 * It stays staged until the engine acknowledges this exact `rev`; only then is it shown as saved.
 * `responsible`/`date`: a string is sent, null withdraws a saved value, undefined is omitted.
 */
export interface ListedEvidence {
  id: string;
  rev: number;
  operation: "create" | "update";
  /** The plan task the document was added to. Create sends it as the explicit scope. */
  taskId: string;
  provisionId: string;
  evidenceType: string;
  /** The document name. Sent as both title and description. */
  description: string;
  responsible?: string | null;
  date?: string | null;
  fileRef?: string | null;
}

/** One document editor: three short steps (name, type, optional details). */
export interface EvidenceDraft {
  document: string;
  responsible: string;
  date: string;
  evidenceType: string;
  note: string;
  step?: number;
  /** Slot being edited; absent for a new document. */
  editing?: string;
  /** Undefined retains a saved binding; null explicitly removes it. */
  fileRef?: string | null;
}

export type ApplicantType = "manufacturer" | "contractor" | "homebuilder" | "builder" | "designer" | "owner" | "engineer" | "other";

export interface Case {
  id: string;
  title: string;
  /**
   * The title is a saved name (from the engine) or the applicant's own; the description never replaces
   * it. Unset on a new draft, whose placeholder title is never sent as a name.
   */
  titleKept?: boolean;
  applicantType: ApplicantType | null;
  /** Test-fixture provenance only. Product visits never load sample cases. */
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
  /** Listing writes waiting for the engine's acknowledgement. Not file references. */
  listedEvidence?: ListedEvidence[];
  /** Listed documents whose code reference was withdrawn. They stay on the case, unlinked;
   * selecting that reference again does not relink them (engine `auto_link = false`). */
  unscopedEvidence?: string[];
  /** Evidence slot ids waiting for DELETE /cases/{id}/evidence/{id}. */
  deletedEvidence?: string[];
  /** Last listing revision number; each staged write takes the next one. */
  evidenceRev?: number;
  /** A removal the engine refused (for example an ambiguous older slot). Not retried. */
  evidenceIssues?: Record<string, string>;
  /** Unfinished editors for this visit only; never sent as facts. Reset clears them. */
  evidenceDrafts?: Record<string, EvidenceDraft>;
  /** What intake read, and its plan. Absent until the description has been read. */
  intake?: IntakeState;
  /** The latest code identification (committed articles, quoted choices, labels). */
  identify?: IdentifyResult;
  /** Derived Section D work at an explicit case snapshot; never sent as applicant facts. */
  professionalWork?: { basis: string; professional: ProfessionalResult; plan: SectionDPlan };
}
