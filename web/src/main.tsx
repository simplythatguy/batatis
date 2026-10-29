import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { SpeedInsights } from "@vercel/speed-insights/react";
import "@fontsource-variable/inter/opsz.css";
import "@fontsource-variable/geist-mono";
import "../../docs/design/tokens.css";
import "./shared.css";
import "./calm/calm.css";
import "./calm/mercury.css";
import { App } from "./App";
import { CaseProvider } from "./store";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <CaseProvider>
      <App />
      <SpeedInsights />
    </CaseProvider>
  </StrictMode>,
);
