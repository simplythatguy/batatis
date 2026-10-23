/** Open the existing comments route for the captured owned case; never selects another case. */
import { useEffect } from "react";
import { getAccountState } from "../account";
import { openCommentsPage } from "../comments/opening";
import { getAssistantState, assistantKey, useAssistant } from "./assistant";
import { registerPanel } from "./destinations";

export function NativePanels({ ownedCaseId }: { ownedCaseId: string | null }) {
  const { binding: b } = useAssistant();
  useEffect(() => {
    if (!b.caseId || !b.accountId || b.mode !== "case") return;
    const key = assistantKey(), caseId = b.caseId;
    let live = true;
    const current = () => {
      const a = getAccountState(), now = getAssistantState().binding;
      return live && assistantKey() === key && now.caseId === caseId && a.phase === "signed-in" && a.user?.id === b.accountId && a.user.role === b.role && a.user.authority === b.authority;
    };
    const offs: (() => void)[] = [];

    if (b.role === "applicant" && ownedCaseId === caseId) {
      offs.push(registerPanel("comments", caseId, async (requested) => {
        if (requested !== caseId || !current()) return false;
        // Opened only once the page renders this application (its data-application-id), not merely the route.
        const opened = await openCommentsPage(caseId);
        return opened && current();
      }));
    }

    return () => {
      live = false; offs.forEach((off) => off());
    };
  }, [b.accountId, b.role, b.authority, b.caseId, b.mode, ownedCaseId]);
  return null;
}
