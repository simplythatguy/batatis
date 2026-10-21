/**
 * Identify payloads from PR #12. A ranking hint is not a Yes.
 * `cached` is true only for mode `cached_demo`.
 * The decision route may return a Section C row or the stored identify body.
 */
import type { SectionCRow } from "./api/types.gen";
import type { IdentifyArticle, IdentifyResult } from "./api/types.gen";
import type { Action } from "./model";
import type { CandidateAnswer } from "./types";

export const DECISION_UNAVAILABLE =
  "Article decisions aren't available yet. Your Yes, No, or Not sure is kept on this check.";

export const CONFIRM_UNAVAILABLE = "Saving accepted articles isn't available yet.";

export const INFORMATION_UNAVAILABLE = "The officer information request isn't available yet.";

export function isCachedDemo(payload: { mode?: string | null; cached?: boolean | null }): boolean {
  return payload.mode === "cached_demo" && payload.cached === true;
}

export function wireDecision(answer: CandidateAnswer): "yes" | "no" | "not_sure" {
  return answer === "not-sure" ? "not_sure" : answer;
}

/** A stored decision only. `suggested`, `committed`, and `status` are ranking hints. */
export function articleAnswer(article: { decision?: string | null }): CandidateAnswer | null {
  if (article.decision === "yes" || article.decision === "no") return article.decision;
  if (article.decision === "not_sure") return "not-sure";
  return null;
}

export interface PlannedArticle {
  provision: string;
  title: string | null;
  part: number;
  quote: string | null;
  reason: string | null;
}

export interface PlannedQuestion {
  id?: string;
  field: string;
  text: string;
  why?: string | null;
}

export interface PlannedDecision {
  candidateId: string;
  answer: CandidateAnswer;
  openQuestionId: string | null;
}

export interface IdentifyPlan {
  articles: PlannedArticle[];
  questions: PlannedQuestion[];
  noteQuestions: boolean;
  decisions: PlannedDecision[];
  note: string;
}

/** The fields planIdentify reads. A stored or cached payload may omit any of them. */
export type IdentifyPayload = Partial<Pick<IdentifyResult, "questions" | "open_questions">> & {
  mode?: string | null;
  cached?: boolean | null;
  articles?: (Pick<IdentifyArticle, "provision" | "title"> & Partial<IdentifyArticle>)[];
};

export function planIdentify(result: IdentifyPayload, limit?: number): IdentifyPlan {
  const ranked = (result.articles ?? []).filter((article) => Boolean(article?.provision && /^\d/.test(article.provision)));
  const sliced = limit == null ? ranked : ranked.slice(0, limit);
  const articles = sliced.map((article) => ({
    provision: article.provision,
    title: article.title,
    part: article.part || Number(String(article.provision).split(".")[0]) || 0,
    quote: article.quote ?? null,
    reason: article.reason ?? null,
  }));
  const questions = (result.open_questions ?? [])
    .filter((q) => q.field && q.text)
    .map((q) => ({ id: q.id, field: q.field ?? "", text: q.text ?? "", why: q.why }));
  const count = articles.length;
  const lead = count
    ? `${count} articles ranked. Choose Yes, No, or Not sure on each one. Nothing is accepted until you choose Yes.`
    : (result.questions?.[0] ?? "Article ranking returned no articles for this description.");
  const note = isCachedDemo(result) ? `${lead} This ranking is a stored demo. It is not an acceptance.` : lead;
  const decisions = sliced.flatMap((article) => {
    const answer = articleAnswer(article);
    if (!answer) return [];
    return [
      {
        candidateId: `id-${article.provision}`,
        answer,
        openQuestionId: answer === "not-sure" && article.open_question_id ? article.open_question_id : null,
      },
    ];
  });
  return {
    articles,
    questions,
    noteQuestions: questions.length > 0 || result.open_questions != null,
    decisions,
    note,
  };
}

export function applyIdentifyPlan(dispatch: (action: Action) => void, plan: IdentifyPlan) {
  if (plan.articles.length) dispatch({ type: "addIdentified", articles: plan.articles });
  if (plan.noteQuestions) dispatch({ type: "noteIdentifyQuestions", questions: plan.questions });
  for (const decision of plan.decisions) {
    dispatch({ type: "answerCandidate", id: decision.candidateId, answer: decision.answer });
    if (decision.answer === "not-sure" && decision.openQuestionId) {
      dispatch({ type: "bindOpenQuestion", candidateId: decision.candidateId, questionId: decision.openQuestionId });
    }
  }
}

export interface DecisionRead {
  row: SectionCRow | null;
  openQuestionId: string | null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object";
}

function isFullRow(value: unknown): value is SectionCRow {
  if (!isRecord(value)) return false;
  if ("articles" in value) return false;
  return (
    typeof value.provision_id === "string" &&
    typeof value.citation === "string" &&
    typeof value.attribution_status === "string" &&
    Array.isArray(value.pairs) &&
    Array.isArray(value.intents)
  );
}

function sameProvision(id: string, provision: string): boolean {
  return id === provision || id.startsWith(provision) || provision.startsWith(id);
}

function rowFrom(value: Record<string, unknown>): SectionCRow {
  const row = value as unknown as SectionCRow;
  return {
    ...row,
    attributed_via: row.attributed_via ?? null,
    differs: row.differs ?? false,
    intent_comparison: row.intent_comparison ?? null,
    intents: row.intents ?? [],
    only_in_ae: row.only_in_ae ?? [],
    only_in_intent: row.only_in_intent ?? [],
    pairs: row.pairs ?? [],
    related_root: row.related_root ?? null,
    related_root_method: row.related_root_method ?? null,
    explainer: row.explainer ?? null,
  };
}

/** Accept a bare Section C row or the identify envelope #12 returns today. */
export function readDecisionBody(body: unknown, provision: string): DecisionRead {
  if (!isRecord(body)) return { row: null, openQuestionId: null };
  if (Array.isArray(body.articles)) {
    const cards = body.articles.filter(isRecord);
    const card = cards.find((article) => {
      const listed = typeof article.provision === "string" ? article.provision : "";
      const sentence = typeof article.provision_id === "string" ? article.provision_id : "";
      return listed === provision || sentence === provision || sameProvision(listed, provision) || sameProvision(sentence, provision);
    });
    const openQuestionId = card && typeof card.open_question_id === "string" ? card.open_question_id : null;
    const rows = Array.isArray(body.section_c) ? body.section_c.filter(isFullRow).map((row) => rowFrom(row as unknown as Record<string, unknown>)) : [];
    const row = rows.find((item) => item.provision_id === provision || sameProvision(item.provision_id, provision)) ?? null;
    return { row, openQuestionId };
  }
  if (isFullRow(body)) {
    const extra = body as SectionCRow & { open_question_id?: unknown };
    const openQuestionId = typeof extra.open_question_id === "string" ? extra.open_question_id : null;
    return { row: rowFrom(body as unknown as Record<string, unknown>), openQuestionId };
  }
  return { row: null, openQuestionId: null };
}
