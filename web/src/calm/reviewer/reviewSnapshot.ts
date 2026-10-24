/** One read-only officer snapshot. Publish it together, or keep the previous view and its drafts. */
import { accounts, type Message } from "../../api/accounts";
import { engine, EngineError, type EngineGap, type InformationRequest } from "../../api/client";
import type { Case } from "../../api/types.gen";

export async function readReviewSnapshot(caseId: string, signal: AbortSignal): Promise<{
  c: Case;
  gaps: EngineGap[] | null;
  information: InformationRequest | null;
  messages: Message[] | null;
  gapError: string;
  questionError: string;
}> {
  const c = await engine.getCase(caseId, signal) as unknown as Case;
  const [gaps, information, messages] = await Promise.allSettled([
    engine.gaps(caseId, signal), engine.informationRequest(caseId, signal), accounts.messages(caseId, signal),
  ]);
  // A claim, resubmission or content edit during the reads must not mix old facts with new questions.
  const latest = await engine.getCase(caseId, signal);
  if (latest.version !== c.version) throw new EngineError(409, "The application changed while its review was loading. Refresh to read the current version.");
  const info = information.status === "fulfilled" ? information.value : null;
  const matched = info?.case_id === c.id && info.case_version === c.version && Array.isArray(info.questions);
  return {
    c,
    gaps: gaps.status === "fulfilled" ? gaps.value : null,
    information: matched ? info : null,
    messages: messages.status === "fulfilled" ? messages.value : null,
    gapError: gaps.status === "fulfilled" ? "" : "The completeness check didn’t run. Refresh to try again.",
    questionError: matched ? "" : "Saved questions didn’t load for this revision. Refresh to try again; an empty gap list does not mean every question was answered.",
  };
}
