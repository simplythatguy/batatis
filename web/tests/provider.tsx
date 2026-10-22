// Test-only entry: mounts the production provider and exposes its public interface.
import { createRoot } from "react-dom/client";
import { CaseProvider, useCase } from "../src/store";
function Probe() {
  const store = useCase();
  Object.assign(window, { caseStore: store });
  return <pre>{JSON.stringify({ phase: store.phase, engineId: store.engineId, savedNote: store.savedNote, syncOk: store.syncOk, gaps: store.gaps })}</pre>;
}
createRoot(document.getElementById("root")!).render(<CaseProvider><Probe /></CaseProvider>);
