// Stable mounted production dialog: tests vary props/session without relying on remounts.
import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import "../../docs/design/tokens.css";
import "../src/styles.css";
import "../src/calm/calm.css";
import "../src/calm/accounts.css";
import { review } from "../src/api/accounts";
import type { EngineGap } from "../src/api/client";
import { setAccountState } from "../src/calm/account";
import { ReturnDialog } from "../src/calm/reviewer/ReturnDialog";

function Harness() {
  const [props, setProps] = useState({ open: false, caseId: "unopened", applicant: "SYNTHETIC applicant", gaps: [] as EngineGap[] });
  const [sent, setSent] = useState("");
  Object.assign(window, { returnDraft: { setProps, setAccountState } });
  return <div className="cf-app">
    <ReturnDialog {...props} onClose={() => setProps(current => ({ ...current, open: false }))}
      onSend={async (message, items) => {
        await review.decide(props.caseId, { outcome: "return", message, items });
        setSent(message);
        setProps(current => current.caseId === props.caseId ? { ...current, open: false } : current);
      }} />
    <output aria-label="Sent message">{sent}</output>
  </div>;
}
createRoot(document.getElementById("root")!).render(<StrictMode><Harness /></StrictMode>);
