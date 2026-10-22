import { createContext, useContext } from "react";
import { Icon24 } from "../icons";
import { MOD_KEY } from "../ui";
import { toggleAssistant, useAssistant } from "./assistant";

/** True inside the shell, where the assistant panel is mounted; pages outside it get no Ask. */
export const AskHost = createContext(false);

/** The one pointer and touch entry to the assistant (Cmd/Ctrl+J and field help are the others). */
export function AskButton() {
  const host = useContext(AskHost);
  const assistant = useAssistant();
  if (!host) return null;
  return (
    <button type="button" className="cf-btn is-ghost is-sm cf-ask" aria-pressed={assistant.open} aria-label="Ask the assistant" onClick={toggleAssistant} title={`Assistant (${MOD_KEY} J)`}>
      <Icon24 name="spark" size={16} /><span className="cf-ask-label">Ask</span>
    </button>
  );
}
