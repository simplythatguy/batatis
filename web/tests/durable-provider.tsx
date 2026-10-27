/** Mount production save hooks in a real DOM; the runner supplies an in-memory HTTP fixture. */
import { createRoot } from "react-dom/client";
import { CaseProvider, useCase } from "../src/store";
import { bootAccount, getAccountState, setAccountState } from "../src/calm/account";
import { draftAccount } from "../src/calm/applicantDraft";
import { useQuestionDraft } from "../src/calm/useQuestionDraft";
import { questionDrafts } from "../src/calm/questionDrafts";
import { getSession, updateSession } from "../src/calm/session";
import { engineGeneration } from "../src/api/sync";
import { signOut } from "../src/calm/auth/useAuthGate";
import { signOutStatus } from "../src/calm/auth/signOutGuard";
import { Start } from "../src/calm/Start";
import { SaveStatus } from "../src/calm/Shell";
import { pauseApplicationEdits } from "../src/calm/applicationEditing";
import { ReadingState, CodeProgress } from "../src/calm/ReadCards";

function Probe() {
  const store = useCase();
  const base = String(store.c.facts.find(f => f.field === "owner")?.value ?? "");
  const draft = useQuestionDraft(draftAccount(getAccountState().user), engineGeneration(), store.engineId, "owner-editor", base);
  Object.assign(window, { caseStore: store, questionDrafts, getSession, updateSession, getAccountState, setAccountState, signOut, signOutStatus, pauseApplicationEdits });
  return <>
    <SaveStatus />
    <Start />
    <section aria-label="Reading progress"><ReadingState /></section>
    <section aria-label="Code progress"><CodeProgress /></section>
    <textarea aria-label="Unconfirmed owner" value={draft.value} onChange={e => draft.setValue(e.target.value)} />
    <output aria-label="Editor conflict">{draft.conflict ? "Changed base; text retained" : ""}</output>
    <output aria-label="Save state">{store.saveStatus}</output>
    <output aria-label="Job state">{JSON.stringify(store.reading)}</output>
  </>;
}

createRoot(document.getElementById("root")!).render(<CaseProvider><Probe /></CaseProvider>);
bootAccount();
