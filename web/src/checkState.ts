/** Visit-local intent only. Server-side authorization/deduplication is a separate
 * integration requirement; this state does not protect arbitrary API clients. */
export type SaveStatus = "idle" | "unsaved" | "saving" | "saved" | "failed";
export type CheckStatus = "not_requested" | "running" | "needs_answers" | "ready" | "unavailable" | "stale";
export interface CheckState {
  status: CheckStatus;
  generation: number;
  revision: number;
  attempt: number;
  note: string;
  detail: string;
  completedAt?: string;
}
export const newCheckState = (): CheckState => ({ status: "not_requested", generation: -1, revision: -1, attempt: 0, note: "", detail: "" });
export const checkCurrent = (state: CheckState, generation: number, revision: number) =>
  state.generation === generation && state.revision === revision && ["needs_answers", "ready"].includes(state.status);
