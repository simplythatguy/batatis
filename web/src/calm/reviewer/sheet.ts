/**
 * The submitted application as the officer reads it: Part 1, Sections A–D, straight from the
 * saved engine case. Field aliases mirror engine/completeness.py and engine/process_fields.py, so a
 * case written by the web app or through the API reads the same. Missing values stay null. Pure.
 */
import type { Case as EngineCase } from "../../api/types.gen";
import type { InformationRequest, ReviewQuestion } from "../../api/client";
import { answerWithdrawn, localField } from "../../intakeFields";
import { evidenceBinding } from "../../evidence";

type Fact = EngineCase["facts"][number];

export interface SheetRow {
  field?: string;
  label: string;
  value: string | null;
  /** Required for completeness (missing shows "— missing"; optional shows "—"). */
  required: boolean;
  /** The applicant has not confirmed this value. */
  unconfirmed?: boolean;
}

export interface SheetRef {
  provision: string;
  codes: string;
}

export interface SheetView {
  applicant: SheetRow[];
  project: SheetRow[];
  alternative: SheetRow;
  references: SheetRef[];
  process: SheetRow[];
  supporting: SheetRow[];
  /** One per document: a study listed once per objective it covers shows once; `ids` holds every listing. */
  documents: { id: string; ids: string[]; title: string; fileId: string | null; fileName: string | null; type: string | null; author: string | null; date: string | null }[];
  questions: ReviewQuestion[];
}

const A_FIELDS: [string, string[], boolean][] = [
  ["Owner", ["owner_name", "owner", "section_a.owner_name"], true],
  ["Representative", ["representative", "owner_rep_name", "applicant_name"], true],
  ["Mailing address", ["mailing_address", "mailingAddress"], true],
  ["Date of request", ["application_date", "request_date", "date", "section_a.date"], true],
];

const B_FIELDS: [string, string[], boolean][] = [
  ["Jurisdiction-wide variance", ["scope"], true],
  ["Permit number", ["permit", "permit_number"], false],
  ["Municipal address", ["civic_address", "municipal_address", "municipalAddress", "address"], true],
  ["Legal description", ["legal_description", "legalDescription", "section_b.legal_description"], true],
];

const PROCESS: [string, string[]][] = [
  ["Rationale", ["rationale"]],
  ["Risk assessment", ["risk_assessment", "risk"]],
  ["Mitigating measures", ["mitigating_measures", "mitigation"]],
  ["Assumptions and limits", ["assumptions_and_limits", "assumptions_limits", "assumptions"]],
  ["Maintenance and operation", ["maintenance_operation", "operation_maintenance", "maintenance"]],
  ["Qualifications", ["qualifications"]],
];

const LABELS: Record<string, string> = {
  site: "No, one site",
  jurisdiction: "Yes, jurisdiction-wide",
  not_engaged: "Not engaged yet",
  not_engaged_yet: "Not engaged yet",
  not_sure: "Not sure",
  true: "Yes",
  false: "No",
};

/** The newest fact among the aliases (the engine's latest_fact rule), without withdrawn answers. */
export function latest(facts: Fact[], fields: string[]): Fact | null {
  const aliases = new Set(fields.map(localField));
  for (let i = facts.length - 1; i >= 0; i--) {
    const f = facts[i];
    if (aliases.has(localField(f.field))) {
      if (answerWithdrawn(f)) return null;
      return f;
    }
  }
  return null;
}

function text(f: Fact | null): string | null {
  if (!f || f.value == null) return null;
  const raw = typeof f.value === "boolean" ? String(f.value) : String(f.value).trim();
  if (!raw) return null;
  return LABELS[raw] ?? raw;
}

function row(facts: Fact[], label: string, fields: string[], required: boolean): SheetRow {
  const f = latest(facts, fields);
  const value = text(f);
  return { field: fields[0], label, value, required, unconfirmed: Boolean(value && f?.status === "unconfirmed") };
}

const authorityLabel = (id: string | null | undefined) => (id ? id.charAt(0).toUpperCase() + id.slice(1) : null);

export function sheetFromEngine(c: EngineCase, information?: InformationRequest | null): SheetView {
  const facts = c.facts ?? [];
  // Engagement can be shown when no role is stated; it never becomes a credential.
  const professionalField = latest(facts, ["professional.role"]) ? "professional.role" : "professional.status";
  const registrationField = latest(facts, ["professional.registration_number"]) ? "professional.registration_number" : "professional.seal";
  const docs = new Map<string, string>();
  for (const f of facts) {
    const m = /^evidence\.([^.]+)\.title$/.exec(f.field);
    if (m && typeof f.value === "string" && f.value.trim()) docs.set(m[1], f.value.trim());
  }
  const documents = listedDocuments(facts, docs);
  const references = (c.section_c ?? []).map((r) => {
    const objectives = [...new Set(r.pairs.map((p) => p.objective).filter(Boolean))];
    const functions = [...new Set(r.pairs.map((p) => p.function).filter(Boolean))];
    const codes = objectives.length || functions.length
      ? `Objectives ${objectives.join(", ") || "—"} · Functions ${functions.join(", ") || "—"}`
      : "No row in the attribution table";
    return { provision: r.provision_id, codes };
  });
  return {
    questions: information && information.case_id === c.id && information.case_version === c.version ? information.questions ?? [] : [],
    applicant: A_FIELDS.map(([l, f, r]) => row(facts, l, f, r)),
    project: [
      { field: "authority", label: "Reviewing authority", value: authorityLabel(c.authority ?? c.jurisdiction?.id), required: true },
      ...B_FIELDS.map(([l, f, r]) => row(facts, l, f, r)),
    ],
    alternative: row(facts, "Proposed alternative", ["alternative_description", "alternative"], true),
    references,
    process: PROCESS.map(([l, f]) => row(facts, l, [...f.map((x) => `process.${x}`), ...f], true)),
    supporting: [
      row(facts, "Registered professional", [professionalField], true),
      row(facts, "Registration or seal", [registrationField], false),
      { field: "documents", label: "Documents listed", value: documents.length ? `${documents.length} ${documents.length === 1 ? "document" : "documents"}` : null, required: true },
    ],
    documents,
  };
}

const same = (s: string | null) => (s ?? "").toLowerCase().replace(/\s+/g, " ").trim();

function listedDocuments(facts: Fact[], docs: Map<string, string>): SheetView["documents"] {
  const out = new Map<string, SheetView["documents"][number]>();
  for (const [id, title] of docs) {
    const binding = evidenceBinding(facts, id);
    const metadata = (field: string) => text(latest(facts, [`evidence.${id}.${field}`]));
    const doc = { id, ids: [id], title, fileId: binding?.fileId ?? null, fileName: binding?.name ?? null,
      type: metadata("evidence_type"), author: metadata("responsible_party"), date: metadata("date") };
    const key = JSON.stringify([same(title), same(doc.author), same(doc.date)]);
    const first = out.get(key);
    if (first) { first.ids.push(id); first.fileId ??= doc.fileId; first.fileName ??= doc.fileName; }
    else out.set(key, doc);
  }
  return [...out.values()];
}
