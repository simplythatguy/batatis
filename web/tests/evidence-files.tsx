// Mount the real wizard/provider without the unrelated account/router workflow.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "../../docs/design/tokens.css";
import "../src/styles.css";
import { CaseProvider, useCase } from "../src/store";
import { Recommendations } from "../src/screens/Recommendations";
import { Application } from "../src/calm/Application";
import { useRoute } from "../src/router";

function Probe() {
  const store = useCase();
  const route = useRoute();
  Object.assign(window, { caseStore: store });
  return store.phase === "case" ? route.path === "/application" ? <Application download="" /> : <Recommendations /> : null;
}
createRoot(document.getElementById("root")!).render(<StrictMode><CaseProvider><Probe /></CaseProvider></StrictMode>);
