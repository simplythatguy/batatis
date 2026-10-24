/** Authenticated thread responses renew cookies, so stale requests must be aborted. */
import { useCallback, useLayoutEffect, useRef } from "react";
import { useAccount } from "./account";

export function useThreadRequests(caseId: string) {
  const { phase, user } = useAccount();
  const pending = useRef(new Set<AbortController>());

  // Layout cleanup runs on replacement/unmount before an old response can renew its cookie.
  // Depend on the user object too: a new login for the same user is a new account session.
  useLayoutEffect(() => {
    const requests = pending.current;
    return () => {
      for (const ctl of requests) ctl.abort();
      requests.clear();
    };
  }, [caseId, phase, user]);

  const startRequest = useCallback(() => {
    const ctl = new AbortController();
    pending.current.add(ctl);
    return ctl;
  }, []);
  const finishRequest = useCallback((ctl: AbortController) => { pending.current.delete(ctl); }, []);
  return { phase, user, startRequest, finishRequest };
}
