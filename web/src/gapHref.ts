/** Where the applicant fixes an engine finding. Never falls back to Describe: an unmatched field opens its section. */
const FIELD_HREF: Record<string, string> = {
  owner_name: "#/application?tab=A&focus=field-owner",
  representative: "#/application?tab=A&focus=field-representative",
  mailing_address: "#/application?tab=A&focus=field-mailingAddress",
  application_date: "#/application?tab=A&focus=field-date",
  civic_address: "#/application?tab=B&focus=field-municipalAddress",
  legal_description: "#/application?tab=B&focus=field-legalDescription",
  alternative_description: "#/application?tab=B&focus=field-alternative",
  scope: "#/application?tab=B&focus=field-scope",
  jurisdiction: "#/describe?focus=authority",
  rationale: "#/application?tab=alt&focus=field-rationale",
  risk_assessment: "#/application?tab=alt&focus=field-risk",
  mitigating_measures: "#/application?tab=alt&focus=field-mitigation",
  assumptions_and_limits: "#/application?tab=alt&focus=field-assumptions",
  maintenance_operation: "#/application?tab=alt&focus=field-maintenance",
  qualifications: "#/application?tab=alt&focus=field-qualifications",
  provisions: "#/code-check",
  professional_qualifications: "#/application?tab=alt&focus=field-qualifications",
  professional_requirement: "#/application?tab=D&focus=prof-role",
  responsible_professional: "#/application?tab=D&focus=prof-role",
};

// Div C 2.3.1.1 documentation items and the "demonstrate" prompts, by the paper block that answers them.
const DOCUMENTATION_HREF: Record<string, string> = {
  "div_c.code_analysis": FIELD_HREF.rationale,
  "div_c.qualifications": FIELD_HREF.qualifications,
  "div_c.maintenance": FIELD_HREF.maintenance_operation,
  "demonstrate.failure_conditions": FIELD_HREF.risk_assessment,
  "demonstrate.lapsed_maintenance": FIELD_HREF.maintenance_operation,
  "demonstrate.emergency_response": FIELD_HREF.assumptions_and_limits,
};

const EVIDENCE_HREF = "#/application?focus=evidence";
const SIGN_HREF = "#/application?step=sign";
const SECTION_HREF: Record<string, string> = {
  A: "#/application?tab=A", B: "#/application?tab=B", C: "#/section-c", D: EVIDENCE_HREF, process: "#/application?tab=alt",
};

/** The app link that fixes a field (engine gap field or a reviewer's ticked item). */
export function hrefFor(field: string, section?: string | null): string {
  const key = field;
  if (FIELD_HREF[key]) return FIELD_HREF[key];
  if (DOCUMENTATION_HREF[key]) return DOCUMENTATION_HREF[key];
  if (/^(?:signature|owner_signature|owner_rep_signature|consent)\b|signature_date$/.test(key)) return SIGN_HREF;
  if (/^(?:section_c|provisions|citation)/.test(key)) return "#/section-c";
  if (/^(?:evidence|professional|supporting_doc|attachment|document|file\.|div_c\.testing_procedures)/.test(key)) return EVIDENCE_HREF;
  if (key.startsWith("section_b")) return SECTION_HREF.B;
  return (section && SECTION_HREF[section]) || "#/application";
}
