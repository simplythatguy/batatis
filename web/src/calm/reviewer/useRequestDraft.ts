import { useCallback, useEffect, useRef, useState } from "react";
import { AccountsError } from "../../api/accounts";
import { packageReview, type ReviewTarget } from "../../api/packageReview";
import type { PackageReviewIndex, RequestLimits, ReviewSession } from "../../api/types.gen";
import { accountSession } from "../account";
import { draftProblem, draftReducer, editBody, initialDraft, type DraftEvent } from "./requestDraft";

export function useRequestDraft({ target, session, limits, enabled, onSaved, onConflict }: {
  target: ReviewTarget; session: ReviewSession; limits: RequestLimits; enabled: boolean;
  onSaved: (index: PackageReviewIndex) => void; onConflict: () => void;
}) {
  const [state, setState] = useState(() => initialDraft(session));
  const current = useRef(state);
  current.current = state;
  const callbacks = useRef({ onSaved, onConflict });
  callbacks.current = { onSaved, onConflict };
  const pending = useRef(false);
  const lifetime = useRef(0);
  useEffect(() => () => { lifetime.current++; }, [target.kind, target.id, session.version]);
  const acknowledged = useRef(session.information_request);
  useEffect(() => {
    if (session.information_request === acknowledged.current) return;
    acknowledged.current = session.information_request;
    // A refreshed request replaces the draft when nothing is unsaved, or when the last save was refused
    // as a conflict (the officer's edits were made against a request that no longer exists).
    const save = current.current.save;
    if (save.kind === "saved" || (save.kind === "error" && save.conflict)) setState(previous => ({ ...initialDraft(session), savedAt: previous.savedAt }));
  }, [session.information_request]);
  const dispatch = useCallback((event: DraftEvent) => setState(previous => draftReducer(previous, event)), []);

  const save = useCallback(async () => {
    const state = current.current;
    if (!enabled || pending.current || state.save.kind === "saved" || draftProblem(state.content, session, limits)) return;
    const epoch = lifetime.current, account = accountSession();
    const live = () => epoch === lifetime.current && account === accountSession();
    pending.current = true;
    dispatch({ type: "start" });
    try {
      const index = await packageReview.edit(target, session.version, editBody(state.content));
      if (!live()) return;
      if (!index.latest || index.latest.version !== session.version) throw new AccountsError(409, "The review version changed. Reload the latest review.", "request save version changed");
      acknowledged.current = index.latest.information_request;
      dispatch({ type: "saved", session: index.latest, at: new Date().toISOString() });
      callbacks.current.onSaved(index);
    } catch (error) {
      if (!live()) return;
      const conflict = error instanceof AccountsError && error.status === 409;
      const detail = error instanceof AccountsError && error.body && typeof error.body === "object" && "detail" in error.body ? error.body.detail : null;
      dispatch({ type: "failed", conflict, message: typeof detail === "string" ? detail : error instanceof AccountsError ? error.detail : "The request didn’t save. Try again." });
      if (conflict) callbacks.current.onConflict();
    } finally {
      pending.current = false;
    }
  }, [target, session, limits, enabled, dispatch]);

  const problem = draftProblem(state.content, session, limits);
  useEffect(() => {
    if (!enabled || state.save.kind !== "dirty" || problem) return;
    const timer = setTimeout(() => void save(), 600);
    return () => clearTimeout(timer);
  }, [state, problem, enabled, save]);
  useEffect(() => {
    if (state.save.kind === "saved") return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [state.save.kind]);
  return { state, dispatch, save, problem, pending: state.save.kind !== "saved" };
}
