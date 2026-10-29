/**
 * What the officer reads by name. A saved review also carries every raw case answer (journey state, rule
 * inputs, office choices) and the generated form's own widget names ("Owner", "Lot", "Signature1"). Only
 * fields with a form label here are shown, and a widget shows as the case field it prints, so nothing
 * repeats. Pure.
 */
import { localField } from "../../intakeFields";

const LABEL: Readonly<Record<string, string>> = {
  owner: "Owner",
  representative: "Representative",
  mailingAddress: "Mailing address",
  date: "Date of request",
  owner_signature: "Owner signature",
  owner_rep_signature: "Representative signature",
  authority: "Reviewing authority",
  scope: "Jurisdiction-wide variance",
  permit: "Permit number",
  municipalAddress: "Municipal address",
  legalDescription: "Legal description",
  alternative: "Proposed alternative",
  building_area_m2: "Building area (m²)",
  storeys: "Storeys",
  occupancy: "Occupancy",
  code_or_standard: "Code or standard",
  "process.rationale": "Rationale",
  "process.risk_assessment": "Risk assessment",
  "process.mitigating_measures": "Mitigating measures",
  "process.assumptions_and_limits": "Assumptions and limits",
  "process.maintenance_operation": "Maintenance and operation",
  "process.qualifications": "Qualifications",
  "professional.role": "Registered professional",
  "professional.status": "Registered professional",
  "professional.registration_number": "Registration or seal",
  "professional.seal": "Registration or seal",
  documents: "Documents listed",
};

const LEGAL_PARTS = ["Lot", "Block", "Plan", "QTR", "SEC", "TWP", "RGE", "MER",
  "lot", "block", "plan", "ats_qtr", "ats_sec", "ats_twp", "ats_rge", "ats_mer"];

/** The form's widget and passage names, as the case field each one prints. */
const PRINTS: Readonly<Record<string, string>> = {
  Owner: "owner", "Owner Print": "owner", "Owner Rep": "representative", "Owner Rep Print": "representative",
  "Mailing Address": "mailingAddress", "Date of Reqeuest": "date", Permit: "permit",
  "Municipal Address": "municipalAddress", "Legal description": "legalDescription",
  ...Object.fromEntries(LEGAL_PARTS.map((name) => [name, "legalDescription"])),
  "Check Box": "scope", "Code or Standard": "code_or_standard",
  "Article(s)": "section_c.article", Objective: "section_c.objective", Function: "section_c.function",
  "Intent statement": "section_c.intent",
  "Supporting Doc": "documents", "Name Responsible": "documents", supporting_doc: "documents",
  Signature1: "owner_signature", Signature2: "owner_rep_signature", signature: "owner_signature",
  Date1: "owner_signature_date", Date2: "owner_rep_signature_date",
  professional_name: "professional.role", professional_qualifications: "process.qualifications",
};

/** The one name a field goes by on the sheet, whichever alias or form widget carried it. */
export const formField = (field: string): string => PRINTS[field] ?? localField(field);

/** The form label for a field, or null when it is internal to the case. */
export const formLabel = (field: string): string | null => LABEL[formField(field)] ?? null;

const WORDS: Readonly<Record<string, string>> = { true: "Yes", false: "No" };

/** A saved value as a person reads it: "Yes", not "True"; "Single family", not "single_family". */
export function formValue(value: string | null | undefined): string | null {
  if (value == null) return null;
  const word = WORDS[value.trim().toLowerCase()];
  if (word) return word;
  return /^[a-z]+(?:_[a-z]+)+$/.test(value) ? value.charAt(0).toUpperCase() + value.slice(1).replace(/_/g, " ") : value;
}

const DOCUMENT_PART: Readonly<Record<string, string>> = {
  title: "title", description: "description", evidence_type: "type", responsible_party: "responsible person",
  issuer: "issuer", date: "date", file_ref: "attachment", professional_seal: "seal",
};

/** What a change in the submission history is called, or null when it is internal to the case. */
export function changeLabel(field: string, documentTitle: (id: string) => string | null): string | null {
  if (field.startsWith("clarification.")) return "Applicant clarification";
  if (field.startsWith("request_answer.")) return "Answer to your request";
  if (field.startsWith("codecheck.")) return "Applicant code check answer";
  if (field.startsWith("identify.")) return "Applicant code question answer";
  if (field === "provisions") return "Code references";
  const document = /^evidence\.([^.]+)\.(?:listing\.)?([^.]+)$/.exec(field);
  if (document) {
    const part = DOCUMENT_PART[document[2]];
    return part ? `${documentTitle(document[1]) || "Document"} · ${part}` : null;
  }
  return formLabel(field);
}
