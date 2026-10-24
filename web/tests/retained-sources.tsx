// The real applicant Application and officer ReviewDetail, backed by real authenticated HTTP.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "../../docs/design/tokens.css";
import "../src/styles.css";
import "../src/calm/calm.css";
import { CaseProvider, useCase } from "../src/store";
import { Application } from "../src/calm/Application";
import { ReviewDetail } from "../src/calm/reviewer/ReviewDetail";
import { RetainedSourceFiles } from "../src/RetainedSourceFiles";
import { useRoute } from "../src/router";

function Probe() {
  const store = useCase();
  const route = useRoute();
  Object.assign(window, { caseStore: store });
  if (route.path === "/inventory") return <RetainedSourceFiles caseId={route.params.get("case")} />;
  if (route.path === "/officer") return <ReviewDetail caseId={route.params.get("case") || ""} />;
  return store.phase === "case" ? <Application download="" /> : null;
}
createRoot(document.getElementById("root")!).render(<StrictMode><CaseProvider><Probe /></CaseProvider></StrictMode>);
