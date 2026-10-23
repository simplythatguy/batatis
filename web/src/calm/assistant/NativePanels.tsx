/** Open the existing comments route for the captured owned case; never selects another case. */
import { useEffect } from "react";
import { getAccountState } from "../account";
import { getAssistantState, assistantKey, useAssistant } from "./assistant";
import { registerPanel } from "./destinations";
const frame = () => new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));

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
        location.hash = `#/comments?case=${encodeURIComponent(caseId)}`;
        for (let i = 0; i < 60; i++) {
          await frame();
          if (!current()) return false;
          const [path, query = ""] = location.hash.slice(1).split("?");
          // Shell may remove the redundant case parameter after checking the open case.
          if (path === "/comments" && (!query || new URLSearchParams(query).get("case") === caseId) && document.querySelector(".cf-comments")) return true;
        }
        return false;
      }));
    }

    return () => {
      live = false; offs.forEach((off) => off());
    };
  }, [b.accountId, b.role, b.authority, b.caseId, b.mode, ownedCaseId]);
  return null;
}
