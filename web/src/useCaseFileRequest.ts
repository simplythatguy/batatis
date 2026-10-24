import { useCallback, useEffect, useMemo, useRef } from "react";
import { accountSession, useAccount } from "./calm/account";

/** File reads belong to one case and account snapshot, including re-login as the same person.
 * Abort is paired with a callback guard because a completed/ignored abort can still resolve. */
export function useCaseFileRequest(caseId: string, fileId = "") {
  useAccount();
  const session = accountSession();
  const scope = useMemo(() => ({ caseId, fileId, session }), [caseId, fileId, session]);
  const latest = useRef(scope);
  latest.current = scope;
  const pending = useRef<AbortController | null>(null);
  const cancel = useCallback(() => { pending.current?.abort(); pending.current = null; }, []);
  useEffect(() => cancel, [scope, cancel]);
  const start = useCallback(() => {
    cancel();
    const controller = new AbortController();
    pending.current = controller;
    return {
      signal: controller.signal,
      current: () => !controller.signal.aborted && pending.current === controller
        && latest.current === scope && accountSession() === scope.session,
    };
  }, [scope, cancel]);
  return { scope, start, cancel };
}
