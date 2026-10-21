// Test-only entry. Production screens and provider; no fixture enters the build.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "../../docs/design/tokens.css";
import "../src/styles.css";
import { App } from "../src/App";
import { CaseProvider, useCase } from "../src/store";
function Probe() {
  Object.assign(window, { caseStore: useCase() });
  return <App />;
}
createRoot(document.getElementById("root")!).render(<StrictMode><CaseProvider><Probe /></CaseProvider></StrictMode>);
