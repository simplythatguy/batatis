// Test-only entry. Production screens and provider; no fixture enters the build.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "../../docs/design/tokens.css";
import "../src/shared.css";
import { App } from "../src/App";
import { CaseProvider, useCase } from "../src/store";
function Probe() {
  Object.assign(window, { caseStore: useCase() });
  return <App />;
}
const root = createRoot(document.getElementById("root")!);
Object.assign(window, { unmountCase: () => root.unmount() });
root.render(<StrictMode><CaseProvider><Probe /></CaseProvider></StrictMode>);
