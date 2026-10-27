/** Contract-shaped unit data only; no provider or real application records. */
import { readFile } from "node:fs/promises";
import type { ApplicantDraft, Case as EngineCase, DraftingRecord } from "../src/api/types.gen";
import type { Fact } from "../src/types";

export const draft = {
  id: "draft-risk", field: "process.risk_assessment", title: "Risk assessment",
  text: "A dry location is assumed.\n\nArrange a review of the proposed assembly.",
  claims: [
    { text: "A dry location is assumed.", kind: "assumption", sources: [{ source_id: "description", quote: "Assume a dry location.\nKeep this exact excerpt." }] },
    { text: "Arrange a review of the proposed assembly.", kind: "plan", sources: [{ source_id: "guidance", quote: "Review the proposed assembly." }] },
  ],
  questions: [{ text: "Who will prepare the assessment?", routed_to: "professional" }],
  status: "draft",
} satisfies Pick<ApplicantDraft, "id" | "field" | "title" | "text" | "claims" | "questions" | "status">;

export const drafting = {
  drafts: [draft], stale: false, input_fingerprint: "unit-fingerprint", registry_searches: [], notices: [],
  sources: [
    { id: "description", kind: "description", ref: "description", page: null, label: "Project description", text: "Assume a dry location.\nKeep this exact excerpt.", url: null },
    { id: "guidance", kind: "guidance", ref: "guide", page: 2, label: "Source guidance", text: "Review the proposed assembly.", url: "https://example.test/source.pdf" },
  ],
} satisfies Pick<DraftingRecord, "drafts" | "stale" | "input_fingerprint" | "registry_searches" | "notices" | "sources">;

export function pointed(field: string, value: string, id = field): Fact {
  return { id, field, value, status: "confirmed", kind: "pointed", confidence: null, formula: null, inputs: [], source: { type: "user_text", ref: "Unit fixture", quote: value } };
}

export async function savedDraftCase() {
  const base: EngineCase = JSON.parse(await readFile(new URL("../src/calm/fixtures/reopen-api-case.json", import.meta.url), "utf8"));
  return { ...base, id: "case-drafts", status: "draft", version: 1, intake: null, identify: null, decision: null,
    provisions: [], selected_articles: [], drafting: structuredClone(drafting),
    facts: [pointed("project.description", "Assume a dry location."), pointed("owner_name", "Unit owner"), pointed("process.risk_assessment", "My manual risk answer.")],
  };
}
